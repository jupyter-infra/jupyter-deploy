from mypy_boto3_inspector2.client import Inspector2Client
from mypy_boto3_inspector2.type_defs import FilterCriteriaTypeDef, FindingTypeDef, StringFilterTypeDef
from mypy_boto3_sts.client import STSClient

from jupyter_deploy.api.aws.sts import sts_identity


def is_ecr_scanning_enabled(client: Inspector2Client, sts_client: STSClient) -> bool:
    """Return True if Inspector2 ECR scanning is enabled for the caller's account."""
    account_id = sts_identity.get_caller_account(sts_client)
    response = client.batch_get_account_status(accountIds=[account_id])
    for account in response.get("accounts", []):
        resource_state = account.get("resourceState", {})
        ecr_state = resource_state.get("ecr", {})
        status = ecr_state.get("status", "")
        if status == "ENABLED":
            return True
    return False


def list_image_findings(
    client: Inspector2Client,
    repository_name: str,
    image_tag: str,
    severity_filter: list[str] | None = None,
) -> list[FindingTypeDef]:
    """Call Inspector2:ListFindings filtered by ECR image and return all findings."""
    filter_criteria: FilterCriteriaTypeDef = {
        "ecrImageRepositoryName": [StringFilterTypeDef(comparison="EQUALS", value=repository_name)],
        "ecrImageTags": [StringFilterTypeDef(comparison="EQUALS", value=image_tag)],
    }
    if severity_filter:
        filter_criteria["severity"] = [StringFilterTypeDef(comparison="EQUALS", value=s) for s in severity_filter]

    findings: list[FindingTypeDef] = []
    paginator = client.get_paginator("list_findings")
    for page in paginator.paginate(filterCriteria=filter_criteria):
        findings.extend(page.get("findings", []))
    return findings
