from mypy_boto3_ssm import SSMClient
from mypy_boto3_ssm.type_defs import DescribeInstanceInformationRequestTypeDef, InstanceInformationTypeDef


def describe_instance_information(ssm_client: SSMClient, instance_id: str) -> InstanceInformationTypeDef:
    """Call SSM:DescribeInstanceInformation, return the result."""

    request: DescribeInstanceInformationRequestTypeDef = {"Filters": [{"Key": "InstanceIds", "Values": [instance_id]}]}
    response = ssm_client.describe_instance_information(**request)
    information_list = response["InstanceInformationList"]

    if not information_list:
        raise ValueError("SSM:DescribeInstanceInformation returned an empty list")

    return information_list[0]
