import json
from typing import Any

from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.handlers.payloads import PoolDetail
from jupyter_deploy.handlers.resource.resource_utils import collect_results, evaluate_status_rules
from jupyter_deploy.provider import manifest_command_runner as cmd_runner
from jupyter_deploy.provider.resolved_clidefs import ResolvedCliParameter, StrResolvedCliParameter


class PoolHandler(BaseProjectHandler):
    """Handler class to interact with node pools."""

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

    def list_pools(self) -> list[str]:
        """Returns list of node pool names."""
        command = self.project_manifest.get_command("pool.list")
        runner = self._runner()
        runner.run_command_sequence(command, cli_paramdefs={})
        raw = runner.get_result_value(command, "pool.list", str)
        items: list[Any] = json.loads(raw) if isinstance(raw, str) else raw
        return [item.get("metadata", {}).get("name", "") for item in items if isinstance(item, dict)]

    def show_pool(self, name: str) -> PoolDetail:
        """Returns detailed info for a named node pool."""
        command = self.project_manifest.get_command("pool.status")
        runner = self._runner()
        cli_paramdefs: dict[str, ResolvedCliParameter[Any]] = {
            "name": StrResolvedCliParameter(parameter_name="name", value=name),
        }
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
        results = collect_results(runner, command)
        resource = results.get("resource", {})
        rules = self.project_manifest.pool_status_rules
        # No rules declared -> fall back to "Unknown" (evaluate_status_rules' own
        # no-match sentinel) rather than an empty string that reads as a bug.
        status = evaluate_status_rules(json.dumps(resource), rules) if rules else "Unknown"
        return PoolDetail(
            name=results.get("name", name),
            status=status,
            resource=resource,
        )

    def get_status(self, name: str) -> str:
        """Returns the status of a named node pool, derived from manifest status rules."""
        detail = self.show_pool(name=name)
        return detail.status
