import json
import subprocess
from datetime import UTC, datetime
from enum import Enum

from kubernetes import client

from jupyter_deploy import cmd_utils
from jupyter_deploy.api.k8s import batch as k8s_batch
from jupyter_deploy.api.k8s.utils import format_age
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.enum import StatusCategory
from jupyter_deploy.exceptions import InstructionError, InstructionNotFoundError
from jupyter_deploy.provider.instruction_runner import InstructionRunner
from jupyter_deploy.provider.k8s.kubeconfig_verify import verify_kubeconfig_context
from jupyter_deploy.provider.resolved_argdefs import (
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
    retrieve_optional_arg,
)
from jupyter_deploy.provider.resolved_resultdefs import (
    ResolvedInstructionResult,
    StrResolvedInstructionResult,
)

_EMPTY_SUB_COMPONENT = ""


class K8sBatchInstruction(str, Enum):
    GET_CRONJOB_STATUS = "get-cronjob-status"
    GET_CRONJOB = "get-cronjob"
    CREATE_JOB_FROM_CRONJOB = "create-job-from-cronjob"
    GET_JOB_LOGS = "get-job-logs"


class K8sBatchRunner(InstructionRunner):
    """Runner class for Kubernetes Batch API instructions."""

    def __init__(
        self, display_manager: DisplayManager, api_client: client.ApiClient, kubeconfig_path: str | None = None
    ) -> None:
        super().__init__(display_manager)
        self.batch_api = client.BatchV1Api(api_client)
        self.core_api = client.CoreV1Api(api_client)
        self._kubeconfig_path = kubeconfig_path

    def _get_cronjob_status(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)
        query_arg = retrieve_optional_arg(resolved_arguments, "query", StrResolvedInstructionArgument, "")

        self.display_manager.info(f"Getting cronjob status: {name_arg.value}")
        status = k8s_batch.get_cronjob_status(self.batch_api, name=name_arg.value, namespace=scope_arg.value)

        details = status.schedule

        job_result = None
        if query_arg.value:
            job_result = k8s_batch.get_last_job_result(
                self.batch_api, namespace=scope_arg.value, label_selector=query_arg.value
            )

        if status.suspended:
            status_display = "Suspended"
            status_category = StatusCategory.DEGRADED
        elif status.active_count > 0 or (job_result and job_result.status == "Running"):
            status_display = "Active"
            status_category = StatusCategory.IN_PROGRESS
        else:
            status_display = "Idle"
            status_category = StatusCategory.HEALTHY

        if job_result:
            sub_display = job_result.status
            age = format_age(job_result.completion_time)
            if age:
                sub_display += f" ({age})"
            sub_component = json.dumps(
                {"name": "run (latest)", "status": sub_display, "last_updated": job_result.completion_time}
            )
        else:
            sub_component = _EMPTY_SUB_COMPONENT

        return {
            "Name": StrResolvedInstructionResult(result_name="Name", value=status.name),
            "Status": StrResolvedInstructionResult(result_name="Status", value=status_display),
            "StatusCategory": StrResolvedInstructionResult(result_name="StatusCategory", value=status_category),
            "Details": StrResolvedInstructionResult(result_name="Details", value=details),
            "SubComponent": StrResolvedInstructionResult(result_name="SubComponent", value=sub_component),
        }

    def _get_cronjob(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)

        self.display_manager.info(f"Getting cronjob details: {name_arg.value}")
        info = k8s_batch.get_cronjob(self.batch_api, name=name_arg.value, namespace=scope_arg.value)

        return {
            "Name": StrResolvedInstructionResult(result_name="Name", value=info.name),
            "Resource": StrResolvedInstructionResult(result_name="Resource", value=json.dumps(info.resource)),
        }

    def _create_job_from_cronjob(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)

        self.display_manager.info(f"Triggering job from cronjob: {name_arg.value}")
        job_name = k8s_batch.create_job_from_cronjob(self.batch_api, name=name_arg.value, namespace=scope_arg.value)

        return {
            "JobName": StrResolvedInstructionResult(result_name="JobName", value=job_name),
        }

    def _resolve_cronjob_pod_name(self, cronjob_name: str, namespace: str, label_selector: str) -> str:
        matching = k8s_batch.find_jobs(self.batch_api, namespace=namespace, label_selector=label_selector)

        if not matching:
            raise ValueError(f"No jobs found for cronjob {cronjob_name} in namespace {namespace}")

        matching.sort(
            key=lambda j: j.status.start_time if j.status and j.status.start_time else datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )

        latest_job = matching[0]
        job_name = latest_job.metadata.name if latest_job.metadata else ""
        if not job_name:
            raise ValueError(f"No jobs found for cronjob {cronjob_name} in namespace {namespace}")

        pods = self.core_api.list_namespaced_pod(namespace=namespace, label_selector=f"job-name={job_name}")
        if not pods.items:
            raise ValueError(f"No pods found for job {job_name} in namespace {namespace}")

        pod_name = pods.items[0].metadata.name if pods.items[0].metadata else ""
        if not pod_name:
            raise ValueError(f"No pods found for job {job_name} in namespace {namespace}")
        return pod_name

    def _get_job_logs(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)
        query_arg = require_arg(resolved_arguments, "query", StrResolvedInstructionArgument)
        extra_arg = retrieve_optional_arg(resolved_arguments, "extra", StrResolvedInstructionArgument, "")
        expected_cluster_config = retrieve_optional_arg(
            resolved_arguments, "expected_cluster_config", StrResolvedInstructionArgument, ""
        ).value

        self.display_manager.info(f"Getting logs for cronjob: {name_arg.value}")

        pod_name = self._resolve_cronjob_pod_name(name_arg.value, scope_arg.value, query_arg.value)

        verify_kubeconfig_context(expected_cluster_config or None, self._kubeconfig_path)
        kubectl_cmd = ["kubectl", "logs", pod_name, "--namespace", scope_arg.value]
        if self._kubeconfig_path:
            kubectl_cmd.extend(["--kubeconfig", self._kubeconfig_path])
        if extra_arg.value:
            kubectl_cmd.extend(extra_arg.value.split())

        try:
            logs = cmd_utils.run_cmd_and_capture_output(kubectl_cmd)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else ""
            if "unknown flag" in stderr or "unknown shorthand flag" in stderr or "invalid argument" in stderr:
                raise InstructionError(stderr) from None
            raise
        return {
            "Logs": StrResolvedInstructionResult(result_name="Logs", value=logs),
        }

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        try:
            instruction = K8sBatchInstruction(instruction_name)
        except ValueError:
            raise InstructionNotFoundError(f"Unknown K8s batch instruction: '{instruction_name}'") from None

        if instruction == K8sBatchInstruction.GET_CRONJOB_STATUS:
            return self._get_cronjob_status(resolved_arguments)
        elif instruction == K8sBatchInstruction.GET_CRONJOB:
            return self._get_cronjob(resolved_arguments)
        elif instruction == K8sBatchInstruction.CREATE_JOB_FROM_CRONJOB:
            return self._create_job_from_cronjob(resolved_arguments)
        elif instruction == K8sBatchInstruction.GET_JOB_LOGS:
            return self._get_job_logs(resolved_arguments)

        raise InstructionNotFoundError(f"Unknown K8s batch instruction: '{instruction_name}'")
