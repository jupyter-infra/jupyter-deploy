from typing import Any

from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.exceptions import ResourceNameRequiredError
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.handlers.payloads import ServerDetail
from jupyter_deploy.handlers.resource.resource_utils import collect_results, evaluate_status_rules
from jupyter_deploy.provider import manifest_command_runner as cmd_runner
from jupyter_deploy.provider.resolved_clidefs import ResolvedCliParameter, StrResolvedCliParameter


class ServerHandler(BaseProjectHandler):
    """Handler class to directly interact with a jupyter server app."""

    _output_handler: EngineOutputsHandler

    def __init__(self, display_manager: DisplayManager) -> None:
        """Instantiate the Users handler."""
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

    def _resolve_scope(self, scope: str | None) -> str:
        """Return the scope, falling back to the manifest-declared default."""
        if scope:
            return scope
        try:
            scope_def = self._output_handler.get_declared_output_def(
                "server_default_scope", StrTemplateOutputDefinition
            )
            if scope_def.value:
                return scope_def.value
        except (NotImplementedError, KeyError, ValueError):
            pass
        return "default"

    def list_servers(
        self, scope: str | None = None, limit: int | None = None, continue_from: str | None = None
    ) -> tuple[list[str], str | None]:
        """Returns a list of server names and an optional continuation token."""
        resolved_scope = self._resolve_scope(scope)
        command = self.project_manifest.get_command("server.list")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        cli_paramdefs: dict[str, ResolvedCliParameter[Any]] = {
            "scope": StrResolvedCliParameter(parameter_name="scope", value=resolved_scope),
            "limit": StrResolvedCliParameter(parameter_name="limit", value=str(limit) if limit is not None else ""),
            "continue_from": StrResolvedCliParameter(parameter_name="continue_from", value=continue_from or ""),
        }
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
        names = runner.get_result_value(command, "server.list", list)
        next_token = runner.get_result_value_with_fallback(command, "server.list.next_token", str, "") or None
        return names, next_token

    def _require_name(self, name: str | None) -> None:
        if name is None and self.project_manifest.multi_server:
            raise ResourceNameRequiredError("server", "jd server list")

    def get_server_status(self, name: str | None = None, scope: str | None = None) -> str:
        """Sends an health check to the jupyter server app, return status."""
        self._require_name(name)
        resolved_scope = self._resolve_scope(scope)
        command = self.project_manifest.get_command("server.status")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        cli_paramdefs: dict[str, ResolvedCliParameter[Any]] = {
            "scope": StrResolvedCliParameter(parameter_name="scope", value=resolved_scope),
        }
        if name is not None:
            cli_paramdefs["name"] = StrResolvedCliParameter(parameter_name="name", value=name)
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)

        rules = self.project_manifest.server_status_rules
        if not rules:
            return runner.get_result_value(command, "server.status", str)

        resource_json = runner.get_result_value(command, "server.status.resource", str)
        return evaluate_status_rules(resource_json, rules)

    def show_server(self, name: str, scope: str | None = None) -> ServerDetail:
        """Returns detailed information about a server."""
        resolved_scope = self._resolve_scope(scope)
        command = self.project_manifest.get_command("server.show")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(
            command,
            cli_paramdefs={
                "name": StrResolvedCliParameter(parameter_name="name", value=name),
                "scope": StrResolvedCliParameter(parameter_name="scope", value=resolved_scope),
            },
        )
        results = collect_results(runner, command)
        return ServerDetail(name=results.get("name", ""), resource=results.get("resource", {}))

    def _build_cli_paramdefs(
        self,
        service: str | None = None,
        allow_all_services: bool = True,
        name: str | None = None,
        scope: str | None = None,
    ) -> dict[str, ResolvedCliParameter[Any]]:
        resolved_scope = self._resolve_scope(scope)
        cli_paramdefs: dict[str, ResolvedCliParameter[Any]] = {
            "scope": StrResolvedCliParameter(parameter_name="scope", value=resolved_scope),
        }
        if service is not None:
            validated_service = self.project_manifest.get_validated_service(service, allow_all=allow_all_services)
            cli_paramdefs["service"] = StrResolvedCliParameter(parameter_name="service", value=validated_service)
        if name is not None:
            cli_paramdefs["name"] = StrResolvedCliParameter(parameter_name="name", value=name)
        return cli_paramdefs

    def start_server(self, service: str, name: str | None = None, scope: str | None = None) -> None:
        """Start the server or workspace."""
        self._require_name(name)
        command = self.project_manifest.get_command("server.start")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        cli_paramdefs = self._build_cli_paramdefs(service=service, name=name, scope=scope)
        cli_paramdefs["action"] = StrResolvedCliParameter(parameter_name="action", value="start")
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)

    def stop_server(self, service: str, name: str | None = None, scope: str | None = None) -> None:
        """Stop the server or workspace."""
        self._require_name(name)
        command = self.project_manifest.get_command("server.stop")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        cli_paramdefs = self._build_cli_paramdefs(service=service, name=name, scope=scope)
        cli_paramdefs["action"] = StrResolvedCliParameter(parameter_name="action", value="stop")
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)

    def restart_server(self, service: str, name: str | None = None, scope: str | None = None) -> None:
        """Restart the server or workspace."""
        self._require_name(name)
        command = self.project_manifest.get_command("server.restart")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        cli_paramdefs = self._build_cli_paramdefs(service=service, name=name, scope=scope)
        cli_paramdefs["action"] = StrResolvedCliParameter(parameter_name="action", value="restart")
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)

    def get_server_logs(
        self, service: str, extra: list[str], name: str | None = None, scope: str | None = None
    ) -> tuple[str, str, int]:
        """Return the stdout, stderr, and exit code from the server logs command."""
        self._require_name(name)
        command = self.project_manifest.get_command("server.logs")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        cli_paramdefs = self._build_cli_paramdefs(service=service, allow_all_services=False, name=name, scope=scope)
        cli_paramdefs["extra"] = StrResolvedCliParameter(parameter_name="extra", value=" ".join(extra))
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
        stdout = runner.get_result_value(command, "server.logs", str)
        stderr = runner.get_result_value(command, "server.errors", str)
        returncode = runner.get_result_value_with_fallback(command, "server.logs.returncode", int, 0)
        return stdout, stderr, returncode

    def exec_command(
        self, service: str, command_args: list[str], name: str | None = None, scope: str | None = None
    ) -> tuple[str, str, int]:
        """Execute a command inside a service container, return the stdout, stderr, and exit code."""
        self._require_name(name)
        command = self.project_manifest.get_command("server.exec")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        command_string = " ".join(command_args)
        cli_paramdefs = self._build_cli_paramdefs(service=service, allow_all_services=False, name=name, scope=scope)
        cli_paramdefs["commands"] = StrResolvedCliParameter(parameter_name="commands", value=command_string)
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
        stdout = runner.get_result_value(command, "server.exec.stdout", str)
        stderr = runner.get_result_value(command, "server.exec.stderr", str)
        returncode = runner.get_result_value_with_fallback(command, "server.exec.returncode", int, 0)
        return stdout, stderr, returncode

    def connect(self, service: str, name: str | None = None, scope: str | None = None) -> None:
        """Start an interactive shell session inside a service container."""
        self._require_name(name)
        command = self.project_manifest.get_command("server.connect")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        cli_paramdefs = self._build_cli_paramdefs(service=service, allow_all_services=False, name=name, scope=scope)
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
