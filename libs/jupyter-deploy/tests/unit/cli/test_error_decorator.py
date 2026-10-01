"""Unit tests for the CLI error handling context manager.

These assert the contract, not the copy: that the values a caller passed to the exception reach
the user, that each error offers the remedy it should (and withholds the ones it should not), and
that errors which must read differently do. Pinning whole sentences here would turn every wording
change into a test edit without catching anything a reader would call a bug.
"""

import unittest

import typer
from rich.console import Console
from typer.testing import CliRunner

from jupyter_deploy.cli.error_decorator import (
    handle_cli_errors,
    handle_connect_info_errors,
    unsupported_command_message,
)
from jupyter_deploy.constants import RETRYABLE_EXIT_CODE
from jupyter_deploy.enum import ProviderType
from jupyter_deploy.exceptions import (
    CommandNotImplementedError,
    InvalidProviderCredentialsError,
    InvalidVariableTypeError,
    JupyterDeployError,
    ManifestValueNotDeclaredError,
    OptionalParameterNotSupportedError,
    ProjectOutputsNotAvailableError,
    ProviderPermissionError,
    RequiredOutputNotFoundError,
    RequiredOutputTypeError,
    ResourceNameRequiredError,
    TransientProviderError,
)


def _app_raising(error: Exception) -> typer.Typer:
    """Return a 2-command app whose commands all raise the error inside the error handler."""
    app = typer.Typer()
    pool_app = typer.Typer()
    app.add_typer(pool_app, name="pool")

    @app.command()
    def config() -> None:
        with handle_cli_errors(Console(width=200)):
            raise error

    @pool_app.command()
    def show() -> None:
        with handle_cli_errors(Console(width=200)):
            raise error

    return app


def _render(error: Exception, argv: list[str]) -> str:
    """Return what the CLI prints when `error` escapes the given command."""
    result = CliRunner().invoke(_app_raising(error), argv)
    assert result.exit_code == 1, f"Expected a non-zero exit, got {result.exit_code}: {result.output}"
    assert "Traceback" not in result.output, f"A handled error must not print a traceback: {result.output}"
    return result.output


class TestUnsupportedCommandMessage(unittest.TestCase):
    """Test cases for the CommandNotImplementedError message."""

    def test_names_the_invoked_command_not_the_manifest_command(self) -> None:
        output = _render(CommandNotImplementedError("pool.status"), ["pool", "show"])

        # What the user typed, minus the program name -- not the manifest identifier behind it.
        self.assertIn("pool show", output)
        self.assertNotIn("pool.status", output)
        self.assertNotIn("root", output)

    def test_names_both_when_the_capability_belongs_to_another_command(self) -> None:
        output = _render(CommandNotImplementedError("secret.reveal"), ["config"])

        # The user typed `config`, but the missing capability is not config's own: name both,
        # otherwise the message blames a command that works.
        self.assertIn("config", output)
        self.assertIn("secret.reveal", output)

    def test_falls_back_to_the_manifest_command_outside_a_cli_invocation(self) -> None:
        message = unsupported_command_message(CommandNotImplementedError("pool.status"))

        self.assertIn("pool.status", message)


