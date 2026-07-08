import json
import shlex
import subprocess
from enum import Enum

from kubernetes import client

from jupyter_deploy import cmd_utils
from jupyter_deploy.api.k8s import core as k8s_core
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.exceptions import (
    InstructionError,
    InstructionNotFoundError,
    InteractiveSessionError,
    InteractiveSessionTimeoutError,
)
from jupyter_deploy.provider.instruction_runner import InstructionRunner
from jupyter_deploy.provider.k8s.kubeconfig_verify import verify_kubeconfig_context
from jupyter_deploy.provider.resolved_argdefs import (
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
    retrieve_optional_arg,
)
from jupyter_deploy.provider.resolved_resultdefs import (
    ListStrResolvedInstructionResult,
    ResolvedInstructionResult,
    StrResolvedInstructionResult,
)


class K8sCoreInstruction(str, Enum):
    """K8s Core API instructions accessible from manifest api-name."""

    LIST_NODES = "list-nodes"
    GET_NODE = "get-node"
    LIST_PODS = "list-pods"
    GET_POD = "get-pod"
    DEPLOYMENT_LOGS = "deployment-logs"
    EXEC_POD = "exec-pod"
    EXEC_POD_INTERACTIVE = "exec-pod-interactive"


class K8sCoreRunner(InstructionRunner):
    """Runner class for Kubernetes Core API instructions."""

    def __init__(
        self, display_manager: DisplayManager, api_client: client.ApiClient, kubeconfig_path: str | None = None
    ) -> None:
        super().__init__(display_manager)
        self.core_api = client.CoreV1Api(api_client)
        self.apps_api = client.AppsV1Api(api_client)
        self._kubeconfig_path = kubeconfig_path

    def _list_nodes(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        query_arg = retrieve_optional_arg(resolved_arguments, "query", StrResolvedInstructionArgument, "")
        page_size_arg = retrieve_optional_arg(resolved_arguments, "page_size", StrResolvedInstructionArgument, "")
        pagination_token_arg = retrieve_optional_arg(
            resolved_arguments, "pagination_token", StrResolvedInstructionArgument, ""
        )

        self.display_manager.info("Listing nodes")
        nodes, next_token = k8s_core.list_nodes(
            self.core_api,
            label_selector=query_arg.value or None,
            limit=int(page_size_arg.value) if page_size_arg.value else None,
            _continue=pagination_token_arg.value or None,
        )

        node_names = [node.name for node in nodes]
        return {
            "NodeNames": ListStrResolvedInstructionResult(result_name="NodeNames", value=node_names),
            "NextToken": StrResolvedInstructionResult(result_name="NextToken", value=next_token or ""),
        }

    def _get_node(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)

        self.display_manager.info(f"Getting node: {name_arg.value}")
        node = k8s_core.get_node(self.core_api, name=name_arg.value)

        return {
            "Name": StrResolvedInstructionResult(result_name="Name", value=node.name),
            "Status": StrResolvedInstructionResult(result_name="Status", value=node.status.value),
            "Resource": StrResolvedInstructionResult(result_name="Resource", value=json.dumps(node.resource)),
        }

    def _list_pods(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)
        query_arg = retrieve_optional_arg(resolved_arguments, "query", StrResolvedInstructionArgument, "")
        page_size_arg = retrieve_optional_arg(resolved_arguments, "page_size", StrResolvedInstructionArgument, "")
        pagination_token_arg = retrieve_optional_arg(
            resolved_arguments, "pagination_token", StrResolvedInstructionArgument, ""
        )

        self.display_manager.info(f"Listing pods in namespace: {scope_arg.value}")
        pods, next_token = k8s_core.list_pods(
            self.core_api,
            namespace=scope_arg.value,
            label_selector=query_arg.value or None,
            limit=int(page_size_arg.value) if page_size_arg.value else None,
            _continue=pagination_token_arg.value or None,
        )

        pod_names = [pod.name for pod in pods]
        return {
            "PodNames": StrResolvedInstructionResult(result_name="PodNames", value=",".join(pod_names)),
            "NextToken": StrResolvedInstructionResult(result_name="NextToken", value=next_token or ""),
        }

    def _get_pod(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)

        self.display_manager.info(f"Getting pod: {name_arg.value}")
        pod = k8s_core.get_pod(self.core_api, name=name_arg.value, namespace=scope_arg.value)

        return {
            "Name": StrResolvedInstructionResult(result_name="Name", value=pod.name),
            "Phase": StrResolvedInstructionResult(result_name="Phase", value=pod.phase.value),
        }

    def _deployment_logs(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)
        container_arg = retrieve_optional_arg(resolved_arguments, "container", StrResolvedInstructionArgument, "")
        extra_arg = retrieve_optional_arg(resolved_arguments, "extra", StrResolvedInstructionArgument, "")
        expected_cluster_config = retrieve_optional_arg(
            resolved_arguments, "expected_cluster_config", StrResolvedInstructionArgument, ""
        ).value

        self.display_manager.info(f"Getting logs for deployment {name_arg.value} in namespace: {scope_arg.value}")

        pod_name = self._resolve_pod_name(name_arg.value, scope_arg.value)
        container = container_arg.value if container_arg.value and container_arg.value != "default" else None

        verify_kubeconfig_context(expected_cluster_config or None, self._kubeconfig_path)
        kubectl_cmd = ["kubectl", "logs", pod_name, "--namespace", scope_arg.value]
        if self._kubeconfig_path:
            kubectl_cmd.extend(["--kubeconfig", self._kubeconfig_path])
        if container:
            kubectl_cmd.extend(["-c", container])
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

    def _resolve_pod_name(self, deployment_name: str, namespace: str) -> str:
        deployment = self.apps_api.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        match_labels = deployment.spec.selector.match_labels or {}
        label_selector = ",".join(f"{k}={v}" for k, v in match_labels.items())
        if not label_selector:
            raise ValueError(f"Deployment {deployment_name} has no selector labels")
        pods, _ = k8s_core.list_pods(self.core_api, namespace=namespace, label_selector=label_selector, limit=1)
        if not pods:
            raise ValueError(f"No pods found for deployment {deployment_name} in namespace {namespace}")
        return pods[0].name

    def _exec_pod(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)
        command_arg = require_arg(resolved_arguments, "command", StrResolvedInstructionArgument)
        container_arg = retrieve_optional_arg(resolved_arguments, "container", StrResolvedInstructionArgument, "")
        deployment_name_arg = retrieve_optional_arg(
            resolved_arguments, "deployment_name", StrResolvedInstructionArgument, ""
        )
        name_arg = retrieve_optional_arg(resolved_arguments, "name", StrResolvedInstructionArgument, "")

        if deployment_name_arg.value:
            pod_name = self._resolve_pod_name(deployment_name_arg.value, scope_arg.value)
        elif name_arg.value:
            pod_name = name_arg.value
        else:
            raise ValueError("Either 'name' (pod name) or 'deployment_name' must be provided")

        container = container_arg.value if container_arg.value and container_arg.value != "default" else None
        command_parts = shlex.split(command_arg.value)
        self.display_manager.info(f"Executing command on pod: {pod_name}")
        result = k8s_core.exec_pod(
            self.core_api,
            name=pod_name,
            namespace=scope_arg.value,
            command=command_parts,
            container=container,
        )

        return {
            "Stdout": StrResolvedInstructionResult(result_name="Stdout", value=result.stdout),
            "Stderr": StrResolvedInstructionResult(result_name="Stderr", value=result.stderr),
            "ReturnCode": StrResolvedInstructionResult(result_name="ReturnCode", value=str(result.returncode)),
        }

    def _exec_pod_interactive(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)
        command_arg = retrieve_optional_arg(resolved_arguments, "command", StrResolvedInstructionArgument, "/bin/bash")
        container_arg = retrieve_optional_arg(resolved_arguments, "container", StrResolvedInstructionArgument, "")
        deployment_name_arg = retrieve_optional_arg(
            resolved_arguments, "deployment_name", StrResolvedInstructionArgument, ""
        )
        name_arg = retrieve_optional_arg(resolved_arguments, "name", StrResolvedInstructionArgument, "")
        expected_cluster_config = retrieve_optional_arg(
            resolved_arguments, "expected_cluster_config", StrResolvedInstructionArgument, ""
        ).value

        if deployment_name_arg.value:
            pod_name = self._resolve_pod_name(deployment_name_arg.value, scope_arg.value)
        elif name_arg.value:
            pod_name = name_arg.value
        else:
            raise ValueError("Either 'name' (pod name) or 'deployment_name' must be provided")

        container = container_arg.value if container_arg.value and container_arg.value != "default" else None

        verify_kubeconfig_context(expected_cluster_config or None, self._kubeconfig_path)
        kubectl_cmd = ["kubectl", "exec", "-it", pod_name, "-n", scope_arg.value]
        if self._kubeconfig_path:
            kubectl_cmd.extend(["--kubeconfig", self._kubeconfig_path])
        if container:
            kubectl_cmd.extend(["-c", container])
        kubectl_cmd.extend(["--", command_arg.value])

        self.display_manager.hint("Type 'exit' to close the session.")
        self.display_manager.stop_spinning()

        retcode, timed_out = cmd_utils.run_cmd_and_pipe_to_terminal(kubectl_cmd)

        if timed_out:
            raise InteractiveSessionTimeoutError("kubectl exec session timed out")
        if retcode:
            raise InteractiveSessionError("kubectl exec session failed")

        return {}

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        try:
            instruction = K8sCoreInstruction(instruction_name)
        except ValueError:
            raise InstructionNotFoundError(f"Unknown K8s core instruction: '{instruction_name}'") from None

        if instruction == K8sCoreInstruction.LIST_NODES:
            return self._list_nodes(resolved_arguments)
        elif instruction == K8sCoreInstruction.GET_NODE:
            return self._get_node(resolved_arguments)
        elif instruction == K8sCoreInstruction.LIST_PODS:
            return self._list_pods(resolved_arguments)
        elif instruction == K8sCoreInstruction.GET_POD:
            return self._get_pod(resolved_arguments)
        elif instruction == K8sCoreInstruction.DEPLOYMENT_LOGS:
            return self._deployment_logs(resolved_arguments)
        elif instruction == K8sCoreInstruction.EXEC_POD:
            return self._exec_pod(resolved_arguments)
        elif instruction == K8sCoreInstruction.EXEC_POD_INTERACTIVE:
            return self._exec_pod_interactive(resolved_arguments)

        raise InstructionNotFoundError(f"Unknown K8s core instruction: '{instruction_name}'")
