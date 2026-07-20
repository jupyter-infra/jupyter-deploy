from typing import Any

from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.exceptions import ResourceNameRequiredError
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.handlers.payloads import HostDetail
from jupyter_deploy.handlers.resource.resource_utils import collect_results
from jupyter_deploy.provider import manifest_command_runner as cmd_runner
from jupyter_deploy.provider.resolved_clidefs import (
    ListStrResolvedCliParameter,
    ResolvedCliParameter,
    StrResolvedCliParameter,
)


class HostHandler(BaseProjectHandler):
    """Handler class to directly interact with the host running jupyter server."""

    _output_handler: EngineOutputsHandler

    def __init__(self, display_manager: DisplayManager) -> None:
        """Instantiate the Host handler."""
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
            raise NotImplementedError(f"OutputsHandler implementation not found for engine: {self.engine}")

    def list_hosts(
        self,
        query: str,
        limit: int | None = None,
        continue_from: str | None = None,
    ) -> tuple[list[str], str | None]:
        """Returns a list of host names and an optional continuation token."""
        command = self.project_manifest.get_command("host.list")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        cli_paramdefs: dict[str, ResolvedCliParameter[Any]] = {
            "query": StrResolvedCliParameter(parameter_name="query", value=query),
            "limit": StrResolvedCliParameter(parameter_name="limit", value=str(limit) if limit is not None else ""),
            "continue_from": StrResolvedCliParameter(parameter_name="continue_from", value=continue_from or ""),
        }
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
        names = runner.get_result_value(command, "host.list", list)
        next_token = runner.get_result_value_with_fallback(command, "host.list.next_token", str, "") or None
        return names, next_token

    def _require_name(self, name: str | None) -> None:
        if name is None and self.project_manifest.multi_host:
            raise ResourceNameRequiredError("host", "jd host list")

    def get_host_status(self, name: str | None = None) -> str:
        """Returns the status of the host machine."""
        self._require_name(name)
        command = self.project_manifest.get_command("host.status")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        cli_paramdefs: dict[str, ResolvedCliParameter[Any]] = {}
        if name is not None:
            cli_paramdefs["name"] = StrResolvedCliParameter(parameter_name="name", value=name)
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
        return runner.get_result_value(command, "host.status", str)

    def show_host(self, name: str) -> HostDetail:
        """Returns detailed information about a host."""
        command = self.project_manifest.get_command("host.show")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(
            command,
            cli_paramdefs={
                "name": StrResolvedCliParameter(parameter_name="name", value=name),
            },
        )
        results = collect_results(runner, command)
        return HostDetail(
            name=results.get("name", ""),
            status=results.get("status", ""),
            resource=results.get("resource", {}),
        )

    def _build_cli_paramdefs(self, name: str | None = None) -> dict[str, ResolvedCliParameter[Any]]:
        cli_paramdefs: dict[str, ResolvedCliParameter[Any]] = {}
        if name is not None:
            cli_paramdefs["name"] = StrResolvedCliParameter(parameter_name="name", value=name)
        return cli_paramdefs

    def stop_host(self, name: str | None = None) -> None:
        """Stop the host machine."""
        self._require_name(name)
        command = self.project_manifest.get_command("host.stop")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs=self._build_cli_paramdefs(name=name))

    def start_host(self, name: str | None = None) -> None:
        """Start the host machine."""
        self._require_name(name)
        command = self.project_manifest.get_command("host.start")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs=self._build_cli_paramdefs(name=name))

    def restart_host(self, name: str | None = None) -> None:
        """Restart the host machine."""
        self._require_name(name)
        command = self.project_manifest.get_command("host.restart")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs=self._build_cli_paramdefs(name=name))

    def get_connection_status(self) -> str:
        """Returns the Session Manager connection status of the host."""
        command = self.project_manifest.get_command("host.status-for-connection")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs={})
        return runner.get_result_value(command, "host.status-for-connection", str)

    def connect(self, name: str | None = None) -> None:
        """Start an SSH-style connection to the host."""
        self._require_name(name)
        command = self.project_manifest.get_command("host.connect")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs=self._build_cli_paramdefs(name=name))

    def exec_command(self, command_args: list[str], name: str | None = None) -> tuple[str, str, int]:
        """Execute a command on the host, return the stdout, stderr, and exit code."""
        self._require_name(name)
        command = self.project_manifest.get_command("host.exec")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        command_string = " ".join(command_args)
        cli_paramdefs = self._build_cli_paramdefs(name=name)
        cli_paramdefs["commands"] = ListStrResolvedCliParameter(parameter_name="commands", value=[command_string])
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
        stdout = runner.get_result_value(command, "host.exec.stdout", str)
        stderr = runner.get_result_value(command, "host.exec.stderr", str)
        returncode = runner.get_result_value_with_fallback(command, "host.exec.returncode", int, 0)
        return stdout, stderr, returncode
