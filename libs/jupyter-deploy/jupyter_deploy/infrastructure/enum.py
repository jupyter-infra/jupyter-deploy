from enum import Enum


class AWSInfrastructureType(str, Enum):
    """Enum to list the types of AWS infrastructure."""

    EC2 = "ec2"
    IAM = "iam"


# Use the AWS infrastructure type as the default infrastructure type for now
# When more provider-specific infrastructure types are added, we can update this
# to use a Union type or create a new enum that includes all values from all provider-specific enums
InfrastructureType = AWSInfrastructureType
