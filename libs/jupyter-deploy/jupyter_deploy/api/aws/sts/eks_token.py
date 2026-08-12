from __future__ import annotations

import base64

from botocore.auth import SigV4QueryAuth
from botocore.awsrequest import AWSRequest
from botocore.session import Session as BotocoreSession

from jupyter_deploy.enum import ProviderType
from jupyter_deploy.exceptions import InvalidProviderCredentialsError

_TOKEN_PREFIX = "k8s-aws-v1."
_TOKEN_EXPIRY_SECONDS = 60
_CLUSTER_ID_HEADER = "x-k8s-aws-id"
_STS_ACTION = "Action=GetCallerIdentity&Version=2011-06-15"


def get_eks_bearer_token(cluster_name: str, region: str) -> str:
    """Generate an EKS bearer token using a presigned STS GetCallerIdentity URL.

    Uses the default credential chain (env vars, profile, IMDS, etc.).
    """
    session = BotocoreSession()
    credentials = session.get_credentials()
    if credentials is None:
        raise InvalidProviderCredentialsError(
            ProviderType.AWS, "no AWS credentials found in the default credential chain"
        )
    frozen_credentials = credentials.get_frozen_credentials()

    endpoint = f"https://sts.{region}.amazonaws.com/?{_STS_ACTION}"
    request = AWSRequest(method="GET", url=endpoint, headers={_CLUSTER_ID_HEADER: cluster_name})

    signer = SigV4QueryAuth(frozen_credentials, "sts", region, expires=_TOKEN_EXPIRY_SECONDS)
    signer.add_auth(request)

    signed_url: str = request.url  # type: ignore[assignment]
    token_body = base64.urlsafe_b64encode(signed_url.encode("utf-8")).rstrip(b"=").decode("utf-8")
    return f"{_TOKEN_PREFIX}{token_body}"
