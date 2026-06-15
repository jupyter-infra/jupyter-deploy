"""Unit tests for interactive variable capture in terraform callbacks."""

import unittest
from collections import deque

from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.engine.terraform.tf_enums import TerraformSequenceId
from jupyter_deploy.engine.terraform.tf_supervised_execution_callback import (
    TerraformSupervisedExecutionCallback,
    _parse_hcl_interactive_value,
)


class TestParseHclInteractiveValue(unittest.TestCase):
    def test_scalar_string(self) -> None:
        self.assertEqual(_parse_hcl_interactive_value("hello"), "hello")

    def test_empty_string(self) -> None:
        self.assertEqual(_parse_hcl_interactive_value(""), "")

    def test_string_with_whitespace(self) -> None:
        self.assertEqual(_parse_hcl_interactive_value("  hello  "), "  hello  ")

    def test_list_of_strings(self) -> None:
        result = _parse_hcl_interactive_value('["team-a", "team-b"]')
        self.assertEqual(result, ["team-a", "team-b"])

    def test_empty_list(self) -> None:
        result = _parse_hcl_interactive_value("[]")
        self.assertEqual(result, [])

    def test_dict(self) -> None:
        result = _parse_hcl_interactive_value('{"key": "value"}')
        self.assertEqual(result, {"key": "value"})

    def test_empty_dict(self) -> None:
        result = _parse_hcl_interactive_value("{}")
        self.assertEqual(result, {})

    def test_list_of_dicts(self) -> None:
        result = _parse_hcl_interactive_value('[{"name": "ebs1", "mount_point": "data"}]')
        self.assertEqual(result, [{"name": "ebs1", "mount_point": "data"}])

    def test_list_of_dicts_multiple(self) -> None:
        raw = '[{"name": "a", "size": "50"}, {"name": "b", "size": "100"}]'
        result = _parse_hcl_interactive_value(raw)
        self.assertEqual(result, [{"name": "a", "size": "50"}, {"name": "b", "size": "100"}])

    def test_trailing_comma_list(self) -> None:
        result = _parse_hcl_interactive_value('["a", "b",]')
        self.assertEqual(result, ["a", "b"])

    def test_trailing_comma_dict(self) -> None:
        result = _parse_hcl_interactive_value('{"k": "v",}')
        self.assertEqual(result, {"k": "v"})

    def test_trailing_comma_list_of_dicts(self) -> None:
        result = _parse_hcl_interactive_value('[{"name": "a",}, {"name": "b",},]')
        self.assertEqual(result, [{"name": "a"}, {"name": "b"}])

    def test_invalid_json_returns_raw(self) -> None:
        result = _parse_hcl_interactive_value("[not valid json")
        self.assertEqual(result, "[not valid json")

    def test_invalid_dict_json_returns_raw(self) -> None:
        result = _parse_hcl_interactive_value("{broken")
        self.assertEqual(result, "{broken")

    def test_nested_structure(self) -> None:
        raw = '[{"tags": {"env": "prod"}}]'
        result = _parse_hcl_interactive_value(raw)
        self.assertEqual(result, [{"tags": {"env": "prod"}}])


