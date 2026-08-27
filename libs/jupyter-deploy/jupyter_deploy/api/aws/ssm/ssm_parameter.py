from __future__ import annotations

from mypy_boto3_ssm.client import SSMClient
from mypy_boto3_ssm.type_defs import GetParameterRequestTypeDef


def get_parameter_value(ssm_client: SSMClient, name: str, with_decryption: bool = True) -> str:
    """Return the ``Value`` field of the named SSM parameter.

    ``with_decryption=True`` transparently decrypts ``SecureString`` params; harmless for
    plain ``String`` params.

    Raises:
        ValueError: if the response has no Parameter or no Value.
    """
    request: GetParameterRequestTypeDef = {"Name": name, "WithDecryption": with_decryption}
    response = ssm_client.get_parameter(**request)

    parameter = response.get("Parameter", {})
    value = parameter.get("Value")
    if not value:
        raise ValueError(f"SSM parameter '{name}' has no Value")
    return value
