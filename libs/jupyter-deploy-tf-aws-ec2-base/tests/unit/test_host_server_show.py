"""Run this template's host/server list and show commands through the real command runner.

AWS runners are mocked; core.* runs for real, so these pin both the wiring (which step answers which
result) and the name validation that stops `--name <anything>` from describing the one host or server.
"""

import unittest
from typing import Any
from unittest.mock import Mock, patch

import yaml
from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import ResourceNotFoundError
from jupyter_deploy.handlers.resource.resource_utils import collect_results
from jupyter_deploy.manifest import JupyterDeployManifestV1
from jupyter_deploy.provider.core.core_runner import CoreInstructionRunner
from jupyter_deploy.provider.manifest_command_runner import ManifestCommandRunner
from jupyter_deploy.provider.resolved_clidefs import ResolvedCliParameter, StrResolvedCliParameter
from jupyter_deploy.provider.resolved_resultdefs import ListStrResolvedInstructionResult, StrResolvedInstructionResult

from jupyter_deploy_tf_aws_ec2_base.template import TEMPLATE_PATH

_FACTORY = "jupyter_deploy.provider.manifest_command_runner.InstructionRunnerFactory.get_provider_instruction_runner"
_INSTANCE_ID = "i-0123456789abcdef0"


class TestHostServerShow(unittest.TestCase):
    manifest: JupyterDeployManifestV1

    @classmethod
    def setUpClass(cls) -> None:
        with open(TEMPLATE_PATH / "manifest.yaml") as f:
            cls.manifest = JupyterDeployManifestV1(**yaml.safe_load(f))

    def _run(self, cmd_name: str, cli: dict[str, str] | None = None) -> tuple[Mock, dict[str, Any]]:
        """Return the AWS runner mock and the command's results keyed without the command prefix.

        A `.list` result is read as a list, the way the handlers read it; every other result goes
        through collect_results, the way `show` reads it.
        """
        output_handler = Mock()
        output_handler.get_full_project_outputs.return_value = {
            "instance_id": StrTemplateOutputDefinition(output_name="instance_id", value=_INSTANCE_ID),
            "server_status_check_document": StrTemplateOutputDefinition(
                output_name="server_status_check_document", value="status-doc"
            ),
        }
        aws_runner = Mock()
        aws_runner.execute_instruction.side_effect = lambda instruction_name, resolved_arguments: {
            "aws.ec2.describe-instance": {
                "Name": StrResolvedInstructionResult(result_name="Name", value=_INSTANCE_ID),
                "Names": ListStrResolvedInstructionResult(result_name="Names", value=[_INSTANCE_ID]),
                "Status": StrResolvedInstructionResult(result_name="Status", value="running"),
                "Resource": StrResolvedInstructionResult(
                    result_name="Resource", value='{"instance_type": "t3.medium"}'
                ),
            },
            "aws.ssm.wait-command-sync": {
                "StandardOutputContent": StrResolvedInstructionResult(
                    result_name="StandardOutputContent", value="IN_SERVICE\n"
                ),
            },
        }[instruction_name]
        core_runner = CoreInstructionRunner(NullDisplay())

        def fake_factory(api_name: str, *_args: object, **_kwargs: object) -> Any:
            if api_name.startswith("aws."):
                return aws_runner
            if api_name.startswith("core."):
                return core_runner
            raise AssertionError(f"unexpected api_name: {api_name}")

        cli_paramdefs: dict[str, ResolvedCliParameter[Any]] = {
            k: StrResolvedCliParameter(parameter_name=k, value=v) for k, v in (cli or {}).items()
        }
        command = self.manifest.get_command(cmd_name)
        with patch(_FACTORY, side_effect=fake_factory):
            runner = ManifestCommandRunner(
                display_manager=Mock(), output_handler=output_handler, variable_handler=Mock()
            )
            runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
        if cmd_name.endswith(".list"):
            return aws_runner, {"list": runner.get_result_value(command, cmd_name, list)}
        return aws_runner, collect_results(runner, command)

    def test_host_list_is_the_instance_id(self) -> None:
        aws_runner, results = self._run("host.list")
        self.assertEqual(results["list"], [_INSTANCE_ID])
        aws_runner.execute_instruction.assert_not_called()

    def test_host_show_describes_the_instance(self) -> None:
        _, results = self._run("host.show", {"name": _INSTANCE_ID})
        self.assertEqual(results["name"], _INSTANCE_ID)
        self.assertEqual(results["status"], "running")
        self.assertEqual(results["resource"], {"instance_type": "t3.medium"})

    def test_host_show_rejects_another_name_before_calling_aws(self) -> None:
        with self.assertRaises(ResourceNotFoundError) as ctx:
            self._run("host.show", {"name": "default"})
        self.assertEqual(str(ctx.exception), "host 'default' not found")

    def test_server_list_is_jupyter(self) -> None:
        aws_runner, results = self._run("server.list", {"scope": "default"})
        self.assertEqual(results["list"], ["jupyter"])
        aws_runner.execute_instruction.assert_not_called()

    def test_server_show_reports_host_and_status(self) -> None:
        _, results = self._run("server.show", {"name": "jupyter", "scope": "default"})
        self.assertEqual(results["name"], "jupyter")
        self.assertEqual(results["resource"], {"host": _INSTANCE_ID, "status": "IN_SERVICE"})

    def test_server_show_rejects_another_name_before_calling_aws(self) -> None:
        with self.assertRaises(ResourceNotFoundError) as ctx:
            self._run("server.show", {"name": "default", "scope": "default"})
        self.assertEqual(str(ctx.exception), "server 'default' not found")

    def test_server_name_matches_the_compose_service(self) -> None:
        """The server is named after the compose service that runs it; renaming one must rename both."""
        self.assertIn("jupyter", self.manifest.services or [])
        compose = (TEMPLATE_PATH / "services" / "docker-compose.yml.tftpl").read_text()
        self.assertIn("container_name: jupyter\n", compose)
