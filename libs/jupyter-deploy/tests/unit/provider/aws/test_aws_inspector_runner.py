import json
import unittest
from datetime import UTC, datetime
from unittest.mock import Mock, patch

import botocore.exceptions

from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import ImageTagNotFoundError, InstructionNotFoundError
from jupyter_deploy.provider.aws.aws_inspector_runner import AwsInspectorRunner
from jupyter_deploy.provider.resolved_argdefs import ResolvedInstructionArgument, StrResolvedInstructionArgument


class _OtherException(botocore.exceptions.ClientError):
    """Distinct exception so ImageNotFoundException doesn't shadow ScanNotFoundException in except chains."""


class TestAwsInspectorRunner(unittest.TestCase):
    @patch("boto3.client")
    def test_instantiates_clients(self, mock_boto3_client: Mock) -> None:
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        AwsInspectorRunner(NullDisplay(), region_name="us-west-2")

        self.assertEqual(mock_boto3_client.call_count, 3)
        mock_boto3_client.assert_any_call("inspector2", region_name="us-west-2")
        mock_boto3_client.assert_any_call("ecr", region_name="us-west-2")
        mock_boto3_client.assert_any_call("sts", region_name="us-west-2")

    def test_raises_on_unmatched_instruction_name(self) -> None:
        runner = AwsInspectorRunner(NullDisplay(), region_name="us-west-2")

        with self.assertRaises(InstructionNotFoundError) as ctx:
            runner.execute_instruction(instruction_name="non-existent", resolved_arguments={})

        self.assertIn("non-existent", str(ctx.exception))


class TestIsInspectorEnabled(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.inspector2.inspector2_findings.is_ecr_scanning_enabled")
    def test_caches_result(self, mock_is_enabled: Mock) -> None:
        runner = AwsInspectorRunner(NullDisplay(), region_name="us-west-2")
        mock_is_enabled.return_value = True

        result1 = runner._is_inspector_enabled()
        result2 = runner._is_inspector_enabled()

        self.assertTrue(result1)
        self.assertTrue(result2)
        mock_is_enabled.assert_called_once()

    @patch("jupyter_deploy.api.aws.inspector2.inspector2_findings.is_ecr_scanning_enabled")
    def test_returns_false_when_disabled(self, mock_is_enabled: Mock) -> None:
        runner = AwsInspectorRunner(NullDisplay(), region_name="us-west-2")
        mock_is_enabled.return_value = False

        self.assertFalse(runner._is_inspector_enabled())


class TestListVulnerabilitiesInspector(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.inspector2.inspector2_findings.is_ecr_scanning_enabled")
    @patch("jupyter_deploy.api.aws.inspector2.inspector2_findings.list_image_findings")
    def test_returns_structured_vulnerabilities(self, mock_list_findings: Mock, mock_is_enabled: Mock) -> None:
        runner = AwsInspectorRunner(NullDisplay(), region_name="us-west-2")
        mock_is_enabled.return_value = True
        mock_list_findings.return_value = [
            {
                "title": "CVE-2026-1234 - openssl vulnerability",
                "severity": "CRITICAL",
                "inspectorScore": 9.8,
                "epss": {"score": 0.42},
                "lastObservedAt": datetime(2026, 6, 18, 16, 0, 0, tzinfo=UTC),
                "packageVulnerabilityDetails": {
                    "vulnerablePackages": [
                        {"name": "openssl", "version": "3.0.18", "fixedInVersion": "3.0.19", "packageManager": "OS"}
                    ],
                },
            },
            {
                "title": "CVE-2026-5678 - lodash issue",
                "severity": "HIGH",
                "inspectorScore": 7.3,
                "lastObservedAt": datetime(2026, 6, 18, 15, 0, 0, tzinfo=UTC),
                "packageVulnerabilityDetails": {
                    "vulnerablePackages": [
                        {"name": "lodash", "version": "4.17.20", "fixedInVersion": "4.18.0", "packageManager": "NODE"}
                    ],
                },
            },
        ]

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "repository_name": StrResolvedInstructionArgument(
                argument_name="repository_name", value="my-app/jupyterlab"
            ),
            "image_tag": StrResolvedInstructionArgument(argument_name="image_tag", value="v1"),
        }

        result = runner._list_vulnerabilities(resolved_arguments=resolved_args)

        vulns = json.loads(result["Vulnerabilities"].value)
        self.assertEqual(len(vulns), 2)
        self.assertEqual(vulns[0]["cve"], "CVE-2026-1234")
        self.assertEqual(vulns[0]["package"], "openssl")
        self.assertEqual(vulns[0]["type"], "OS")
        self.assertEqual(vulns[0]["score"], 9.8)
        self.assertEqual(vulns[1]["cve"], "CVE-2026-5678")
        self.assertEqual(vulns[1]["type"], "NODE")
        self.assertEqual(vulns[1]["score"], 7.3)
        # EPSS is plumbed when present and None when the finding omits it.
        self.assertEqual(vulns[0]["epss_score"], 0.42)
        self.assertIsNone(vulns[1]["epss_score"])
        self.assertEqual(result["CriticalCount"].value, "1")
        self.assertEqual(result["HighCount"].value, "1")
        self.assertEqual(result["ScannerType"].value, "Inspector Enhanced")


class TestListVulnerabilitiesEcrBasicFallback(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.inspector2.inspector2_findings.is_ecr_scanning_enabled")
    @patch("jupyter_deploy.api.aws.ecr.ecr_repository.describe_image_scan_findings")
    def test_falls_back_to_ecr_basic_when_inspector_disabled(
        self, mock_scan_findings: Mock, mock_is_enabled: Mock
    ) -> None:
        runner = AwsInspectorRunner(NullDisplay(), region_name="us-west-2")
        mock_is_enabled.return_value = False
        mock_scan_findings.return_value = (
            [
                {
                    "name": "CVE-2026-9999",
                    "severity": "HIGH",
                    "attributes": [
                        {"key": "package_name", "value": "glibc"},
                        {"key": "package_version", "value": "2.36"},
                        {"key": "CVSS3_SCORE", "value": "7.5"},
                    ],
                },
            ],
            "COMPLETE",
            "2026-06-18T15:49:33+00:00",
        )

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "repository_name": StrResolvedInstructionArgument(
                argument_name="repository_name", value="my-app/jupyterlab"
            ),
            "image_tag": StrResolvedInstructionArgument(argument_name="image_tag", value="v1"),
        }

        result = runner._list_vulnerabilities(resolved_arguments=resolved_args)

        vulns = json.loads(result["Vulnerabilities"].value)
        self.assertEqual(len(vulns), 1)
        self.assertEqual(vulns[0]["cve"], "CVE-2026-9999")
        self.assertEqual(vulns[0]["package"], "glibc")
        self.assertEqual(vulns[0]["score"], 7.5)
        self.assertIsNone(vulns[0]["epss_score"])  # ECR basic has no EPSS.
        self.assertEqual(result["ScannerType"].value, "ECR Basic")
        self.assertEqual(result["LastScanned"].value, "2026-06-18T15:49:33+00:00")

    @patch("jupyter_deploy.api.aws.inspector2.inspector2_findings.is_ecr_scanning_enabled")
    @patch("jupyter_deploy.api.aws.ecr.ecr_repository.describe_image_scan_findings")
    def test_raises_image_tag_not_found_on_ecr_exception(self, mock_scan_findings: Mock, mock_is_enabled: Mock) -> None:
        runner = AwsInspectorRunner(NullDisplay(), region_name="us-west-2")
        mock_is_enabled.return_value = False

        mock_scan_findings.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "ImageNotFoundException", "Message": "Image not found"}},
            "DescribeImageScanFindings",
        )
        runner.ecr_client.exceptions.ImageNotFoundException = botocore.exceptions.ClientError

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "repository_name": StrResolvedInstructionArgument(
                argument_name="repository_name", value="my-app/jupyterlab"
            ),
            "image_tag": StrResolvedInstructionArgument(argument_name="image_tag", value="v99"),
        }

        with self.assertRaises(ImageTagNotFoundError) as ctx:
            runner._list_vulnerabilities(resolved_arguments=resolved_args)

        self.assertEqual(ctx.exception.tag, "v99")


