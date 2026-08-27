from __future__ import annotations

import base64

from botocore.auth import SigV4QueryAuth
from botocore.awsrequest import AWSRequest
from botocore.session import Session as BotocoreSession

from jupyter_deploy.enum import ProviderType
from jupyter_deploy.exceptions import InvalidProviderCredentialsError

TOKEN_PREFIX = "k8s-aws-v1."
BINDING_HEADER_NAME = "x-k8s-aws-id"
DEFAULT_TOKEN_EXPIRY_SECONDS = 60
_STS_ACTION = "Action=GetCallerIdentity&Version=2011-06-15"


def get_eks_bearer_token(binding_id: str, region: str, expires_in_seconds: int = DEFAULT_TOKEN_EXPIRY_SECONDS) -> str:
    """Generate a k8s-aws-v1 bearer token using a presigned STS GetCallerIdentity URL.

    The ``binding_id`` is echoed in the ``x-k8s-aws-id`` header at signing time, so a token
    minted for one deployment cannot be replayed against another — the STS-side signature
    verification fails without matching the exact header value. EKS uses this construct to
    bind tokens to a cluster; the ``jd proxy`` template reuses it to bind tokens to a
    deployment. Uses the default credential chain (env vars, profile, IMDS, etc.).

    Args:
        binding_id: The opaque identifier signed into the ``x-k8s-aws-id`` header. For EKS
            this is the cluster name; for the jupyterlab template it is the deployment ID.
        region: AWS region for the regional STS endpoint.
        expires_in_seconds: Presigned-URL lifetime; also the token's usable window.
    """
    session = BotocoreSession()
    credentials = session.get_credentials()
    if credentials is None:
        raise InvalidProviderCredentialsError(
            ProviderType.AWS, "no AWS credentials found in the default credential chain"
        )
    frozen_credentials = credentials.get_frozen_credentials()

    endpoint = f"https://sts.{region}.amazonaws.com/?{_STS_ACTION}"
    request = AWSRequest(method="GET", url=endpoint, headers={BINDING_HEADER_NAME: binding_id})

    signer = SigV4QueryAuth(frozen_credentials, "sts", region, expires=expires_in_seconds)
    signer.add_auth(request)

    signed_url: str = request.url  # type: ignore[assignment]
    token_body = base64.urlsafe_b64encode(signed_url.encode("utf-8")).rstrip(b"=").decode("utf-8")
    return f"{TOKEN_PREFIX}{token_body}"
