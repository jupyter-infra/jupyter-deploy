import json
from enum import Enum

import boto3
from mypy_boto3_ecr.client import ECRClient
from mypy_boto3_inspector2.client import Inspector2Client
from mypy_boto3_sts.client import STSClient

from jupyter_deploy.api.aws.ecr import ecr_repository
from jupyter_deploy.api.aws.inspector2 import inspector2_findings
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.exceptions import ImageTagNotFoundError, InstructionNotFoundError
from jupyter_deploy.provider.instruction_runner import InstructionRunner
from jupyter_deploy.provider.resolved_argdefs import (
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
)
from jupyter_deploy.provider.resolved_resultdefs import (
    ResolvedInstructionResult,
    StrResolvedInstructionResult,
)


class AwsInspectorInstruction(str, Enum):
    """AWS Inspector2 instructions accessible from manifest.commands[].sequence[].api-name."""

    LIST_VULNERABILITIES = "list-vulnerabilities"
    GET_SCAN_STATUS = "get-scan-status"


class AwsInspectorRunner(InstructionRunner):
    """Runner for image vulnerability scanning.

    Auto-detects whether Inspector2 Enhanced scanning is enabled for the account.
    If enabled, reads from Inspector2 (OS + pip packages, EPSS, continuous re-scan).
    If not, falls back to ECR basic scan findings (OS packages only, push-time).
    """

    def __init__(self, display_manager: DisplayManager, region_name: str | None) -> None:
        super().__init__(display_manager)
        self.region_name = region_name
        self.inspector_client: Inspector2Client = boto3.client("inspector2", region_name=region_name)
        self.ecr_client: ECRClient = boto3.client("ecr", region_name=region_name)
        self._sts_client: STSClient = boto3.client("sts", region_name=region_name)
        self._inspector_enabled: bool | None = None

    def _is_inspector_enabled(self) -> bool:
        if self._inspector_enabled is not None:
            return self._inspector_enabled
        self._inspector_enabled = inspector2_findings.is_ecr_scanning_enabled(self.inspector_client, self._sts_client)
        return self._inspector_enabled

    def _list_vulnerabilities_inspector(
        self, repository_name: str, image_tag: str
    ) -> dict[str, ResolvedInstructionResult]:
        findings = inspector2_findings.list_image_findings(
            self.inspector_client,
            repository_name=repository_name,
            image_tag=image_tag,
            severity_filter=["CRITICAL", "HIGH"],
        )

        vulnerabilities: list[dict] = []
        last_scanned = ""
        critical_count = 0
        high_count = 0

        for finding in findings:
            severity = finding.get("severity", "")
            if severity == "CRITICAL":
                critical_count += 1
            elif severity == "HIGH":
                high_count += 1

            last_observed = finding.get("lastObservedAt")
            if last_observed:
                iso = last_observed.isoformat()
                if not last_scanned or iso > last_scanned:
                    last_scanned = iso

            vuln_details = finding.get("packageVulnerabilityDetails", {})
            vulnerable_packages = vuln_details.get("vulnerablePackages", [])
            package_name = vulnerable_packages[0].get("name", "") if vulnerable_packages else ""
            installed_version = vulnerable_packages[0].get("version", "") if vulnerable_packages else ""
            fixed_version = vulnerable_packages[0].get("fixedInVersion", "") if vulnerable_packages else ""

            score = finding.get("inspectorScore", 0.0)
            package_manager = vulnerable_packages[0].get("packageManager", "") if vulnerable_packages else ""

            # EPSS (Exploit Prediction Scoring System) probability, 0.0-1.0; absent on some findings.
            epss_details = finding.get("epss") or {}
            epss_score = epss_details.get("score")

            raw_title = finding.get("title", "")
            cve = raw_title.split(" - ")[0].strip() if " - " in raw_title else raw_title

            vulnerabilities.append(
                {
                    "cve": cve,
                    "type": package_manager,
                    "package": package_name,
                    "severity": severity,
                    "installed_version": installed_version,
                    "fixed_version": fixed_version,
                    "score": score,
                    "epss_score": epss_score,
                }
            )

        vulnerabilities.sort(key=lambda v: v["score"], reverse=True)

        return {
            "Vulnerabilities": StrResolvedInstructionResult(
                result_name="Vulnerabilities", value=json.dumps(vulnerabilities)
            ),
            "LastScanned": StrResolvedInstructionResult(result_name="LastScanned", value=last_scanned),
            "CriticalCount": StrResolvedInstructionResult(result_name="CriticalCount", value=str(critical_count)),
            "HighCount": StrResolvedInstructionResult(result_name="HighCount", value=str(high_count)),
            "ScannerType": StrResolvedInstructionResult(result_name="ScannerType", value="Inspector Enhanced"),
        }

    def _list_vulnerabilities_ecr_basic(
        self, repository_name: str, image_tag: str
    ) -> dict[str, ResolvedInstructionResult]:
        findings, _, completed_at = ecr_repository.describe_image_scan_findings(
            self.ecr_client, repository_name=repository_name, image_tag=image_tag
        )

        vulnerabilities: list[dict] = []
        critical_count = 0
        high_count = 0

        for finding in findings:
            severity = finding.get("severity", "")
            if severity not in ("CRITICAL", "HIGH"):
                continue
            if severity == "CRITICAL":
                critical_count += 1
            elif severity == "HIGH":
                high_count += 1

            cve = finding.get("name", "")
            attrs = {a["key"]: a["value"] for a in finding.get("attributes", []) if "key" in a and "value" in a}
            package_name = attrs.get("package_name", "")
            installed_version = attrs.get("package_version", "")
            fixed_version = ""
            score = float(attrs.get("CVSS3_SCORE", "0") or "0")

            vulnerabilities.append(
                {
                    "cve": cve,
                    "type": "OS",
                    "package": package_name,
                    "severity": severity,
                    "installed_version": installed_version,
                    "fixed_version": fixed_version,
                    "score": score,
                    "epss_score": None,  # ECR basic scanning does not provide EPSS.
                }
            )

        vulnerabilities.sort(key=lambda v: v["score"], reverse=True)

        return {
            "Vulnerabilities": StrResolvedInstructionResult(
                result_name="Vulnerabilities", value=json.dumps(vulnerabilities)
            ),
            "LastScanned": StrResolvedInstructionResult(result_name="LastScanned", value=completed_at),
            "CriticalCount": StrResolvedInstructionResult(result_name="CriticalCount", value=str(critical_count)),
            "HighCount": StrResolvedInstructionResult(result_name="HighCount", value=str(high_count)),
            "ScannerType": StrResolvedInstructionResult(result_name="ScannerType", value="ECR Basic"),
        }

    def _verify_tag_exists(self, repository_name: str, image_tag: str) -> None:
        """Confirm the image tag exists in ECR, raising ImageTagNotFoundError otherwise."""
        try:
            ecr_repository.describe_image(self.ecr_client, repository_name=repository_name, image_tag=image_tag)
        except self.ecr_client.exceptions.ImageNotFoundException:
            raise ImageTagNotFoundError(repository_name, image_tag) from None

    @staticmethod
    def _empty_ecr_basic_result() -> dict[str, ResolvedInstructionResult]:
        """Return an empty ECR basic vulnerability result for un-scanned images."""
        return {
            "Vulnerabilities": StrResolvedInstructionResult(result_name="Vulnerabilities", value=json.dumps([])),
            "LastScanned": StrResolvedInstructionResult(result_name="LastScanned", value=""),
            "CriticalCount": StrResolvedInstructionResult(result_name="CriticalCount", value="0"),
            "HighCount": StrResolvedInstructionResult(result_name="HighCount", value="0"),
            "ScannerType": StrResolvedInstructionResult(result_name="ScannerType", value="ECR Basic"),
        }

    def _list_vulnerabilities(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        repository_name_arg = require_arg(resolved_arguments, "repository_name", StrResolvedInstructionArgument)
        image_tag_arg = require_arg(resolved_arguments, "image_tag", StrResolvedInstructionArgument)
        repository_name = repository_name_arg.value
        image_tag = image_tag_arg.value

        if self._is_inspector_enabled():
            self.display_manager.info(f"Reading Inspector findings for {repository_name}:{image_tag}")
            result = self._list_vulnerabilities_inspector(repository_name, image_tag)
            if not json.loads(result["Vulnerabilities"].value):
                # Inspector is authoritative: zero findings means clean (continuous re-scan).
                # Validate the tag exists rather than falling back to stale ECR basic findings.
                self.display_manager.info(f"No Inspector findings, verifying tag exists: {repository_name}:{image_tag}")
                self._verify_tag_exists(repository_name, image_tag)
            return result

        try:
            self.display_manager.info(f"Reading ECR scan findings for {repository_name}:{image_tag}")
            return self._list_vulnerabilities_ecr_basic(repository_name, image_tag)
        except self.ecr_client.exceptions.ImageNotFoundException:
            raise ImageTagNotFoundError(repository_name, image_tag) from None
        except self.ecr_client.exceptions.ScanNotFoundException:
            # Image exists but was never scanned (scan-on-push disabled or image predates scanning).
            self.display_manager.warning(
                f"No scan results for {repository_name}:{image_tag} — enable scan-on-push or trigger a manual scan."
            )
            return self._empty_ecr_basic_result()

    def _get_scan_status(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        repository_name_arg = require_arg(resolved_arguments, "repository_name", StrResolvedInstructionArgument)
        image_tag_arg = require_arg(resolved_arguments, "image_tag", StrResolvedInstructionArgument)

        if self._is_inspector_enabled():
            findings = inspector2_findings.list_image_findings(
                self.inspector_client,
                repository_name=repository_name_arg.value,
                image_tag=image_tag_arg.value,
            )
            if findings:
                last_observed = findings[0].get("lastObservedAt")
                last_scanned = last_observed.isoformat() if last_observed else ""
                return {
                    "ScannerType": StrResolvedInstructionResult(result_name="ScannerType", value="Inspector Enhanced"),
                    "LastScanned": StrResolvedInstructionResult(result_name="LastScanned", value=last_scanned),
                    "ScanStatus": StrResolvedInstructionResult(result_name="ScanStatus", value="ACTIVE"),
                }
            return {
                "ScannerType": StrResolvedInstructionResult(result_name="ScannerType", value="Inspector Enhanced"),
                "LastScanned": StrResolvedInstructionResult(result_name="LastScanned", value=""),
                "ScanStatus": StrResolvedInstructionResult(result_name="ScanStatus", value="NO_FINDINGS"),
            }

        try:
            _, scan_status, completed_at = ecr_repository.describe_image_scan_findings(
                self.ecr_client, repository_name=repository_name_arg.value, image_tag=image_tag_arg.value
            )
        except self.ecr_client.exceptions.ScanNotFoundException:
            # Image exists but was never scanned (scan-on-push disabled or image predates scanning).
            scan_status, completed_at = "NOT_SCANNED", ""
        return {
            "ScannerType": StrResolvedInstructionResult(result_name="ScannerType", value="ECR Basic"),
            "LastScanned": StrResolvedInstructionResult(result_name="LastScanned", value=completed_at),
            "ScanStatus": StrResolvedInstructionResult(result_name="ScanStatus", value=scan_status),
        }

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        try:
            instruction = AwsInspectorInstruction(instruction_name)
        except ValueError:
            raise InstructionNotFoundError(f"Unknown Inspector instruction: '{instruction_name}'") from None

        if instruction == AwsInspectorInstruction.LIST_VULNERABILITIES:
            return self._list_vulnerabilities(resolved_arguments)
        elif instruction == AwsInspectorInstruction.GET_SCAN_STATUS:
            return self._get_scan_status(resolved_arguments)

        raise InstructionNotFoundError(f"Unknown Inspector instruction: '{instruction_name}'")