class TestRequiredOutputErrors(unittest.TestCase):
    """Test cases for outputs a command depends on but cannot resolve.

    Two of the four are worth re-deploying for; the other two are not, and the four must not all
    read the same, or the user cannot tell which situation they are in.
    """

    def test_no_outputs_at_all_points_at_deploying_the_project(self) -> None:
        output = _render(ProjectOutputsNotAvailableError("deployment_id"), ["config"])

        self.assertIn("deployment_id", output)
        self.assertIn("jd up", output)

    def test_missing_output_points_at_re_applying_the_template(self) -> None:
        output = _render(RequiredOutputNotFoundError("deployment_id"), ["config"])

        self.assertIn("deployment_id", output)
        self.assertIn("jd up", output)

    def test_an_empty_project_reads_differently_from_a_stale_one(self) -> None:
        empty = _render(ProjectOutputsNotAvailableError("deployment_id"), ["config"])
        stale = _render(RequiredOutputNotFoundError("deployment_id"), ["config"])

        # Both suggest deploying, so the wording is the only thing telling the user whether the
        # project was never deployed or no longer matches its template.
        self.assertNotEqual(empty, stale)

    def test_output_type_error_reports_both_types_and_offers_no_retry(self) -> None:
        error = RequiredOutputTypeError(
            output_name="deployment_id",
            expected_type="StrTemplateOutputDefinition",
            actual_type="ListStrTemplateOutputDefinition",
        )

        output = _render(error, ["config"])

        self.assertIn("deployment_id", output)
        self.assertIn("StrTemplateOutputDefinition", output)
        self.assertIn("ListStrTemplateOutputDefinition", output)
        # A template bug: re-deploying cannot change the declared type.
        self.assertNotIn("jd up", output)

    def test_value_not_declared_offers_no_remedy(self) -> None:
        output = _render(ManifestValueNotDeclaredError("open_url"), ["config"])

        self.assertIn("open_url", output)
        # Nothing the user can do to this project fixes it, and creating a fresh one is not a fix.
        self.assertNotIn("jd init", output)
        self.assertNotIn("jd up", output)


class TestInvalidVariableType(unittest.TestCase):
    """Test cases for a variables.yaml value whose type does not match the template's declaration."""

    def test_reports_the_variable_the_reason_and_where_to_fix_it(self) -> None:
        error = InvalidVariableTypeError(
            variable_name="oauth_allowed_teams",
            value="my-org:my-team",
            details=["Input should be a valid list, got: str"],
        )

        output = _render(error, ["config"])

        self.assertIn("oauth_allowed_teams", output)
        self.assertIn("my-org:my-team", output)
        # Without the reason the user cannot tell what shape the value should have taken.
        self.assertIn("Input should be a valid list", output)
        self.assertIn("variables.yaml", output)

    def test_reports_every_offending_part_of_the_value(self) -> None:
        error = InvalidVariableTypeError(
            variable_name="workspace_nodepools",
            value=[{"name": {}}, {"disk_size_gb": 50}],
            details=[
                "at [0].name: Input should be a valid string, got: dict",
                "at [1].disk_size_gb: Input should be a valid string, got: int",
            ],
        )

        output = _render(error, ["config"])

        self.assertIn("[0].name", output)
        self.assertIn("[1].disk_size_gb", output)


class TestOptionalParameterNotSupported(unittest.TestCase):
    """Test cases for a flag the template cannot honour, e.g. `jd open --server-name`."""

    def test_reports_the_parameter_and_what_supports_it(self) -> None:
        output = _render(OptionalParameterNotSupportedError("--server-name", "multi-app templates"), ["config"])

        # Both values come from the caller, so this holds for any future parameter.
        self.assertIn("--server-name", output)
        self.assertIn("multi-app templates", output)

    def test_does_not_disown_the_command_itself(self) -> None:
        unsupported_param = _render(
            OptionalParameterNotSupportedError("--server-name", "multi-app templates"), ["config"]
        )
        unsupported_command = _render(CommandNotImplementedError("config"), ["config"])

        # The bug this guards: a flag-only gap rendered as "this command is not supported".
        self.assertNotEqual(unsupported_param, unsupported_command)


class TestResourceNameRequired(unittest.TestCase):
    """Test cases for a resource command run without a name on a multi-resource template."""

    def test_reports_the_resource_the_flag_and_the_list_command(self) -> None:
        output = _render(ResourceNameRequiredError("host", "jd host list"), ["config"])

        self.assertIn("host", output)
        self.assertIn("--name", output)
        self.assertIn("jd host list", output)

    def test_names_the_flag_once(self) -> None:
        output = _render(ResourceNameRequiredError("host", "jd host list"), ["config"])

        # The message names the flag; a hint repeating it told the user the same thing twice.
        self.assertEqual(output.count("--name"), 1, f"Expected --name once, got: {output}")


