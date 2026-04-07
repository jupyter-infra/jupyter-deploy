from mypy_boto3_secretsmanager.client import SecretsManagerClient
from mypy_boto3_secretsmanager.type_defs import GetSecretValueResponseTypeDef


def get_secret_value(
    client: SecretsManagerClient,
    secret_id: str,
) -> GetSecretValueResponseTypeDef:
    """Call SecretsManager:GetSecretValue and return the response."""
    return client.get_secret_value(SecretId=secret_id)
