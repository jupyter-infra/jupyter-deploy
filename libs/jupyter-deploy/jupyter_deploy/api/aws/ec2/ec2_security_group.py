from __future__ import annotations

from botocore.exceptions import ClientError
from mypy_boto3_ec2.client import EC2Client
from mypy_boto3_ec2.type_defs import IpPermissionTypeDef, IpRangeTypeDef

_DUPLICATE_PERMISSION_CODE = "InvalidPermission.Duplicate"


def _tcp_port_permission(cidr: str, port: int, description: str | None = None) -> IpPermissionTypeDef:
    # Only include a Description when authorizing. Revoke must match purely on CIDR — AWS's
    # RevokeSecurityGroupIngress treats a supplied Description as part of the match, so a rule
    # created with a different description (e.g. the terraform placeholder) would not be removed.
    ip_range: IpRangeTypeDef = {"CidrIp": cidr}
    if description is not None:
        ip_range["Description"] = description
    return {"IpProtocol": "tcp", "FromPort": port, "ToPort": port, "IpRanges": [ip_range]}


def _existing_cidrs_for_port(ec2_client: EC2Client, security_group_id: str, port: int) -> list[str]:
    response = ec2_client.describe_security_groups(GroupIds=[security_group_id])
    groups = response.get("SecurityGroups", [])
    if not groups:
        return []
    cidrs: list[str] = []
    for permission in groups[0].get("IpPermissions", []):
        if (
            permission.get("IpProtocol") == "tcp"
            and permission.get("FromPort") == port
            and permission.get("ToPort") == port
        ):
            cidrs.extend(r["CidrIp"] for r in permission.get("IpRanges", []) if r.get("CidrIp"))
    return cidrs


def reconcile_caller_ingress(ec2_client: EC2Client, security_group_id: str, cidr: str, port: int = 443) -> None:
    """Make ``cidr`` the sole ingress rule on ``port`` for the security group.

    Authorizes ``cidr`` if absent (tolerating a concurrent duplicate), then revokes every
    other ``port`` ingress CIDR so a stale caller IP never lingers as an open door.
    """
    existing = _existing_cidrs_for_port(ec2_client, security_group_id, port)

    if cidr not in existing:
        try:
            ec2_client.authorize_security_group_ingress(
                GroupId=security_group_id,
                IpPermissions=[_tcp_port_permission(cidr, port, description="jupyter-deploy proxy caller")],
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") != _DUPLICATE_PERMISSION_CODE:
                raise

    for stale in existing:
        if stale != cidr:
            ec2_client.revoke_security_group_ingress(
                GroupId=security_group_id, IpPermissions=[_tcp_port_permission(stale, port)]
            )
