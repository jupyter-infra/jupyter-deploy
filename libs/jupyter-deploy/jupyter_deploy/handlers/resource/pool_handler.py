import json
from typing import Any

from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.exceptions import PoolNotFoundError
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.handlers.payloads import PoolDetail
from jupyter_deploy.handlers.resource.resource_utils import collect_results, evaluate_status_rules
from jupyter_deploy.provider import manifest_command_runner as cmd_runner
from jupyter_deploy.provider.resolved_clidefs import ResolvedCliParameter, StrResolvedCliParameter

# Pool kinds surfaced through the unified `jd pool` interface. "karpenter" is a
# Karpenter NodePool (k8s CRD); "managed" is an EKS Managed Node Group (AWS API).
POOL_TYPE_KARPENTER = "karpenter"
POOL_TYPE_MANAGED = "managed"


class PoolHandler(BaseProjectHandler):
    """Handler class to interact with node pools.

    A "pool" abstracts over two different underlying objects — Karpenter
    NodePools and EKS Managed Node Groups — so users can list, show, and check
    status without knowing which kind a pool is. This handler owns that
    abstraction: it queries both sets of manifest commands, tags each result
    with its kind, and routes show/status to the right command by kind.
    """

    _output_handler: EngineOutputsHandler

    def __init__(self, display_manager: DisplayManager) -> None:
        """Instantiate the Pool handler."""
        super().__init__(display_manager=display_manager)

        if self.engine == EngineType.TERRAFORM:
            self._output_handler = tf_outputs.TerraformOutputsHandler(
                project_path=self.project_path, project_manifest=self.project_manifest
            )
            self._variable_handler = tf_variables.TerraformVariablesHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
                display_manager=self.display_manager,
            )
        else:
            raise NotImplementedError(f"PoolHandler not implemented for engine: {self.engine}")

    def _runner(self) -> cmd_runner.ManifestCommandRunner:
        return cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )

    def _list_karpenter_names(self) -> list[str]:
        """Return the names of Karpenter NodePools."""
        command = self.project_manifest.get_command("pool.list")
        runner = self._runner()
        runner.run_command_sequence(command, cli_paramdefs={})
        raw = runner.get_result_value(command, "pool.list", str)
        items: list[Any] = json.loads(raw) if isinstance(raw, str) else raw
        return [item.get("metadata", {}).get("name", "") for item in items if isinstance(item, dict)]

    def _list_managed_names(self) -> list[str]:
        """Return the names of EKS Managed Node Groups.

        Returns an empty list when the template declares no managed-pool command,
        so templates without MNGs transparently show only Karpenter pools.
        """
        command = self.project_manifest.get_command_or_none("pool.list-managed")
        if command is None:
            return []
        runner = self._runner()
        runner.run_command_sequence(command, cli_paramdefs={})
        names = runner.get_result_value(command, "pool.list-managed", list)
        return [name for name in names if name]

    def list_pools(self) -> list[PoolDetail]:
        """Return all pools (Karpenter + managed), each tagged with its type.

        Status/resource are left empty here — listing stays cheap and does not
        fan out a describe call per pool. Use show_pool/get_status for detail.
        """
        pools = [PoolDetail(name=name, type=POOL_TYPE_KARPENTER) for name in self._list_karpenter_names() if name]
        pools += [PoolDetail(name=name, type=POOL_TYPE_MANAGED) for name in self._list_managed_names() if name]
        return pools

    def _resolve_pool_type(self, name: str) -> str:
        """Determine whether a named pool is Karpenter or managed.

        Karpenter is checked first; falls back to managed only when the name is
        found among the MNGs. Raises PoolNotFoundError if it matches neither.
        """
        karpenter_names = self._list_karpenter_names()
        if name in karpenter_names:
            return POOL_TYPE_KARPENTER
        managed_names = self._list_managed_names()
        if name in managed_names:
            return POOL_TYPE_MANAGED
        raise PoolNotFoundError(name, karpenter_names + managed_names)

    def show_pool(self, name: str) -> PoolDetail:
        """Return detailed info for a named pool, routing by its type."""
        pool_type = self._resolve_pool_type(name)
        if pool_type == POOL_TYPE_MANAGED:
            command = self.project_manifest.get_command("pool.status-managed")
            rules = self.project_manifest.pool_managed_status_rules
        else:
            command = self.project_manifest.get_command("pool.status")
            rules = self.project_manifest.pool_status_rules

        runner = self._runner()
        cli_paramdefs: dict[str, ResolvedCliParameter[Any]] = {
            "name": StrResolvedCliParameter(parameter_name="name", value=name),
        }
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
        results = collect_results(runner, command)
        resource = results.get("resource", {})
        # No rules declared -> fall back to "Unknown" (evaluate_status_rules' own
        # no-match sentinel) rather than an empty string that reads as a bug.
        status = evaluate_status_rules(json.dumps(resource), rules) if rules else "Unknown"
        return PoolDetail(
            name=results.get("name", name),
            type=pool_type,
            status=status,
            resource=resource,
        )

    def get_status(self, name: str) -> str:
        """Returns the status of a named pool, derived from manifest status rules."""
        detail = self.show_pool(name=name)
        return detail.status
