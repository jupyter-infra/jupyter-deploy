import unittest
from typing import Any, cast

import botocore.exceptions

from jupyter_deploy.exceptions import (
    InvalidProviderCredentialsError,
    ProviderPermissionError,
    TransientProviderError,
)
from jupyter_deploy.provider.aws.aws_error_handler import aws_error_context_manager


def _client_error(
    code: str, message: str = "error", operation_name: str = "TestOp", status_code: int = 400
) -> botocore.exceptions.ClientError:
    error_response = cast(
        Any,
        {"Error": {"Code": code, "Message": message}, "ResponseMetadata": {"HTTPStatusCode": status_code}},
    )
    return botocore.exceptions.ClientError(error_response, operation_name)


class TestAwsErrorContextManager(unittest.TestCase):
    def test_no_credentials_raises_invalid_provider_credentials(self) -> None:
        with self.assertRaises(InvalidProviderCredentialsError), aws_error_context_manager():
            raise botocore.exceptions.NoCredentialsError()

    def test_partial_credentials_raises_invalid_provider_credentials(self) -> None:
        with self.assertRaises(InvalidProviderCredentialsError), aws_error_context_manager():
            raise botocore.exceptions.PartialCredentialsError(provider="test", cred_var="key")

    def test_access_denied_raises_provider_permission_error(self) -> None:
        with self.assertRaises(ProviderPermissionError), aws_error_context_manager():
            raise _client_error("AccessDenied")

    def test_expired_token_raises_invalid_provider_credentials(self) -> None:
        with self.assertRaises(InvalidProviderCredentialsError), aws_error_context_manager():
            raise _client_error("ExpiredToken")

    def test_other_client_error_reraises(self) -> None:
        with self.assertRaises(botocore.exceptions.ClientError), aws_error_context_manager():
            raise _client_error("InvalidParameterValue")

    def test_throttling_raises_transient_provider_error(self) -> None:
        with self.assertRaises(TransientProviderError), aws_error_context_manager():
            raise _client_error("ThrottlingException")

    def test_server_side_error_code_raises_transient_provider_error(self) -> None:
        with self.assertRaises(TransientProviderError), aws_error_context_manager():
            raise _client_error("ServiceUnavailable", status_code=503)

    def test_unclassified_5xx_raises_transient_provider_error(self) -> None:
        # The status code alone is enough: a 5xx is the service failing, whatever it calls the code.
        with self.assertRaises(TransientProviderError), aws_error_context_manager():
            raise _client_error("SomeUndocumentedFailure", status_code=500)

    def test_permission_error_is_not_transient_despite_status(self) -> None:
        # AccessDenied arrives as a 4xx, so the 5xx rule must not shadow the permission branch.
        with self.assertRaises(ProviderPermissionError), aws_error_context_manager():
            raise _client_error("AccessDenied", status_code=403)

    def test_endpoint_connection_error_raises_transient_provider_error(self) -> None:
        with self.assertRaises(TransientProviderError), aws_error_context_manager():
            raise botocore.exceptions.EndpointConnectionError(endpoint_url="https://ec2.us-east-1.amazonaws.com")

    def test_read_timeout_raises_transient_provider_error(self) -> None:
        with self.assertRaises(TransientProviderError), aws_error_context_manager():
            raise botocore.exceptions.ReadTimeoutError(endpoint_url="https://ec2.us-east-1.amazonaws.com")

    def test_connection_closed_raises_transient_provider_error(self) -> None:
        with self.assertRaises(TransientProviderError), aws_error_context_manager():
            raise botocore.exceptions.ConnectionClosedError(endpoint_url="https://ec2.us-east-1.amazonaws.com")

    def test_transient_error_carries_operation_and_original_message(self) -> None:
        with self.assertRaises(TransientProviderError) as ctx, aws_error_context_manager():
            raise _client_error("Throttling", message="Rate exceeded", operation_name="DescribeInstances")

        self.assertEqual(ctx.exception.operation, "DescribeInstances")
        self.assertEqual(ctx.exception.original_message, "Rate exceeded")

    def test_no_exception_passes_through(self) -> None:
        with aws_error_context_manager():
            result = 1 + 1

        self.assertEqual(result, 2)
