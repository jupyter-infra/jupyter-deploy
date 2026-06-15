"""Terraform-specific execution callback for prompt detection and context extraction."""

import json
import re
from typing import Any

from jupyter_deploy.engine.supervised_execution import CompletionContext, DisplayManager, InteractionContext
from jupyter_deploy.engine.supervised_execution_callback import EngineExecutionCallback, NoopExecutionCallback
from jupyter_deploy.engine.terraform.tf_enums import TerraformSequenceId

# Regex to strip ANSI escape codes from terraform output
# Example raw line: "  \x1b[1mEnter a value:\x1b[0m \x1b[0m"
# After stripping: "Enter a value:"
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

# Regex to extract a variable name from terraform's prompt context line
# Matches lines like "var.subdomain" or "  var.oauth_app_client_id"
VAR_NAME_RE = re.compile(r"var\.(\w+)")

# Regex to extract variable names from terraform validation error blocks.
# Terraform emits the variable name in several forms within error blocks:
#   ' 219: variable "subdomain" {'          (validation block, modern tf 1.5+)
#   '  on variables.tf line X, in variable "subdomain":'  (validation block, older tf)
#   'var.custom_tags declared at ...'       (type mismatch from -var-file)
VALIDATION_VAR_RE = re.compile(r'variable "(\w+)"')
VALIDATION_VAR_DECLARED_RE = re.compile(r"var\.(\w+)\s+declared at")


def _parse_hcl_interactive_value(raw: str) -> Any:
    """Parse a value entered interactively in a terraform prompt.

    Terraform accepts JSON-compatible syntax for collections in interactive prompts.
    This converts the raw string to a native Python type so it round-trips through YAML:
      - '["a", "b"]'   → list ["a", "b"]
      - '["a", "b",]'  → list ["a", "b"]  (HCL allows trailing commas)
      - '{"k": "v"}'   → dict {"k": "v"}
      - '[{"k":"v"}]'  → list of dicts
      - 'hello'        → str "hello"
      - ''             → str ""
    """
    stripped = raw.strip()
    if stripped.startswith("[") or stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            pass
        # HCL allows trailing commas — strip them and retry
        cleaned = re.sub(r",\s*([}\]])", r"\1", stripped)
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return raw
    return raw


