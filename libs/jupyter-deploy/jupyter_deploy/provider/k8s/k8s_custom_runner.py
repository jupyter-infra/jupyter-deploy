import json
from enum import Enum

from kubernetes import client

from jupyter_deploy.api.k8s import custom as k8s_custom
from jupyter_deploy.api.k8s.custom import CustomResourceRef
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.exceptions import InstructionNotFoundError
from jupyter_deploy.provider.instruction_runner import InstructionRunner
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


class K8sCustomInstruction(str, Enum):
    """K8s Custom Resource instructions accessible from manifest api-name."""

    LIST = "list"
    GET = "get"
    GET_CLUSTER = "get-cluster"
    PATCH = "patch"
    LIST_CLUSTER = "list-cluster"


class K8sCustomRunner(InstructionRunner):
    """Generic runner for Kubernetes custom resource operations.

    CRD coordinates (group, version, plural) are passed as instruction arguments
    from the manifest, not hardcoded.
    """

    def __init__(self, display_manager: DisplayManager, api_client: client.ApiClient) -> None:
        super().__init__(display_manager)
        self.custom_api = client.CustomObjectsApi(api_client)

    @staticmethod
    def _extract_ref(resolved_arguments: dict[str, ResolvedInstructionArgument]) -> CustomResourceRef:
        group_arg = require_arg(resolved_arguments, "group", StrResolvedInstructionArgument)
        version_arg = require_arg(resolved_arguments, "version", StrResolvedInstructionArgument)
        plural_arg = require_arg(resolved_arguments, "plural", StrResolvedInstructionArgument)
        return CustomResourceRef(group=group_arg.value, version=version_arg.value, plural=plural_arg.value)

    def _list(self, resolved_arguments: dict[str, ResolvedInstructionArgument]) -> dict[str, ResolvedInstructionResult]:
        ref = self._extract_ref(resolved_arguments)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)
        page_size_arg = retrieve_optional_arg(resolved_arguments, "page_size", StrResolvedInstructionArgument, "")
        pagination_token_arg = retrieve_optional_arg(
            resolved_arguments, "pagination_token", StrResolvedInstructionArgument, ""
        )

        self.display_manager.info(f"Listing {ref.plural} in {scope_arg.value}")
        items, next_token = k8s_custom.list_namespaced(
            self.custom_api,
            ref=ref,
            namespace=scope_arg.value,
            limit=int(page_size_arg.value) if page_size_arg.value else None,
            _continue=pagination_token_arg.value or None,
        )

        names = [item.get("metadata", {}).get("name", "") for item in items]
        return {
            "Names": ListStrResolvedInstructionResult(result_name="Names", value=names),
            "Items": StrResolvedInstructionResult(result_name="Items", value=json.dumps(items)),
            "NextToken": StrResolvedInstructionResult(result_name="NextToken", value=next_token or ""),
        }

    def _get(self, resolved_arguments: dict[str, ResolvedInstructionArgument]) -> dict[str, ResolvedInstructionResult]:
        ref = self._extract_ref(resolved_arguments)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)

        self.display_manager.info(f"Getting {ref.plural}/{name_arg.value}")
        result = k8s_custom.get_namespaced(self.custom_api, ref=ref, namespace=scope_arg.value, name=name_arg.value)

        return {
            "Name": StrResolvedInstructionResult(result_name="Name", value=result.name),
            "Resource": StrResolvedInstructionResult(result_name="Resource", value=json.dumps(result.resource)),
        }

    def _get_cluster(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        ref = self._extract_ref(resolved_arguments)
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)

        self.display_manager.info(f"Getting cluster-scoped {ref.plural}/{name_arg.value}")
        result = k8s_custom.get_cluster(self.custom_api, ref=ref, name=name_arg.value)

        return {
            "Name": StrResolvedInstructionResult(result_name="Name", value=result.name),
            "Resource": StrResolvedInstructionResult(result_name="Resource", value=json.dumps(result.resource)),
        }

    def _patch(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        ref = self._extract_ref(resolved_arguments)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        body_arg = require_arg(resolved_arguments, "body", StrResolvedInstructionArgument)

        body = json.loads(body_arg.value)

        self.display_manager.info(f"Patching {ref.plural}/{name_arg.value}")
        result = k8s_custom.patch_namespaced(
            self.custom_api, ref=ref, namespace=scope_arg.value, name=name_arg.value, body=body
        )

        return {
            "Name": StrResolvedInstructionResult(result_name="Name", value=result.name),
            "Resource": StrResolvedInstructionResult(result_name="Resource", value=json.dumps(result.resource)),
        }

    def _list_cluster(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        ref = self._extract_ref(resolved_arguments)
        page_size_arg = retrieve_optional_arg(resolved_arguments, "page_size", StrResolvedInstructionArgument, "")
        pagination_token_arg = retrieve_optional_arg(
            resolved_arguments, "pagination_token", StrResolvedInstructionArgument, ""
        )

        self.display_manager.info(f"Listing cluster-scoped {ref.plural}")
        items, next_token = k8s_custom.list_cluster(
            self.custom_api,
            ref=ref,
            limit=int(page_size_arg.value) if page_size_arg.value else None,
            _continue=pagination_token_arg.value or None,
        )

        names = [item.get("metadata", {}).get("name", "") for item in items]
        return {
            "Names": ListStrResolvedInstructionResult(result_name="Names", value=names),
            "Items": StrResolvedInstructionResult(result_name="Items", value=json.dumps(items)),
            "NextToken": StrResolvedInstructionResult(result_name="NextToken", value=next_token or ""),
        }

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        try:
            instruction = K8sCustomInstruction(instruction_name)
        except ValueError:
            raise InstructionNotFoundError(f"Unknown K8s custom instruction: '{instruction_name}'") from None

        if instruction == K8sCustomInstruction.LIST:
            return self._list(resolved_arguments)
        elif instruction == K8sCustomInstruction.GET:
            return self._get(resolved_arguments)
        elif instruction == K8sCustomInstruction.GET_CLUSTER:
            return self._get_cluster(resolved_arguments)
        elif instruction == K8sCustomInstruction.PATCH:
            return self._patch(resolved_arguments)
        elif instruction == K8sCustomInstruction.LIST_CLUSTER:
            return self._list_cluster(resolved_arguments)

        raise InstructionNotFoundError(f"Unknown K8s custom instruction: '{instruction_name}'")
