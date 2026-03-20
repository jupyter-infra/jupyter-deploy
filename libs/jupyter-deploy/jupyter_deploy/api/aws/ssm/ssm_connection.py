from mypy_boto3_ssm.client import SSMClient
from mypy_boto3_ssm.literals import ConnectionStatusType

CONNECTION_STATUS_CONNECTED: ConnectionStatusType = "connected"
CONNECTION_STATUS_NOT_CONNECTED: ConnectionStatusType = "notconnected"


def get_connection_status(client: SSMClient, instance_id: str) -> ConnectionStatusType:
    """Call SSM:GetConnectionStatus, return the Session Manager connection status.

    Returns:
        "connected" or "notconnected"
    """
    response = client.get_connection_status(Target=instance_id)
    return response["Status"]