class TerraformSupervisedExecutionCallback(EngineExecutionCallback):
    """Terraform-specific implementation of EngineExecutionCallback.

    Handles terraform-specific prompt detection and context extraction:
    - Detects "Enter a value:" prompts
    - Extracts variable descriptions for CONFIG commands
    - Extracts plan summaries for UP/DOWN commands
    """

    def __init__(self, display_manager: DisplayManager, sequence_id: TerraformSequenceId):
        """Initialize the terraform callback.

        Args:
            display_manager: Handler for terminal display
            sequence_id: The terraform command sequence being executed (CONFIG_INIT, UP_APPLY, etc.)
        """
        super().__init__(display_manager)
        self.sequence_id = sequence_id

        # Interactive variable capture: tracks values entered via terraform prompts.
        # _pending_var_name is set when we detect a var.X prompt; cleared when stdin responds.
        self._pending_var_name: str | None = None
        self._captured_variables: dict[str, Any] = {}

    @property
    def captured_variables(self) -> dict[str, Any]:
        """Return variables captured from interactive prompts (var_name → user input)."""
        return self._captured_variables

    def on_stdin_line(self, line: str) -> None:
        """Capture the user's response to a terraform variable prompt.

        Called by PromptHandler each time a line is forwarded from stdin to the
        subprocess. Associates the value with the pending variable name.

        HCL collections (lists/dicts) are parsed via JSON into native Python types
        so they round-trip correctly through YAML:
          '["a","b"]'           → ["a", "b"]
          '{"k": "v"}'         → {"k": "v"}
          '[{"k":"v"},{"k2":"v2"}]' → [{"k":"v"}, {"k2":"v2"}]

        Empty strings are captured as "" (valid for nullable variables).
        """
        if self._pending_var_name:
            value = line.rstrip("\n")
            parsed = _parse_hcl_interactive_value(value)
            self._captured_variables[self._pending_var_name] = parsed
            self._pending_var_name = None

    def handle_interaction(self, line: str) -> None:
        """Override to extract the variable name before delegating to parent.

        When a prompt is first detected, we scan the buffer for the var.X line
        and mark it as pending — the next on_stdin_line call will associate the
        user's input with this variable.
        """
        if not self._waiting_for_interaction:
            # First prompt line — extract variable name from buffer context
            var_name = self._extract_pending_var_name()
            if var_name:
                self._pending_var_name = var_name
        super().handle_interaction(line)

    def extract_failed_variable_names(self) -> list[str]:
        """Extract variable names from terraform validation error blocks.

        Scans the line buffer for "Invalid value for [input] variable" error
        headers, then extracts the variable name from the subsequent lines.
        Only captures variable-level validation failures — not check/precondition
        blocks (those reference resources, not variables).

        Terraform emits two header variants:
          "Error: Invalid value for variable"       — validation block failures
          "Error: Invalid value for input variable" — type mismatch errors

        Followed by:
          │  219: variable "subdomain" {           (modern terraform 1.5+)
          │   on variables.tf line X, in variable "subdomain":  (older)
        """
        failed_vars: list[str] = []
        in_variable_error_block = False

        for line in self._line_buffer:
            clean = ANSI_ESCAPE.sub("", line).strip()

            if "Invalid value for" in clean and "variable" in clean:
                in_variable_error_block = True
                continue

            if in_variable_error_block:
                match = VALIDATION_VAR_RE.search(clean) or VALIDATION_VAR_DECLARED_RE.search(clean)
                if match:
                    var_name = match.group(1)
                    if var_name not in failed_vars:
                        failed_vars.append(var_name)
                    in_variable_error_block = False

        return failed_vars

    def _extract_pending_var_name(self) -> str | None:
        """Scan the line buffer backwards for the most recent var.X line."""
        for i in range(len(self._line_buffer) - 1, -1, -1):
            clean_line = ANSI_ESCAPE.sub("", self._line_buffer[i])
            match = VAR_NAME_RE.search(clean_line)
            if match:
                return match.group(1)
        return None

    def _detect_interaction(self, line: str) -> bool:
        """Detect terraform prompts (cheap check).

        Terraform prompts for user input end with "Enter a value:".
        This applies to both variable prompts and confirmation prompts.

        Args:
            line: The current output line to check

        Returns:
            True if this line is a prompt, False otherwise
        """
        # Cheap check first: does the line contain the prompt text?
        if "Enter a value:" not in line:
            return False

        # Line contains prompt text - strip ANSI codes and confirm it ends with prompt
        clean_line = ANSI_ESCAPE.sub("", line).strip()
        return clean_line.endswith("Enter a value:")

    def _extract_interaction_context(self, line: str) -> InteractionContext:
        """Extract context to display for terraform prompts.

        Called when a prompt is detected. Extracts relevant context based
        on the command being executed.

        Args:
            line: The line that triggered the interaction (the prompt line)

        Returns:
            InteractionContext with relevant buffered lines
        """
        # Command-specific context extraction
        if self.sequence_id in [TerraformSequenceId.config_init, TerraformSequenceId.config_plan]:
            return self._extract_variable_context()
        elif self.sequence_id in [TerraformSequenceId.up_apply, TerraformSequenceId.down_destroy]:
            return self._extract_plan_summary_context()

        # Fallback: return last few lines (including prompt line)
        # Cap at buffer size to be defensive
        buffer_list = list(self._line_buffer)
        fallback_lines = min(10, self._line_buffer.maxlen or 10)
        return InteractionContext(lines=buffer_list[-fallback_lines:])

    def _extract_variable_context(self) -> InteractionContext:
        """Extract context for variable prompts.

        Looks backward in buffer for the most recent line starting with "var."
        and returns all lines from that point including the "Enter a value:"
        prompt line. This captures the full variable description that terraform
        displays before prompting.

        Returns:
            InteractionContext with variable description lines (including prompt line)
        """
        # Note: list() conversion is O(n) but acceptable here because:
        # 1. This method is only called when _detect_interaction() finds a prompt (rare)
        # 2. We need backwards search + slicing which deque doesn't efficiently support
        buffer_list = list(self._line_buffer)
        for i in range(len(buffer_list) - 1, -1, -1):
            # Strip ANSI codes before checking (terraform wraps var names in ANSI codes)
            clean_line = ANSI_ESCAPE.sub("", buffer_list[i])
            if clean_line.startswith("var."):
                # Return lines from var. including the prompt line
                return InteractionContext(lines=buffer_list[i:])

        # Fallback: return last 10 lines (including prompt line) if no var. found
        # Cap at buffer size to be defensive
        fallback_lines = min(10, self._line_buffer.maxlen or 10)
        return InteractionContext(lines=buffer_list[-fallback_lines:])

    def _extract_plan_summary_context(self) -> InteractionContext:
        """Extract context for confirmation prompts (up/down commands).

        Looks backward in buffer for the most recent line containing terraform's
        plan summary (e.g., "Plan: 5 to add, 0 to change, 3 to destroy") and
        returns all lines from that point including the "Enter a value:"
        prompt line.

        Returns:
            InteractionContext with plan summary lines (including prompt line)
        """
        # Note: list() conversion is O(n) but acceptable here because:
        # 1. This method is only called when _detect_interaction() finds a prompt (rare)
        # 2. We need backwards search + slicing which deque doesn't efficiently support
        buffer_list = list(self._line_buffer)
        for i in range(len(buffer_list) - 1, -1, -1):
            # Strip ANSI codes before checking (terraform wraps plan summary in ANSI codes)
            clean_line = ANSI_ESCAPE.sub("", buffer_list[i])
            if "Plan:" in clean_line and ("to add" in clean_line or "to destroy" in clean_line):
                # Return lines from Plan: including the prompt line
                return InteractionContext(lines=buffer_list[i:])

        # Fallback: return last 20 lines (including prompt line) if no Plan: found
        # Cap at buffer size to be defensive
        fallback_lines = min(20, self._line_buffer.maxlen or 20)
        return InteractionContext(lines=buffer_list[-fallback_lines:])

    def _is_interaction_complete(self, line: str) -> bool:
        """Detect if terraform interaction is complete.

        For terraform, interaction is complete when we receive any new line
        after a prompt. This indicates the user has responded and terraform
        has continued execution.

        Args:
            line: The current output line to check

        Returns:
            True (interaction always completes on next line after prompt)
        """
        # Any new line after a prompt means user has responded
        return True

    def get_completion_context(self) -> CompletionContext | None:
        """Return CompletionContext with lines to display, or None if no pattern found.

        Searches the line buffer for completion patterns (Plan:, Apply complete!)
        and returns relevant lines for display. Called after successful execution.
        """
        # Determine pattern and max lines based on sequence
        if self.sequence_id == TerraformSequenceId.config_plan:
            pattern = "Plan:"
            max_lines = 1
        elif self.sequence_id == TerraformSequenceId.up_apply:
            pattern = "Apply complete!"
            max_lines = 50
        else:
            return None  # No completion context for other sequences

        # Search backwards through buffer for the pattern
        buffer_list = list(self._line_buffer)
        for i in range(len(buffer_list) - 1, -1, -1):
            # Strip ANSI codes before checking
            clean_line = ANSI_ESCAPE.sub("", buffer_list[i])
            if pattern in clean_line:
                # Return from this line onwards, up to max_lines or end of buffer
                end_index = min(i + max_lines, len(buffer_list))
                return CompletionContext(lines=buffer_list[i:end_index])

        return None

    def on_execution_error(self, retcode: int) -> None:
        """Handle terraform execution failure by extracting error context.

        Searches backwards through buffer for the first line containing "Error: "
        and displays context from that point onwards. This provides better error
        visibility than showing just the last N lines, as terraform errors are
        typically prefixed with "Error: ".

        Falls back to default behavior (last 50 lines) if no "Error: " found.

        Args:
            retcode: The non-zero return code from the failed command
        """
        # Search backwards through buffer for first "Error: " line
        buffer_list = list(self._line_buffer)
        for i in range(len(buffer_list) - 1, -1, -1):
            # Strip ANSI codes before checking
            clean_line = ANSI_ESCAPE.sub("", buffer_list[i]).strip()
            if "Error: " in clean_line:
                # Found error line - extract from here to end (max 50 lines)
                end_index = min(i + 50, len(buffer_list))
                error_context = buffer_list[i:end_index]
                self._display_manager.display_error_context(error_context)
                return

        # Fallback: no "Error: " found, use default behavior
        super().on_execution_error(retcode)