class TestInteractiveVariableCapture(unittest.TestCase):
    def _create_callback(self) -> TerraformSupervisedExecutionCallback:
        return TerraformSupervisedExecutionCallback(
            display_manager=NullDisplay(),
            sequence_id=TerraformSequenceId.config_plan,
        )

    def test_captures_scalar_value(self) -> None:
        callback = self._create_callback()

        # Simulate: terraform outputs "var.subdomain", then "Enter a value:"
        # The line buffer accumulates these lines before handle_interaction fires
        callback._line_buffer = deque(["var.subdomain", "  The subdomain...", "  Enter a value:"])
        callback.handle_interaction("  Enter a value:")

        # User types a response
        callback.on_stdin_line("my-subdomain\n")

        self.assertEqual(callback.captured_variables, {"subdomain": "my-subdomain"})

    def test_captures_empty_string(self) -> None:
        callback = self._create_callback()
        callback._line_buffer = deque(["var.oauth_allowed_org", "  Enter a value:"])
        callback.handle_interaction("  Enter a value:")

        callback.on_stdin_line("\n")

        self.assertEqual(callback.captured_variables, {"oauth_allowed_org": ""})

    def test_captures_list_value(self) -> None:
        callback = self._create_callback()
        callback._line_buffer = deque(["var.oauth_allowed_teams", "  Enter a value:"])
        callback.handle_interaction("  Enter a value:")

        callback.on_stdin_line('["team-a", "team-b"]\n')

        self.assertEqual(callback.captured_variables, {"oauth_allowed_teams": ["team-a", "team-b"]})

    def test_captures_list_of_dicts(self) -> None:
        callback = self._create_callback()
        callback._line_buffer = deque(["var.additional_ebs_mounts", "  Enter a value:"])
        callback.handle_interaction("  Enter a value:")

        callback.on_stdin_line('[{"name": "ebs1", "mount_point": "data", "size_gb": "50"}]\n')

        self.assertEqual(
            callback.captured_variables,
            {"additional_ebs_mounts": [{"name": "ebs1", "mount_point": "data", "size_gb": "50"}]},
        )

    def test_captures_multiple_variables(self) -> None:
        callback = self._create_callback()

        # First variable
        callback._line_buffer = deque(["var.domain", "  Enter a value:"])
        callback.handle_interaction("  Enter a value:")
        callback.on_stdin_line("example.com\n")

        # Reset interaction state (parent sets _waiting_for_interaction = False after next line)
        callback._waiting_for_interaction = False

        # Second variable
        callback._line_buffer.extend(["var.subdomain", "  Enter a value:"])
        callback.handle_interaction("  Enter a value:")
        callback.on_stdin_line("my-sub\n")

        self.assertEqual(callback.captured_variables, {"domain": "example.com", "subdomain": "my-sub"})

    def test_no_capture_without_prompt(self) -> None:
        callback = self._create_callback()

        # on_stdin_line without a pending var name should be a no-op
        callback.on_stdin_line("random input\n")

        self.assertEqual(callback.captured_variables, {})

    def test_var_name_extracted_with_ansi_codes(self) -> None:
        callback = self._create_callback()

        # Terraform wraps var names in ANSI codes
        callback._line_buffer = deque(["\x1b[1mvar.region\x1b[0m", "  Enter a value:"])
        callback.handle_interaction("  Enter a value:")
        callback.on_stdin_line("us-west-2\n")

        self.assertEqual(callback.captured_variables, {"region": "us-west-2"})


