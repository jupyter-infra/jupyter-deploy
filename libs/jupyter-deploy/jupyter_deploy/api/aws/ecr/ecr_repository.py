from mypy_boto3_ecr.client import ECRClient
from mypy_boto3_ecr.type_defs import ImageDetailTypeDef, ImageScanFindingTypeDef, RepositoryTypeDef


def describe_repository(client: ECRClient, repository_name: str) -> RepositoryTypeDef:
    """Call ECR:DescribeRepositories and return the repository details."""
    response = client.describe_repositories(repositoryNames=[repository_name])
    return response["repositories"][0]


def list_image_tags(client: ECRClient, repository_name: str) -> list[ImageDetailTypeDef]:
    """Call ECR:DescribeImages and return tagged image details."""
    response = client.describe_images(
        repositoryName=repository_name,
        filter={"tagStatus": "TAGGED"},
    )
    return response.get("imageDetails", [])


def describe_image(client: ECRClient, repository_name: str, image_tag: str) -> ImageDetailTypeDef:
    """Call ECR:DescribeImages for a single tag and return its detail.

    Raises ECR's ImageNotFoundException if the tag does not exist in the repository.
    """
    response = client.describe_images(
        repositoryName=repository_name,
        imageIds=[{"imageTag": image_tag}],
    )
    return response["imageDetails"][0]


def describe_image_scan_findings(
    client: ECRClient, repository_name: str, image_tag: str
) -> tuple[list[ImageScanFindingTypeDef], str, str]:
    """Call ECR:DescribeImageScanFindings and return findings, scan status, and completion time."""
    response = client.describe_image_scan_findings(
        repositoryName=repository_name,
        imageId={"imageTag": image_tag},
    )
    scan_status = response.get("imageScanStatus", {}).get("status", "UNKNOWN")
    scan_findings = response.get("imageScanFindings", {})
    findings = scan_findings.get("findings", [])
    completed_at = scan_findings.get("imageScanCompletedAt")
    completed_str = completed_at.isoformat() if completed_at else ""
    return findings, scan_status, completed_str
