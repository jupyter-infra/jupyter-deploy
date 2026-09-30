import unittest
from pathlib import Path
from unittest.mock import ANY, Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.app import runner as app_runner
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.enum import TemplateSource
from jupyter_deploy.exceptions import (
    InvalidTemplateNameError,
    ProjectStoreNotFoundError,
    StoreTypeNotSpecifiedError,
    TemplateNotFoundError,
)
from jupyter_deploy.infrastructure.enum import AWSInfrastructureType

_INIT_HANDLER = "jupyter_deploy.cli.app.InitHandler"


class TestInitCommand(unittest.TestCase):
    def get_mock_project(self) -> Mock:
        mock_project = Mock()

        self.mock_may_export_to_project_path = Mock()
        self.mock_clear_project_path = Mock()
        self.mock_setup = Mock()

        self.mock_may_export_to_project_path.return_value = True

        mock_project.may_export_to_project_path = self.mock_may_export_to_project_path
        mock_project.clear_project_path = self.mock_clear_project_path
        mock_project.setup = self.mock_setup

        return mock_project

    @patch(_INIT_HANDLER)
    def test_init_command_no_args_default_to_terraform(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = self.get_mock_project()

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["init", "."])

        self.assertEqual(result.exit_code, 0, "init command should work")

        mock_handler_cls.assert_called_once_with(
            project_dir=Path("."),
            engine=EngineType.TERRAFORM,
            provider=None,
            infrastructure=None,
            template=None,
            display_manager=ANY,
        )

    @patch(_INIT_HANDLER)
    def test_init_command_passes_attributes_to_project(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = self.get_mock_project()

        runner = CliRunner()
        result = runner.invoke(
            app_runner.app,
            [
                "init",
                "--engine",
                "terraform",
                "--provider",
                "aws",
                "--infrastructure",
                "ec2",
                "--template",
                "other-template",
                "custom-dir",
            ],
        )

        self.assertEqual(result.exit_code, 0, "init command should work")

        mock_handler_cls.assert_called_once_with(
            project_dir=Path("custom-dir"),
            engine=EngineType.TERRAFORM,
            provider="aws",
            infrastructure="ec2",
            template="other-template",
            display_manager=ANY,
        )

    @patch(_INIT_HANDLER)
    def test_init_command_handles_short_options(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = self.get_mock_project()

        runner = CliRunner()
        result = runner.invoke(
            app_runner.app,
            ["init", "-E", "terraform", "-P", "aws", "-I", "ec2", "-T", "a-template", "custom-dir"],
        )

        self.assertEqual(result.exit_code, 0, "init command should work")

        mock_handler_cls.assert_called_once_with(
            project_dir=Path("custom-dir"),
            engine=EngineType.TERRAFORM,
            provider="aws",
            infrastructure="ec2",
            template="a-template",
            display_manager=ANY,
        )

    @patch(_INIT_HANDLER)
    def test_init_command_calls_project_methods(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = self.get_mock_project()

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["init", "."])

        self.assertEqual(result.exit_code, 0, "init command should work")
        self.mock_may_export_to_project_path.assert_called_once()
        self.mock_setup.assert_called_once()

    @patch(_INIT_HANDLER)
    def test_init_command_exits_on_project_conflict_without_overwrite(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = self.get_mock_project()
        self.mock_may_export_to_project_path.return_value = False

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["init", "."])

        self.assertEqual(result.exit_code, 0, "init command should work")
        self.mock_may_export_to_project_path.assert_called_once()
        self.mock_clear_project_path.assert_not_called()
        self.mock_setup.assert_not_called()

    @patch(_INIT_HANDLER)
    @patch("jupyter_deploy.cli.app.typer.confirm")
    def test_init_command_with_overwrite_and_user_confirms(self, mock_confirm: Mock, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = self.get_mock_project()
        self.mock_may_export_to_project_path.return_value = False
        mock_confirm.return_value = True

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["init", "--overwrite", "."])

        self.assertEqual(result.exit_code, 0, "init command should work")
        self.mock_may_export_to_project_path.assert_called_once()
        mock_confirm.assert_called_once()
        self.mock_setup.assert_called_once()

    @patch(_INIT_HANDLER)
    @patch("jupyter_deploy.cli.app.typer.confirm")
    def test_init_command_with_overwrite_and_user_declines(self, mock_confirm: Mock, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = self.get_mock_project()
        self.mock_may_export_to_project_path.return_value = False
        mock_confirm.return_value = False

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["init", "--overwrite", "."])

        self.assertEqual(result.exit_code, 0, "init command should work")
        self.mock_may_export_to_project_path.assert_called_once()
        mock_confirm.assert_called_once()
        self.mock_setup.assert_not_called()

    @patch(_INIT_HANDLER)
    @patch("jupyter_deploy.cli.app.typer.confirm")
    def test_init_command_with_overwrite_on_no_conflict(self, mock_confirm: Mock, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = self.get_mock_project()
        self.mock_may_export_to_project_path.return_value = True

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["init", "--overwrite", "."])

        self.assertEqual(result.exit_code, 0, "init command should work")
        self.mock_may_export_to_project_path.assert_called_once()
        mock_confirm.assert_not_called()
        self.mock_setup.assert_called_once()

    @patch("subprocess.run")
    def test_init_command_calls_help_when_no_path(self, mock_subprocess_run: Mock) -> None:
        mock_subprocess_run.return_value = Mock(returncode=0)

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["init"])

        self.assertEqual(result.exit_code, 1, "init command should exit with error when no path")
        mock_subprocess_run.assert_called_once_with(["jupyter", "deploy", "init", "--help"])


class TestInitResolvedTemplateNotice(unittest.TestCase):
    """The handler resolves the template; the CLI reports back any template the user never typed."""

    def get_mock_project(self, source: TemplateSource, template_name: str = "aws:ec2:jupyterlab") -> Mock:
        mock_project = Mock()
        mock_project.may_export_to_project_path = Mock(return_value=True)
        mock_project.setup = Mock()
        mock_project.template_name = template_name
        mock_project.template_source = source
        return mock_project

    @patch(_INIT_HANDLER)
    def test_notifies_when_the_built_in_default_settled_the_template(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = self.get_mock_project(TemplateSource.BUILT_IN)

        result = CliRunner().invoke(app_runner.app, ["init", "."])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("No template specified", result.output)
        self.assertIn("aws:ec2:jupyterlab", result.output)
        self.assertIn("aws:ec2:base", result.output)

    @patch(_INIT_HANDLER)
    def test_states_the_template_used_without_making_it_a_hint(self, mock_handler_cls: Mock) -> None:
        """Which template was used is a statement; only the line offering a command is a hint."""
        mock_handler_cls.return_value = self.get_mock_project(TemplateSource.BUILT_IN)

        result = CliRunner().invoke(app_runner.app, ["init", "."])

        stated = next(line for line in result.output.splitlines() if "No template specified" in line)
        self.assertNotIn("💡", stated)

    @patch(_INIT_HANDLER)
    def test_points_at_the_preference_flag_rather_than_a_template_to_copy(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = self.get_mock_project(TemplateSource.BUILT_IN)

        result = CliRunner().invoke(app_runner.app, ["init", "."])

        self.assertIn("To set a different template as default", result.output)
        self.assertIn("jd preferences set", result.output)
        self.assertIn("--default-template", result.output)

    @patch(_INIT_HANDLER)
    def test_stays_quiet_when_an_argument_settled_the_template(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = self.get_mock_project(TemplateSource.ARGUMENT)

        result = CliRunner().invoke(app_runner.app, ["init", ".", "--template", "aws:ec2:jupyterlab"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertNotIn("No template specified", result.output)

    @patch(_INIT_HANDLER)
    def test_reports_a_template_that_came_from_a_preference(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = self.get_mock_project(TemplateSource.PREFERENCES, "aws:ec2:base")

        result = CliRunner().invoke(app_runner.app, ["init", "."])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("No template specified", result.output)
        self.assertIn("aws:ec2:base", result.output)
        self.assertIn("from your preferences", result.output)

    @patch(_INIT_HANDLER)
    def test_a_preference_gets_one_line_without_the_built_in_notice(self, mock_handler_cls: Mock) -> None:
        """Somebody who set the preference needs no telling how to set it, nor what it replaced."""
        mock_handler_cls.return_value = self.get_mock_project(TemplateSource.PREFERENCES, "aws:ec2:base")

        result = CliRunner().invoke(app_runner.app, ["init", "."])

        self.assertNotIn("To set a different template as default", result.output)
        self.assertNotIn("built-in default template changed", result.output)

    @patch(_INIT_HANDLER)
    def test_reports_a_malformed_template_name(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.side_effect = InvalidTemplateNameError("ec2:base")

        result = CliRunner().invoke(app_runner.app, ["init", "."])

        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Invalid template name", result.output)


class TestInitRestoreCommand(unittest.TestCase):
    @patch(_INIT_HANDLER)
    def test_restore_from_calls_handler(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.restore.return_value = Path("/tmp/restored").resolve()

        runner = CliRunner()
        result = runner.invoke(
            app_runner.app,
            ["init", "/tmp/restored", "--restore-project", "tpl-abc123", "--store-type", "s3-only"],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        mock_handler_cls.restore.assert_called_once()
        call_kwargs = mock_handler_cls.restore.call_args.kwargs
        self.assertEqual(call_kwargs["project_dir"], Path("/tmp/restored"))
        self.assertEqual(call_kwargs["project_id"], "tpl-abc123")
        self.assertIsNone(call_kwargs["store_id"])
        self.assertIn("restored", result.output)

    @patch(_INIT_HANDLER)
    def test_restore_from_with_store_id(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.restore.return_value = Path("/tmp/restored").resolve()

        runner = CliRunner()
        result = runner.invoke(
            app_runner.app,
            [
                "init",
                "/tmp/restored",
                "--restore-project",
                "tpl-abc123",
                "--store-type",
                "s3-only",
                "--store-id",
                "my-bucket",
            ],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        call_kwargs = mock_handler_cls.restore.call_args.kwargs
        self.assertEqual(call_kwargs["store_id"], "my-bucket")

    def test_restore_without_path_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            app_runner.app,
            ["init", "--restore-project", "tpl-abc123", "--store-type", "s3-only"],
        )

        self.assertNotEqual(result.exit_code, 0)

    @patch(_INIT_HANDLER)
    def test_restore_forwards_no_store_type_for_the_handler_to_resolve(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.restore.return_value = Path("/tmp/restored").resolve()

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["init", "/tmp/restored", "--restore-project", "tpl-abc123"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIsNone(mock_handler_cls.restore.call_args.kwargs["store_type"])

    @patch(_INIT_HANDLER)
    def test_restore_reports_an_unresolved_store_type(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.restore.side_effect = StoreTypeNotSpecifiedError(["s3-only", "s3-ddb"])

        runner = CliRunner()
        result = runner.invoke(app_runner.app, ["init", "/tmp/restored", "--restore-project", "tpl-abc123"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("No store type specified", result.output)
        self.assertIn("jd preferences set --default-store-type", result.output)

    @patch(_INIT_HANDLER)
    def test_restore_from_store_not_found(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.restore.side_effect = ProjectStoreNotFoundError("No store found")

        runner = CliRunner()
        result = runner.invoke(
            app_runner.app,
            ["init", "/tmp/restored", "--restore-project", "tpl-abc123", "--store-type", "s3-only"],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("No store found", result.output)


class TestInitTemplateNotInstalled(unittest.TestCase):
    """The upgrade path: whoever has only the previous default installed must be told what to do."""

    @patch(_INIT_HANDLER)
    def test_names_the_package_to_install(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.side_effect = TemplateNotFoundError(
            template_name="aws:ec2:jupyterlab",
            engine="terraform",
            installed=["aws:ec2:base"],
            suggested_package="jupyter-deploy-tf-aws-ec2-jupyterlab",
        )

        result = CliRunner().invoke(app_runner.app, ["init", "."])

        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("is not installed", result.output)
        self.assertIn("uv add jupyter-deploy-tf-aws-ec2-jupyterlab", result.output)

    @patch(_INIT_HANDLER)
    def test_offers_an_installed_template_as_the_default(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.side_effect = TemplateNotFoundError(
            template_name="aws:ec2:jupyterlab",
            engine="terraform",
            installed=["aws:ec2:base"],
            suggested_package="jupyter-deploy-tf-aws-ec2-jupyterlab",
        )

        result = CliRunner().invoke(app_runner.app, ["init", "."])

        self.assertIn("Installed templates: aws:ec2:base", result.output)
        # The rendered command wraps, so match its parts rather than one line.
        self.assertIn("jd preferences set --default-template", result.output)
        self.assertIn("To default to a template you have", result.output)

    @patch(_INIT_HANDLER)
    def test_offers_no_default_when_nothing_is_installed(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.side_effect = TemplateNotFoundError(
            template_name="aws:ec2:jupyterlab",
            engine="terraform",
            installed=[],
            suggested_package="jupyter-deploy-tf-aws-ec2-jupyterlab",
        )

        result = CliRunner().invoke(app_runner.app, ["init", "."])

        self.assertIn("No template is installed", result.output)
        self.assertNotIn("jd preferences set", result.output)


class TestInitTemplateQualifiers(unittest.TestCase):
    """`--provider` / `--infrastructure` only name segments of a base-name `--template`."""

    def get_mock_project(self) -> Mock:
        mock_project = Mock()
        mock_project.may_export_to_project_path = Mock(return_value=True)
        mock_project.setup = Mock()
        mock_project.template_name = "aws:eks:oidc"
        mock_project.template_source = TemplateSource.ARGUMENT
        return mock_project

    @patch(_INIT_HANDLER)
    def test_qualifies_a_base_name(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = self.get_mock_project()

        result = CliRunner().invoke(app_runner.app, ["init", ".", "-I", "eks", "-T", "oidc"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(mock_handler_cls.call_args.kwargs["infrastructure"], AWSInfrastructureType.EKS)
        self.assertEqual(mock_handler_cls.call_args.kwargs["template"], "oidc")

    @patch(_INIT_HANDLER)
    def test_omitted_flags_are_forwarded_unresolved(self, mock_handler_cls: Mock) -> None:
        """The CLI reports what the user typed; the handler owns the default."""
        mock_handler_cls.return_value = self.get_mock_project()

        result = CliRunner().invoke(app_runner.app, ["init", ".", "-T", "base"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIsNone(mock_handler_cls.call_args.kwargs["provider"])
        self.assertIsNone(mock_handler_cls.call_args.kwargs["infrastructure"])

    @patch(_INIT_HANDLER)
    def test_refuses_infrastructure_with_no_template(self, mock_handler_cls: Mock) -> None:
        """`jd init . -I eks` used to scaffold an ec2 template, silently dropping the flag."""
        result = CliRunner().invoke(app_runner.app, ["init", ".", "-I", "eks"])

        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("--infrastructure cannot be applied", result.output)
        mock_handler_cls.assert_not_called()

    @patch(_INIT_HANDLER)
    def test_refuses_provider_with_no_template(self, mock_handler_cls: Mock) -> None:
        result = CliRunner().invoke(app_runner.app, ["init", ".", "-P", "aws"])

        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("--provider cannot be applied", result.output)
        mock_handler_cls.assert_not_called()

    @patch(_INIT_HANDLER)
    def test_names_both_flags_when_both_are_unusable(self, mock_handler_cls: Mock) -> None:
        result = CliRunner().invoke(app_runner.app, ["init", ".", "-P", "aws", "-I", "eks"])

        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("--provider and --infrastructure cannot be applied", result.output)

    @patch(_INIT_HANDLER)
    def test_refuses_a_qualifier_next_to_a_full_template_name(self, mock_handler_cls: Mock) -> None:
        result = CliRunner().invoke(app_runner.app, ["init", ".", "-T", "aws:ec2:base", "-I", "eks"])

        self.assertEqual(result.exit_code, 1, result.output)
        # The rendered reason wraps, so match its parts rather than one line.
        self.assertIn("--infrastructure cannot be applied", result.output)
        self.assertIn("aws:ec2:base", result.output)
        mock_handler_cls.assert_not_called()
