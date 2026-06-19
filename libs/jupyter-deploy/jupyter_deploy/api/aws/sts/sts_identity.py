from __future__ import annotations

from mypy_boto3_sts.client import STSClient

from jupyter_deploy.exceptions import UnsupportedProviderRegionError

PARTITION_LEAD_REGIONS: dict[str, str] = {
    "aws": "us-east-1",
    "aws-cn": "cn-north-1",
    "aws-us-gov": "us-gov-west-1",
}


def get_caller_arn(sts_client: STSClient) -> str:
    """Return the ARN of the caller's identity via STS:GetCallerIdentity."""
    identity = sts_client.get_caller_identity()
    return identity["Arn"]


def get_caller_account(sts_client: STSClient) -> str:
    """Return the AWS account ID of the caller's identity via STS:GetCallerIdentity."""
    return sts_client.get_caller_identity()["Account"]


def get_partition(sts_client: STSClient) -> str:
    """Return the AWS partition of the caller's identity.

    Calls STS:GetCallerIdentity and extracts the partition from the ARN.
    """
    return get_caller_arn(sts_client).split(":")[1]


def get_partition_lead_region(sts_client: STSClient) -> str:
    """Return the lead region for the caller's AWS partition.

    Raises:
        UnsupportedProviderRegionError: If the partition is not recognized.
    """
    partition = get_partition(sts_client)
    if partition not in PARTITION_LEAD_REGIONS:
        supported = ", ".join(PARTITION_LEAD_REGIONS.keys())
        raise UnsupportedProviderRegionError(
            partition,
            hint=f"Use credentials from one of the supported AWS partitions: {supported}",
        )
    return PARTITION_LEAD_REGIONS[partition]
