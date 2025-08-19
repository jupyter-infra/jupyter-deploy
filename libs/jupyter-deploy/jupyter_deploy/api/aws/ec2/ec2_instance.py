from mypy_boto3_ec2.client import EC2Client
from mypy_boto3_ec2.type_defs import DescribeInstanceStatusRequestTypeDef, DescribeInstanceStatusResultTypeDef


def describe_instance_status(ec2_client: EC2Client, instance_id: str) -> DescribeInstanceStatusResultTypeDef:
    """Call EC2:DescribeInstanceStatus, return the result."""

    request: DescribeInstanceStatusRequestTypeDef = {"InstanceIds": [instance_id]}
    response = ec2_client.describe_instance_status(**request)
    return response
