import json
from enum import Enum

from kubernetes import client

from jupyter_deploy.api.k8s import apiextensions as k8s_apiextensions
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.exceptions import InstructionNotFoundError
from jupyter_deploy.provider.instruction_runner import InstructionRunner
from jupyter_deploy.provider.resolved_argdefs import (
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
)
from jupyter_deploy.provider.resolved_resultdefs import (
    ListStrResolvedInstructionResult,
    ResolvedInstructionResult,
    StrResolvedInstructionResult,
)


class K8sApiextensionsInstruction(str, Enum):
    """K8s apiextensions API instructions accessible from manifest api-name."""

    GET_CRD = "get-crd"


class K8sApiextensionsRunner(InstructionRunner):
    """Runner for the Kubernetes apiextensions API (CustomResourceDefinition).

    Uses the typed ApiextensionsV1Api rather than the generic CustomObjectsApi,
    so CRD introspection (established condition, served versions) is typed rather
    than resolved through stringly-typed field paths.
    """

    def __init__(self, display_manager: DisplayManager, api_client: client.ApiClient) -> None:
        super().__init__(display_manager)
        self.apiextensions_api = client.ApiextensionsV1Api(api_client)

    def _get_crd(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)

        self.display_manager.info(f"Getting CustomResourceDefinition/{name_arg.value}")
        info = k8s_apiextensions.get_crd(self.apiextensions_api, name=name_arg.value)

        return {
            "Name": StrResolvedInstructionResult(result_name="Name", value=info.name),
            "Resource": StrResolvedInstructionResult(result_name="Resource", value=json.dumps(info.resource)),
            "Established": StrResolvedInstructionResult(
                result_name="Established", value="true" if info.established else "false"
            ),
            "ServedVersions": ListStrResolvedInstructionResult(
                result_name="ServedVersions", value=info.served_versions
            ),
            "StoredVersion": StrResolvedInstructionResult(result_name="StoredVersion", value=info.stored_version),
        }

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        try:
            instruction = K8sApiextensionsInstruction(instruction_name)
        except ValueError:
            raise InstructionNotFoundError(f"Unknown K8s apiextensions instruction: '{instruction_name}'") from None

        if instruction == K8sApiextensionsInstruction.GET_CRD:
            return self._get_crd(resolved_arguments)

        raise InstructionNotFoundError(f"Unknown K8s apiextensions instruction: '{instruction_name}'")