class TestInspectorEmptyResult(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.inspector2.inspector2_findings.is_ecr_scanning_enabled")
    @patch("jupyter_deploy.api.aws.inspector2.inspector2_findings.list_image_findings")
    @patch("jupyter_deploy.api.aws.ecr.ecr_repository.describe_image")
    @patch("jupyter_deploy.api.aws.ecr.ecr_repository.describe_image_scan_findings")
    def test_returns_clean_inspector_result_when_empty_and_tag_exists(
        self, mock_scan_findings: Mock, mock_describe_image: Mock, mock_list_findings: Mock, mock_is_enabled: Mock
    ) -> None:
        runner = AwsInspectorRunner(NullDisplay(), region_name="us-west-2")
        mock_is_enabled.return_value = True
        mock_list_findings.return_value = []
        mock_describe_image.return_value = {"imageTags": ["v1"]}

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "repository_name": StrResolvedInstructionArgument(
                argument_name="repository_name", value="my-app/jupyterlab"
            ),
            "image_tag": StrResolvedInstructionArgument(argument_name="image_tag", value="v1"),
        }

        result = runner._list_vulnerabilities(resolved_arguments=resolved_args)

        # Inspector is authoritative: empty means clean, ECR basic is NOT consulted for findings.
        mock_describe_image.assert_called_once()
        mock_scan_findings.assert_not_called()
        self.assertEqual(result["ScannerType"].value, "Inspector Enhanced")
        self.assertEqual(json.loads(result["Vulnerabilities"].value), [])

    @patch("jupyter_deploy.api.aws.inspector2.inspector2_findings.is_ecr_scanning_enabled")
    @patch("jupyter_deploy.api.aws.inspector2.inspector2_findings.list_image_findings")
    @patch("jupyter_deploy.api.aws.ecr.ecr_repository.describe_image")
    def test_raises_tag_not_found_when_inspector_empty_and_tag_missing(
        self, mock_describe_image: Mock, mock_list_findings: Mock, mock_is_enabled: Mock
    ) -> None:
        runner = AwsInspectorRunner(NullDisplay(), region_name="us-west-2")
        mock_is_enabled.return_value = True
        mock_list_findings.return_value = []

        mock_describe_image.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "ImageNotFoundException", "Message": "Image not found"}},
            "DescribeImages",
        )
        runner.ecr_client.exceptions.ImageNotFoundException = botocore.exceptions.ClientError

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "repository_name": StrResolvedInstructionArgument(
                argument_name="repository_name", value="my-app/jupyterlab"
            ),
            "image_tag": StrResolvedInstructionArgument(argument_name="image_tag", value="v99"),
        }

        with self.assertRaises(ImageTagNotFoundError) as ctx:
            runner._list_vulnerabilities(resolved_arguments=resolved_args)

        self.assertEqual(ctx.exception.tag, "v99")