class TerraformNoopExecutionCallback(NoopExecutionCallback):
    """No-op execution callback with terraform-specific prompt detection for verbose mode.

    Extends NoopExecutionCallback to add terraform prompt detection for stdin coordination.

    Does NOT support extract_failed_variable_names or interactive value capture —
    verbose mode is used by agents that pass values via flags/yaml and cannot
    respond to interactive prompts. Nullifying variables would leave them stuck.
    """

    def __init__(self, display_manager: DisplayManager) -> None:
        """Initialize with a display manager.

        Args:
            display_manager: DisplayManager for handling output
        """
        super().__init__(display_manager)

    def is_requesting_user_input(self, line: str) -> bool:
        """Detect terraform prompts for stdin coordination.

        Returns True if line ends with terraform's "Enter a value:" prompt,
        allowing PromptHandler to coordinate stdin/stdout properly.

        Args:
            line: The current output line to check

        Returns:
            True if this line is a terraform prompt, False otherwise
        """
        # Cheap check first: does the line contain the prompt text?
        if "Enter a value:" not in line:
            return False

        # Line contains prompt text - strip ANSI codes and confirm it ends with prompt
        clean_line = ANSI_ESCAPE.sub("", line).strip()
        return clean_line.endswith("Enter a value:")

    def handle_interaction(self, line: str) -> None:
        """Print prompt lines to stdout for verbose mode.

        When prompts are detected, they skip on_log_line() and go directly to
        handle_interaction(). We need to print them so they're visible.

        Args:
            line: The prompt line to display
        """
        if not line.endswith(" "):
            line = line + " "
        print(line, end="", flush=True)
