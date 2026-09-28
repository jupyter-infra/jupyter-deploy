from collections.abc import Generator
from contextlib import contextmanager

import botocore.exceptions

from jupyter_deploy.enum import ProviderType
from jupyter_deploy.exceptions import (
    InvalidProviderCredentialsError,
    ProviderPermissionError,
    TransientProviderError,
)

# Permission-related error codes
# Sources:
# - UnauthorizedOperation: EC2 API
#   (docs.aws.amazon.com/AWSEC2/latest/APIReference/errors-overview.html)
# - AccessDenied, AccessDeniedException, NotAuthorized, OptInRequired: Common across AWS services
#   (observed in practice, need specific documentation)
PERMISSION_ERROR_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "NotAuthorized",
    "UnauthorizedOperation",
    "OptInRequired",
}

# Credential-related error codes
# Sources:
# - ExpiredToken, InvalidIdentityToken : STS API
#   (docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRoleWithWebIdentity.html)
#   (docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html)
# - AuthFailure, IncompleteSignature, InvalidClientTokenId, MissingAuthenticationToken
#   MissingAuthenticationToken: EC2 API
#  (docs.aws.amazon.com/AWSEC2/latest/APIReference/errors-overview.html)
# - AuthorizationHeaderMalformed, AuthorizationQueryParametersError: S3 Error Responses
#   (docs.aws.amazon.com/AmazonS3/latest/API/ErrorResponses.html)
# - ExpiredTokenException: EKS Error Responses
#   (https://docs.aws.amazon.com/eks/latest/APIReference/CommonErrors.html)
CREDENTIAL_ERROR_CODES = {
    "ExpiredToken",
    "InvalidIdentityToken",
    "AuthFailure",
    "IncompleteSignature",
    "InvalidClientTokenId",
    "MissingAuthenticationToken",
    "AuthorizationHeaderMalformed",
    "AuthorizationQueryParametersError",
    "ExpiredTokenException",
}

# Error codes worth retrying: throttling and provider-side failures, as opposed to a permanent
# fault in the request or the caller's credentials. A caller that retries on its own schedule
# (the client proxy's credential refresh loop) needs this separated out — see
# TransientProviderError.
#
# The throttling and request-timeout codes are botocore's own retry sets, copied from
# `botocore.retries.standard` (`ThrottledRetryableChecker._THROTTLED_ERROR_CODES` and
# `TransientRetryableChecker._TRANSIENT_ERROR_CODES`). Copied rather than imported: those
# attributes are private, so importing them would tie us to botocore internals that can be renamed
# in any release, while the codes themselves are AWS wire values that outlive any one SDK version.
# The server-side codes below are AWS common errors
# (docs.aws.amazon.com/AWSEC2/latest/APIReference/CommonErrors.html); botocore catches those by
# status code instead, which the 5xx check in the handler also does.
#
# Note this is a *second* retry layer: botocore already retried these on its own schedule and gave
# up before the error reached us. Ours is what lets the proxy try again a whole refresh cycle later.
TRANSIENT_ERROR_CODES = {
    # Server-side failures (AWS common errors).
    "InternalError",
    "InternalFailure",
    "InternalServerError",
    "ServiceUnavailable",
    "ServiceUnavailableException",
    # Throttling (botocore's _THROTTLED_ERROR_CODES).
    "BandwidthLimitExceeded",
    "EC2ThrottledException",
    "LimitExceededException",
    "PriorRequestNotComplete",
    "ProvisionedThroughputExceededException",
    "RequestLimitExceeded",
    "RequestThrottled",
    "RequestThrottledException",
    "SlowDown",
    "ThrottledException",
    "Throttling",
    "ThrottlingException",
    "TooManyRequestsException",
    "TransactionInProgressException",
    # Request timeouts (botocore's _TRANSIENT_ERROR_CODES).
    "RequestTimeout",
    "RequestTimeoutException",
}


@contextmanager
def aws_error_context_manager() -> Generator[None, None, None]:
    """Catch botocore exceptions and re-raise as jupyter-deploy provider errors."""
    try:
        yield
    except botocore.exceptions.NoCredentialsError as e:
        raise InvalidProviderCredentialsError(
            provider_name=ProviderType.AWS,
            original_message=str(e),
        ) from e
    except botocore.exceptions.PartialCredentialsError as e:
        raise InvalidProviderCredentialsError(
            provider_name=ProviderType.AWS,
            original_message=str(e),
        ) from e
    except (botocore.exceptions.ConnectionError, botocore.exceptions.HTTPClientError) as e:
        # The request never reached AWS, or its response never came back: a network blip, a
        # sleeping laptop, DNS, a closed connection, a read timeout. Nothing about the request or
        # the credentials is wrong, so it is worth retrying. These two botocore base classes cover
        # EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError, ConnectionClosedError and
        # friends — catching the bases rather than the leaves keeps new subclasses retryable too,
        # which is the safe default direction. They are also exactly the pair botocore's own
        # retry layer treats as transient (`TransientRetryableChecker._TRANSIENT_EXCEPTION_CLS`).
        # (botocore.exceptions.ConnectionError is botocore's own class, unrelated to the builtin
        # of the same name.)
        raise TransientProviderError(
            provider_name=ProviderType.AWS,
            operation=None,
            original_message=str(e),
        ) from e
    except botocore.exceptions.ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        status_code = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
        # A 5xx means the service failed, not that the request was wrong, so treat it as transient
        # whatever code it carries — the named codes above are the ones AWS also returns as 4xx
        # (throttling). Permission and credential errors are 4xx, so they never match here.
        if error_code in TRANSIENT_ERROR_CODES or status_code >= 500:
            operation = e.operation_name if hasattr(e, "operation_name") else None
            raise TransientProviderError(
                provider_name=ProviderType.AWS,
                operation=operation,
                original_message=error_message,
            ) from e

        if error_code in PERMISSION_ERROR_CODES:
            operation = e.operation_name if hasattr(e, "operation_name") else None
            raise ProviderPermissionError(
                provider_name=ProviderType.AWS,
                operation=operation,
                original_message=error_message,
            ) from e

        if error_code in CREDENTIAL_ERROR_CODES:
            raise InvalidProviderCredentialsError(
                provider_name=ProviderType.AWS,
                original_message=error_message,
            ) from e

        # For other ClientErrors, re-raise
        raise