class TestEcrBasicScanNotFound(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.inspector2.inspector2_findings.is_ecr_scanning_enabled")
    @patch("jupyter_deploy.api.aws.ecr.ecr_repository.describe_image_scan_findings")
    def test_returns_empty_result_when_image_never_scanned(
        self, mock_scan_findings: Mock, mock_is_enabled: Mock
    ) -> None:
        runner = AwsInspectorRunner(NullDisplay(), region_name="us-west-2")
        mock_is_enabled.return_value = False

        mock_scan_findings.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "ScanNotFoundException", "Message": "Scan not found"}},
            "DescribeImageScanFindings",
        )
        runner.ecr_client.exceptions.ImageNotFoundException = _OtherException
        runner.ecr_client.exceptions.ScanNotFoundException = botocore.exceptions.ClientError

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "repository_name": StrResolvedInstructionArgument(
                argument_name="repository_name", value="my-app/jupyterlab"
            ),
            "image_tag": StrResolvedInstructionArgument(argument_name="image_tag", value="v1"),
        }

        result = runner._list_vulnerabilities(resolved_arguments=resolved_args)

        self.assertEqual(result["ScannerType"].value, "ECR Basic")
        self.assertEqual(json.loads(result["Vulnerabilities"].value), [])
        self.assertEqual(result["CriticalCount"].value, "0")
        self.assertEqual(result["HighCount"].value, "0")
        self.assertEqual(result["LastScanned"].value, "")


class TestGetScanStatus(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.inspector2.inspector2_findings.is_ecr_scanning_enabled")
    @patch("jupyter_deploy.api.aws.inspector2.inspector2_findings.list_image_findings")
    def test_returns_active_when_inspector_has_findings(self, mock_list_findings: Mock, mock_is_enabled: Mock) -> None:
        runner = AwsInspectorRunner(NullDisplay(), region_name="us-west-2")
        mock_is_enabled.return_value = True
        mock_list_findings.return_value = [
            {"lastObservedAt": datetime(2026, 6, 18, 16, 0, 0, tzinfo=UTC)},
        ]

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "repository_name": StrResolvedInstructionArgument(
                argument_name="repository_name", value="my-app/jupyterlab"
            ),
            "image_tag": StrResolvedInstructionArgument(argument_name="image_tag", value="v1"),
        }

        result = runner._get_scan_status(resolved_arguments=resolved_args)

        self.assertEqual(result["ScannerType"].value, "Inspector Enhanced")
        self.assertEqual(result["ScanStatus"].value, "ACTIVE")
        self.assertIn("2026-06-18", result["LastScanned"].value)

    @patch("jupyter_deploy.api.aws.inspector2.inspector2_findings.is_ecr_scanning_enabled")
    @patch("jupyter_deploy.api.aws.ecr.ecr_repository.describe_image_scan_findings")
    def test_falls_back_to_ecr_basic_when_inspector_disabled(
        self, mock_scan_findings: Mock, mock_is_enabled: Mock
    ) -> None:
        runner = AwsInspectorRunner(NullDisplay(), region_name="us-west-2")
        mock_is_enabled.return_value = False
        mock_scan_findings.return_value = ([], "COMPLETE", "2026-06-18T15:49:33+00:00")

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "repository_name": StrResolvedInstructionArgument(
                argument_name="repository_name", value="my-app/jupyterlab"
            ),
            "image_tag": StrResolvedInstructionArgument(argument_name="image_tag", value="v1"),
        }

        result = runner._get_scan_status(resolved_arguments=resolved_args)

        self.assertEqual(result["ScannerType"].value, "ECR Basic")
        self.assertEqual(result["ScanStatus"].value, "COMPLETE")
        self.assertEqual(result["LastScanned"].value, "2026-06-18T15:49:33+00:00")
