import unittest
from datetime import UTC, datetime
from unittest.mock import Mock

import botocore.exceptions
from mypy_boto3_ecr.client import ECRClient
from mypy_boto3_ecr.type_defs import ImageDetailTypeDef, ImageScanFindingTypeDef, RepositoryTypeDef

from jupyter_deploy.api.aws.ecr import ecr_repository


class TestDescribeRepository(unittest.TestCase):
    def test_returns_repository_details(self) -> None:
        mock_client: Mock = Mock(spec=ECRClient)
        repo: RepositoryTypeDef = {
            "repositoryName": "my-app/jupyterlab",
            "repositoryUri": "123456.dkr.ecr.us-west-2.amazonaws.com/my-app/jupyterlab",
            "repositoryArn": "arn:aws:ecr:us-west-2:123456:repository/my-app/jupyterlab",
        }
        mock_client.describe_repositories.return_value = {"repositories": [repo]}

        result = ecr_repository.describe_repository(mock_client, repository_name="my-app/jupyterlab")

        self.assertEqual(result["repositoryName"], "my-app/jupyterlab")
        self.assertEqual(result["repositoryUri"], "123456.dkr.ecr.us-west-2.amazonaws.com/my-app/jupyterlab")
        mock_client.describe_repositories.assert_called_once_with(repositoryNames=["my-app/jupyterlab"])

    def test_raises_on_repository_not_found(self) -> None:
        mock_client: Mock = Mock(spec=ECRClient)
        mock_client.describe_repositories.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "RepositoryNotFoundException", "Message": "Repository not found"}},
            "DescribeRepositories",
        )

        with self.assertRaises(botocore.exceptions.ClientError):
            ecr_repository.describe_repository(mock_client, repository_name="nonexistent")


class TestListImageTags(unittest.TestCase):
    def test_returns_tagged_images(self) -> None:
        mock_client: Mock = Mock(spec=ECRClient)
        pushed_at = datetime(2026, 6, 18, 15, 49, 0, tzinfo=UTC)
        image_detail: ImageDetailTypeDef = {
            "imageTags": ["v1", "latest"],
            "imageDigest": "sha256:abc123",
            "imagePushedAt": pushed_at,
        }
        mock_client.describe_images.return_value = {"imageDetails": [image_detail]}

        result = ecr_repository.list_image_tags(mock_client, repository_name="my-app/jupyterlab")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["imageTags"], ["v1", "latest"])
        self.assertEqual(result[0]["imageDigest"], "sha256:abc123")
        mock_client.describe_images.assert_called_once_with(
            repositoryName="my-app/jupyterlab",
            filter={"tagStatus": "TAGGED"},
        )

    def test_returns_empty_list_when_no_images(self) -> None:
        mock_client: Mock = Mock(spec=ECRClient)
        mock_client.describe_images.return_value = {"imageDetails": []}

        result = ecr_repository.list_image_tags(mock_client, repository_name="my-app/jupyterlab")

        self.assertEqual(result, [])

    def test_raises_on_repository_not_found(self) -> None:
        mock_client: Mock = Mock(spec=ECRClient)
        mock_client.describe_images.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "RepositoryNotFoundException", "Message": "Repository not found"}},
            "DescribeImages",
        )

        with self.assertRaises(botocore.exceptions.ClientError):
            ecr_repository.list_image_tags(mock_client, repository_name="nonexistent")


