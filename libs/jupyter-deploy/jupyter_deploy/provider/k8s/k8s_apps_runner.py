import json
from enum import Enum

from kubernetes import client

from jupyter_deploy.api.k8s import apps as k8s_apps
from jupyter_deploy.api.k8s.utils import format_age
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.enum import StatusCategory
from jupyter_deploy.exceptions import InstructionNotFoundError
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

_EMPTY_SUB_COMPONENT = ""


class K8sAppsInstruction(str, Enum):
    """Instructions supported by the K8s Apps (AppsV1) runner."""

    GET_DEPLOYMENT_STATUS = "get-deployment-status"
    GET_DAEMONSET_STATUS = "get-daemonset-status"
    GET_STATEFULSET_STATUS = "get-statefulset-status"
    GET_DEPLOYMENT = "get-deployment"
    GET_DAEMONSET = "get-daemonset"
    GET_STATEFULSET = "get-statefulset"
    ROLLOUT_RESTART = "rollout-restart"


class K8sAppsRunner(InstructionRunner):
    """Runner class for Kubernetes Apps API instructions."""

    def __init__(self, display_manager: DisplayManager, api_client: client.ApiClient) -> None:
        super().__init__(display_manager)
        self.apps_api = client.AppsV1Api(api_client)
        self.core_api = client.CoreV1Api(api_client)

    def _get_deployment_status(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)

        self.display_manager.info(f"Getting deployment status: {name_arg.value}")
        status = k8s_apps.get_deployment_status(self.apps_api, name=name_arg.value, namespace=scope_arg.value)

        if not status.available:
            status_display = "Degraded"
            status_category = StatusCategory.DEGRADED
        elif status.ready_replicas < status.total_replicas:
            status_display = "Updating"
            status_category = StatusCategory.IN_PROGRESS
        else:
            status_display = "Ready"
            status_category = StatusCategory.HEALTHY
        details = f"{status.ready_replicas}/{status.total_replicas} replicas"

        pod_info = k8s_apps.get_deployment_oldest_pod(
            self.apps_api, self.core_api, name=name_arg.value, namespace=scope_arg.value
        )
        if pod_info:
            sub_display = pod_info.reason or pod_info.phase
            age = format_age(pod_info.last_transition)
            if age:
                sub_display += f" ({age})"
            sub_component = json.dumps(
                {"name": "pod (oldest)", "status": sub_display, "last_updated": pod_info.last_transition}
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

    def _get_daemonset_status(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)

        self.display_manager.info(f"Getting daemonset status: {name_arg.value}")
        status = k8s_apps.get_daemonset_status(self.apps_api, name=name_arg.value, namespace=scope_arg.value)

        if status.ready:
            status_display = "Ready"
            status_category = StatusCategory.HEALTHY
        elif status.updated_pods < status.desired_pods:
            status_display = "Updating"
            status_category = StatusCategory.IN_PROGRESS
        else:
            status_display = "Degraded"
            status_category = StatusCategory.DEGRADED
        details = f"{status.ready_pods}/{status.desired_pods} nodes"

        return {
            "Name": StrResolvedInstructionResult(result_name="Name", value=status.name),
            "Status": StrResolvedInstructionResult(result_name="Status", value=status_display),
            "StatusCategory": StrResolvedInstructionResult(result_name="StatusCategory", value=status_category),
            "Details": StrResolvedInstructionResult(result_name="Details", value=details),
            "SubComponent": StrResolvedInstructionResult(result_name="SubComponent", value=_EMPTY_SUB_COMPONENT),
        }

    def _get_statefulset_status(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)

        self.display_manager.info(f"Getting statefulset status: {name_arg.value}")
        status = k8s_apps.get_statefulset_status(self.apps_api, name=name_arg.value, namespace=scope_arg.value)

        if status.ready:
            status_display = "Ready"
            status_category = StatusCategory.HEALTHY
        elif status.updated_replicas < status.total_replicas:
            status_display = "Updating"
            status_category = StatusCategory.IN_PROGRESS
        else:
            status_display = "Degraded"
            status_category = StatusCategory.DEGRADED
        details = f"{status.ready_replicas}/{status.total_replicas} replicas"

        return {
            "Name": StrResolvedInstructionResult(result_name="Name", value=status.name),
            "Status": StrResolvedInstructionResult(result_name="Status", value=status_display),
            "StatusCategory": StrResolvedInstructionResult(result_name="StatusCategory", value=status_category),
            "Details": StrResolvedInstructionResult(result_name="Details", value=details),
            "SubComponent": StrResolvedInstructionResult(result_name="SubComponent", value=_EMPTY_SUB_COMPONENT),
        }

    def _get_deployment(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)

        self.display_manager.info(f"Getting deployment details: {name_arg.value}")
        info = k8s_apps.get_deployment(self.apps_api, name=name_arg.value, namespace=scope_arg.value)

        return {
            "Name": StrResolvedInstructionResult(result_name="Name", value=info.name),
            "Resource": StrResolvedInstructionResult(result_name="Resource", value=json.dumps(info.resource)),
        }

    def _get_daemonset(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)

        self.display_manager.info(f"Getting daemonset details: {name_arg.value}")
        info = k8s_apps.get_daemonset(self.apps_api, name=name_arg.value, namespace=scope_arg.value)

        return {
            "Name": StrResolvedInstructionResult(result_name="Name", value=info.name),
            "Resource": StrResolvedInstructionResult(result_name="Resource", value=json.dumps(info.resource)),
        }

    def _get_statefulset(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)

        self.display_manager.info(f"Getting statefulset details: {name_arg.value}")
        info = k8s_apps.get_statefulset(self.apps_api, name=name_arg.value, namespace=scope_arg.value)

        return {
            "Name": StrResolvedInstructionResult(result_name="Name", value=info.name),
            "Resource": StrResolvedInstructionResult(result_name="Resource", value=json.dumps(info.resource)),
        }

    def _rollout_restart(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)

        self.display_manager.info(f"Restarting deployment: {name_arg.value}")
        k8s_apps.rollout_restart(self.apps_api, name=name_arg.value, namespace=scope_arg.value)

        return {}

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        try:
            instruction = K8sAppsInstruction(instruction_name)
        except ValueError:
            raise InstructionNotFoundError(f"Unknown K8s apps instruction: '{instruction_name}'") from None

        if instruction == K8sAppsInstruction.GET_DEPLOYMENT_STATUS:
            return self._get_deployment_status(resolved_arguments)
        elif instruction == K8sAppsInstruction.GET_DAEMONSET_STATUS:
            return self._get_daemonset_status(resolved_arguments)
        elif instruction == K8sAppsInstruction.GET_STATEFULSET_STATUS:
            return self._get_statefulset_status(resolved_arguments)
        elif instruction == K8sAppsInstruction.GET_DEPLOYMENT:
            return self._get_deployment(resolved_arguments)
        elif instruction == K8sAppsInstruction.GET_DAEMONSET:
            return self._get_daemonset(resolved_arguments)
        elif instruction == K8sAppsInstruction.GET_STATEFULSET:
            return self._get_statefulset(resolved_arguments)
        elif instruction == K8sAppsInstruction.ROLLOUT_RESTART:
            return self._rollout_restart(resolved_arguments)

        raise InstructionNotFoundError(f"Unknown K8s apps instruction: '{instruction_name}'")
