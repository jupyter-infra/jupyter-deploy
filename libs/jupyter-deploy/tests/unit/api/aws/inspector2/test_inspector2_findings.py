import unittest
from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock

import botocore.exceptions
from mypy_boto3_inspector2.client import Inspector2Client

from jupyter_deploy.api.aws.inspector2 import inspector2_findings


class TestIsEcrScanningEnabled(unittest.TestCase):
    def test_returns_true_when_ecr_enabled(self) -> None:
        mock_inspector: Mock = Mock(spec=Inspector2Client)
        mock_inspector.batch_get_account_status.return_value = {
            "accounts": [
                {
                    "accountId": "123456789012",
                    "resourceState": {
                        "ecr": {"status": "ENABLED"},
                        "ec2": {"status": "DISABLED"},
                    },
                }
            ]
        }
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}

        result = inspector2_findings.is_ecr_scanning_enabled(mock_inspector, mock_sts)

        self.assertTrue(result)

    def test_returns_false_when_ecr_disabled(self) -> None:
        mock_inspector: Mock = Mock(spec=Inspector2Client)
        mock_inspector.batch_get_account_status.return_value = {
            "accounts": [
                {
                    "accountId": "123456789012",
                    "resourceState": {
                        "ecr": {"status": "DISABLED"},
                    },
                }
            ]
        }
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}

        result = inspector2_findings.is_ecr_scanning_enabled(mock_inspector, mock_sts)

        self.assertFalse(result)

    def test_returns_false_when_no_accounts(self) -> None:
        mock_inspector: Mock = Mock(spec=Inspector2Client)
        mock_inspector.batch_get_account_status.return_value = {"accounts": []}
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}

        result = inspector2_findings.is_ecr_scanning_enabled(mock_inspector, mock_sts)

        self.assertFalse(result)

    def test_raises_on_client_error(self) -> None:
        mock_inspector: Mock = Mock(spec=Inspector2Client)
        mock_inspector.batch_get_account_status.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
            "BatchGetAccountStatus",
        )
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}

        with self.assertRaises(botocore.exceptions.ClientError):
            inspector2_findings.is_ecr_scanning_enabled(mock_inspector, mock_sts)


class TestListImageFindings(unittest.TestCase):
    def test_returns_findings_for_image(self) -> None:
        mock_client: Mock = Mock(spec=Inspector2Client)
        finding: dict[str, Any] = {
            "title": "CVE-2026-12345 - openssl",
            "severity": "HIGH",
            "findingArn": "arn:aws:inspector2:us-west-2:123:finding/abc",
            "status": "ACTIVE",
            "type": "PACKAGE_VULNERABILITY",
            "lastObservedAt": datetime(2026, 6, 18, 16, 0, 0, tzinfo=UTC),
            "packageVulnerabilityDetails": {
                "vulnerablePackages": [{"name": "openssl", "version": "3.0.18", "fixedInVersion": "3.0.19"}],
            },
        }
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"findings": [finding]}]
        mock_client.get_paginator.return_value = mock_paginator

        result = inspector2_findings.list_image_findings(
            mock_client, repository_name="my-app/jupyterlab", image_tag="v1"
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "CVE-2026-12345 - openssl")
        self.assertEqual(result[0]["severity"], "HIGH")
        mock_client.get_paginator.assert_called_once_with("list_findings")

    def test_passes_severity_filter(self) -> None:
        mock_client: Mock = Mock(spec=Inspector2Client)
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"findings": []}]
        mock_client.get_paginator.return_value = mock_paginator

        inspector2_findings.list_image_findings(
            mock_client,
            repository_name="my-app/jupyterlab",
            image_tag="v1",
            severity_filter=["CRITICAL", "HIGH"],
        )

        call_kwargs = mock_paginator.paginate.call_args[1]
        severity_filters = call_kwargs["filterCriteria"]["severity"]
        self.assertEqual(len(severity_filters), 2)
        self.assertEqual(severity_filters[0]["value"], "CRITICAL")
        self.assertEqual(severity_filters[1]["value"], "HIGH")

    def test_returns_empty_when_no_findings(self) -> None:
        mock_client: Mock = Mock(spec=Inspector2Client)
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"findings": []}]
        mock_client.get_paginator.return_value = mock_paginator

        result = inspector2_findings.list_image_findings(
            mock_client, repository_name="my-app/jupyterlab", image_tag="v1"
        )

        self.assertEqual(result, [])

    def test_paginates_across_multiple_pages(self) -> None:
        mock_client: Mock = Mock(spec=Inspector2Client)
        finding1: dict[str, Any] = {
            "title": "CVE-1",
            "severity": "HIGH",
            "findingArn": "arn:1",
            "status": "ACTIVE",
            "type": "PACKAGE_VULNERABILITY",
        }
        finding2: dict[str, Any] = {
            "title": "CVE-2",
            "severity": "CRITICAL",
            "findingArn": "arn:2",
            "status": "ACTIVE",
            "type": "PACKAGE_VULNERABILITY",
        }
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {"findings": [finding1]},
            {"findings": [finding2]},
        ]
        mock_client.get_paginator.return_value = mock_paginator

        result = inspector2_findings.list_image_findings(
            mock_client, repository_name="my-app/jupyterlab", image_tag="v1"
        )

        self.assertEqual(len(result), 2)

    def test_raises_on_client_error(self) -> None:
        mock_client: Mock = Mock(spec=Inspector2Client)
        mock_paginator = Mock()
        mock_paginator.paginate.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
            "ListFindings",
        )
        mock_client.get_paginator.return_value = mock_paginator

        with self.assertRaises(botocore.exceptions.ClientError):
            inspector2_findings.list_image_findings(mock_client, repository_name="my-app/jupyterlab", image_tag="v1")