class TestDescribeImage(unittest.TestCase):
    def test_returns_image_detail_for_tag(self) -> None:
        mock_client: Mock = Mock(spec=ECRClient)
        image_detail: ImageDetailTypeDef = {
            "imageTags": ["v1"],
            "imageDigest": "sha256:abc123",
        }
        mock_client.describe_images.return_value = {"imageDetails": [image_detail]}

        result = ecr_repository.describe_image(mock_client, repository_name="my-app/jupyterlab", image_tag="v1")

        self.assertEqual(result["imageTags"], ["v1"])
        mock_client.describe_images.assert_called_once_with(
            repositoryName="my-app/jupyterlab",
            imageIds=[{"imageTag": "v1"}],
        )

    def test_raises_on_image_not_found(self) -> None:
        mock_client: Mock = Mock(spec=ECRClient)
        mock_client.describe_images.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "ImageNotFoundException", "Message": "Image not found"}},
            "DescribeImages",
        )

        with self.assertRaises(botocore.exceptions.ClientError):
            ecr_repository.describe_image(mock_client, repository_name="my-app/jupyterlab", image_tag="v99")

    def test_bubbles_up_other_client_error(self) -> None:
        mock_client: Mock = Mock(spec=ECRClient)
        mock_client.describe_images.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "RepositoryNotFoundException", "Message": "Repository not found"}},
            "DescribeImages",
        )

        with self.assertRaises(botocore.exceptions.ClientError) as ctx:
            ecr_repository.describe_image(mock_client, repository_name="nonexistent", image_tag="v1")

        self.assertEqual(ctx.exception.response["Error"]["Code"], "RepositoryNotFoundException")


class TestDescribeImageScanFindings(unittest.TestCase):
    def test_returns_findings_and_status(self) -> None:
        mock_client: Mock = Mock(spec=ECRClient)
        completed_at = datetime(2026, 6, 18, 15, 49, 33, tzinfo=UTC)
        finding: ImageScanFindingTypeDef = {
            "name": "CVE-2026-12345",
            "severity": "HIGH",
            "attributes": [
                {"key": "package_name", "value": "openssl"},
                {"key": "package_version", "value": "3.0.18"},
                {"key": "CVSS3_SCORE", "value": "7.5"},
            ],
        }
        mock_client.describe_image_scan_findings.return_value = {
            "imageScanStatus": {"status": "COMPLETE"},
            "imageScanFindings": {
                "findings": [finding],
                "imageScanCompletedAt": completed_at,
            },
        }

        findings, status, completed_str = ecr_repository.describe_image_scan_findings(
            mock_client, repository_name="my-app/jupyterlab", image_tag="v1"
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["name"], "CVE-2026-12345")
        self.assertEqual(status, "COMPLETE")
        self.assertEqual(completed_str, "2026-06-18T15:49:33+00:00")
        mock_client.describe_image_scan_findings.assert_called_once_with(
            repositoryName="my-app/jupyterlab",
            imageId={"imageTag": "v1"},
        )

    def test_returns_empty_findings_when_none(self) -> None:
        mock_client: Mock = Mock(spec=ECRClient)
        mock_client.describe_image_scan_findings.return_value = {
            "imageScanStatus": {"status": "COMPLETE"},
            "imageScanFindings": {
                "findings": [],
            },
        }

        findings, status, completed_str = ecr_repository.describe_image_scan_findings(
            mock_client, repository_name="my-app/jupyterlab", image_tag="v1"
        )

        self.assertEqual(findings, [])
        self.assertEqual(status, "COMPLETE")
        self.assertEqual(completed_str, "")

    def test_returns_unknown_status_when_missing(self) -> None:
        mock_client: Mock = Mock(spec=ECRClient)
        mock_client.describe_image_scan_findings.return_value = {
            "imageScanFindings": {"findings": []},
        }

        findings, status, completed_str = ecr_repository.describe_image_scan_findings(
            mock_client, repository_name="my-app/jupyterlab", image_tag="v1"
        )

        self.assertEqual(status, "UNKNOWN")

    def test_raises_on_image_not_found(self) -> None:
        mock_client: Mock = Mock(spec=ECRClient)
        mock_client.describe_image_scan_findings.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "ImageNotFoundException", "Message": "Image not found"}},
            "DescribeImageScanFindings",
        )

        with self.assertRaises(botocore.exceptions.ClientError):
            ecr_repository.describe_image_scan_findings(
                mock_client, repository_name="my-app/jupyterlab", image_tag="v99"
            )
