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

from jupyter_deploy.cli.error_decorator import handle_cli_errors, unsupported_command_message
from jupyter_deploy.exceptions import (
    CommandNotImplementedError,
    ManifestValueNotDeclaredError,
    OptionalParameterNotSupportedError,
    ProjectOutputsNotAvailableError,
    RequiredOutputNotFoundError,
    RequiredOutputTypeError,
    ResourceNameRequiredError,
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