def _connect_info_exit_code(error: Exception) -> int:
    """Return the exit code `jd proxy connect-info` reports for the given failure."""
    app = typer.Typer()

    @app.command()
    def connect_info() -> None:
        with handle_connect_info_errors(Console(width=200)):
            raise error

    return CliRunner().invoke(app, []).exit_code


class TestConnectInfoErrorClassification(unittest.TestCase):
    """The verdict `jd proxy connect-info` hands the client proxy, via its exit code.

    The proxy re-execs this command to refresh its credential and reads the exit code to decide
    whether to keep serving: RETRYABLE_EXIT_CODE means "keep the tunnel up and try again", anything
    else non-zero means "give up and shut down". Misclassifying a transient fault as permanent
    therefore kills a working proxy, so the default has to be retryable.
    """

    def test_expired_credentials_are_permanent(self) -> None:
        # The case that makes self-shutdown worth having: creds expired overnight, no retry helps.
        code = _connect_info_exit_code(InvalidProviderCredentialsError(ProviderType.AWS, "ExpiredToken"))

        self.assertEqual(code, 1)

    def test_denied_permission_is_permanent(self) -> None:
        code = _connect_info_exit_code(ProviderPermissionError(ProviderType.AWS, "sts:GetCallerIdentity", "denied"))

        self.assertEqual(code, 1)

    def test_undeployed_project_is_permanent(self) -> None:
        code = _connect_info_exit_code(ProjectOutputsNotAvailableError("no outputs"))

        self.assertEqual(code, 1)

    def test_template_without_the_command_is_permanent(self) -> None:
        code = _connect_info_exit_code(CommandNotImplementedError("proxy.connect-info"))

        self.assertEqual(code, 1)

    def test_transient_provider_error_is_retryable(self) -> None:
        code = _connect_info_exit_code(TransientProviderError(ProviderType.AWS, "ec2:DescribeInstances", "throttled"))

        self.assertEqual(code, RETRYABLE_EXIT_CODE)

    def test_network_failure_is_retryable(self) -> None:
        code = _connect_info_exit_code(ConnectionResetError("connection reset by peer"))

        self.assertEqual(code, RETRYABLE_EXIT_CODE)

    def test_unclassified_error_defaults_to_retryable(self) -> None:
        # The default this whole classification rests on: an error nobody has classified must not be
        # allowed to take a running proxy down with it. Adding a class to
        # PERMANENT_CONNECT_INFO_ERRORS is the only way to reach exit 1.
        code = _connect_info_exit_code(RuntimeError("something nobody anticipated"))

        self.assertEqual(code, RETRYABLE_EXIT_CODE)

    def test_unlisted_jupyter_deploy_error_defaults_to_retryable(self) -> None:
        # Being one of our own exceptions is not enough to be treated as permanent — a class added
        # later inherits the safe verdict rather than silently gaining the power to kill a proxy.
        code = _connect_info_exit_code(JupyterDeployError("a newly added failure"))

        self.assertEqual(code, RETRYABLE_EXIT_CODE)

    def test_permanent_error_keeps_its_operator_facing_message(self) -> None:
        # A human debugging this runs the command directly, so the permanent path must still read
        # like every other command's error rather than a bare stack trace.
        app = typer.Typer()

        @app.command()
        def connect_info() -> None:
            with handle_connect_info_errors(Console(width=200)):
                raise CommandNotImplementedError("proxy.connect-info")

        result = CliRunner().invoke(app, [])

        self.assertIn("proxy.connect-info", result.output)

    def test_retryable_error_says_it_will_be_retried(self) -> None:
        app = typer.Typer()

        @app.command()
        def connect_info() -> None:
            with handle_connect_info_errors(Console(width=200)):
                raise TransientProviderError(ProviderType.AWS, "ec2:DescribeInstances", "Rate exceeded")

        result = CliRunner().invoke(app, [])

        self.assertIn("Rate exceeded", result.output)
        self.assertIn("retry", result.output)

    def test_success_is_left_alone(self) -> None:
        app = typer.Typer()

        @app.command()
        def connect_info() -> None:
            with handle_connect_info_errors(Console(width=200)):
                pass

        self.assertEqual(CliRunner().invoke(app, []).exit_code, 0)