class TestExtractFailedVariableNames(unittest.TestCase):
    def _create_callback(self) -> TerraformSupervisedExecutionCallback:
        return TerraformSupervisedExecutionCallback(
            display_manager=NullDisplay(),
            sequence_id=TerraformSequenceId.config_plan,
        )

    def test_single_validation_error(self) -> None:
        callback = self._create_callback()
        callback._line_buffer = deque(
            [
                "╷",
                "│ Error: Invalid value for variable",
                "│ ",
                '│   on variables.tf line 230, in variable "subdomain":',
                "│  230:   validation {",
                "│ ",
                "│ The subdomain must only contain letters, numbers, dots, and hyphens.",
                "╵",
            ]
        )
        self.assertEqual(callback.extract_failed_variable_names(), ["subdomain"])

    def test_multiple_validation_errors(self) -> None:
        callback = self._create_callback()
        callback._line_buffer = deque(
            [
                "│ Error: Invalid value for variable",
                '│   on variables.tf line 150, in variable "domain":',
                "│ The domain must not be empty.",
                "│ Error: Invalid value for variable",
                '│   on variables.tf line 230, in variable "subdomain":',
                "│ The subdomain must only contain letters.",
            ]
        )
        self.assertEqual(callback.extract_failed_variable_names(), ["domain", "subdomain"])

    def test_no_validation_errors(self) -> None:
        callback = self._create_callback()
        callback._line_buffer = deque(
            [
                "│ Error: Resource precondition failed",
                '│   on main.tf line 160, in resource "terraform_data" "caller_access_check":',
                "│ The caller role must be listed in admin_role_names.",
            ]
        )
        self.assertEqual(callback.extract_failed_variable_names(), [])

    def test_deduplicates_variable_names(self) -> None:
        callback = self._create_callback()
        # Same variable can fail multiple validations
        callback._line_buffer = deque(
            [
                "│ Error: Invalid value for variable",
                '│   on variables.tf line 150, in variable "s3_bucket_prefix":',
                "│ The s3_bucket_prefix must contain only lowercase.",
                "│ Error: Invalid value for variable",
                '│   on variables.tf line 157, in variable "s3_bucket_prefix":',
                "│ The s3_bucket_prefix cannot start or end with a hyphen.",
            ]
        )
        self.assertEqual(callback.extract_failed_variable_names(), ["s3_bucket_prefix"])

    def test_with_ansi_codes(self) -> None:
        callback = self._create_callback()
        callback._line_buffer = deque(
            [
                "\x1b[1m│\x1b[0m Error: Invalid value for variable",
                '\x1b[1m│\x1b[0m   on variables.tf line 230, in variable "subdomain":',
            ]
        )
        self.assertEqual(callback.extract_failed_variable_names(), ["subdomain"])

    def test_modern_terraform_format(self) -> None:
        """Modern terraform (1.9+) shows the variable definition line."""
        callback = self._create_callback()
        callback._line_buffer = deque(
            [
                "│ Error: Invalid value for variable",
                "│ ",
                "│   on variables.tf line 219:",
                '│  219: variable "subdomain" {',
                "│     ├────────────────",
                '│     │ var.subdomain is "bad_subdomain"',
                "│ ",
                "│ The subdomain must only contain letters, numbers, dots, and hyphens.",
            ]
        )
        self.assertEqual(callback.extract_failed_variable_names(), ["subdomain"])

    def test_ignores_variable_outside_error_block(self) -> None:
        """Lines with 'variable "X"' outside an error block are ignored."""
        callback = self._create_callback()
        callback._line_buffer = deque(
            [
                "Terraform will perform the following actions:",
                "  # module.network.aws_route53_record.subdomain will be created",
                '  + resource "aws_route53_record" "subdomain" {',
                "│ Error: Invalid value for variable",
                '│  219: variable "domain" {',
            ]
        )
        self.assertEqual(callback.extract_failed_variable_names(), ["domain"])

    def test_type_mismatch_from_varfile(self) -> None:
        """Type mismatch errors use 'var.X declared at' format."""
        callback = self._create_callback()
        callback._line_buffer = deque(
            [
                "│ Error: Invalid value for input variable",
                "│ ",
                "│   on jdinputs.staging.auto.tfvars line 1:",
                '│    1: custom_tags = [{"Key" = "key"}]',
                "│ ",
                "│ The given value is not suitable for var.custom_tags declared at",
                "│ variables.tf:385,1-23: map of string required.",
            ]
        )
        self.assertEqual(callback.extract_failed_variable_names(), ["custom_tags"])

    def test_mixed_validation_and_type_errors(self) -> None:
        """Both validation block failures and type mismatches are captured."""
        callback = self._create_callback()
        callback._line_buffer = deque(
            [
                "│ Error: Invalid value for variable",
                '│  219: variable "subdomain" {',
                "│ The subdomain must only contain letters.",
                "│ Error: Invalid value for input variable",
                "│ The given value is not suitable for var.custom_tags declared at",
                "│ variables.tf:385,1-23: map of string required.",
            ]
        )
        self.assertEqual(callback.extract_failed_variable_names(), ["subdomain", "custom_tags"])
