import json
import re
from enum import Enum

from jupyter_deploy.exceptions import InstructionNotFoundError, InvalidInstructionArgumentError, ResourceNotFoundError
from jupyter_deploy.provider.instruction_runner import InstructionRunner
from jupyter_deploy.provider.resolved_argdefs import (
    ListStrResolvedInstructionArgument,
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
    retrieve_optional_arg,
)
from jupyter_deploy.provider.resolved_resultdefs import (
    ListStrResolvedInstructionResult,
    ResolvedInstructionResult,
    StrResolvedInstructionResult,
)

_LIST_ARG_RE = re.compile(r"^list_(\d+)$")
_VALUE_ARG_RE = re.compile(r"^value_(\d+)$")
_FIELD_ARG_PREFIX = "field_"


class CoreInstruction(str, Enum):
    """Built-in combinator instructions accessible from manifest.commands[].sequence[].api-name."""

    CONCAT_LISTS_OF_STR = "concat-lists-of-str"
    COALESCE_STR = "coalesce-str"
    MATCH_NAME = "match-name"
    MAKE_JSON_OBJECT = "make-json-object"


class CoreInstructionRunner(InstructionRunner):
    """Runner for built-in, dependency-free command combinators.

    Combinators satisfy the standard InstructionRunner contract and consume inputs via the
    existing `source: result` argument path — they are "just instructions" from the runner's
    point of view. No cloud SDK, no credentials.
    """

    @staticmethod
    def _sub_instruction_name(instruction_name: str) -> str:
        # expect core.<instruction>
        parts = instruction_name.split(".")
        return ".".join(parts[1:]) if parts[0].lower() == "core" else instruction_name

    def _concat_lists_of_str(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        """Concatenate list_1, list_2, ... (in numeric order) into a single list of str.

        Each operand must be a ListStr (or absent → []). No dedup — it is a concat, not a
        set union. Any non-ListStr operand raises InvalidInstructionArgumentError.
        """
        names = sorted(
            (name for name in resolved_arguments if _LIST_ARG_RE.match(name)),
            key=lambda n: int(_LIST_ARG_RE.match(n).group(1)),  # type: ignore[union-attr]
        )
        concatenated: list[str] = []
        for name in names:
            arg = resolved_arguments[name]
            if not isinstance(arg, ListStrResolvedInstructionArgument):
                raise InvalidInstructionArgumentError(
                    f"concat-lists-of-str operand '{name}' must be a list of str, got {type(arg).__name__}"
                )
            concatenated.extend(arg.value)

        return {"Names": ListStrResolvedInstructionResult(result_name="Names", value=concatenated)}

    def _coalesce_str(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        """Return the first non-empty str operand (value_1, value_2, ... in priority order).

        Matches the SQL COALESCE / ?? contract: a skipped step (absent operand) and a step
        that ran but returned "" are both passed over. If every operand is empty, Value is "".

        Type-suffixed (`coalesce-str`) because "emptiness" is type-specific — this operates
        on str operands and str "" emptiness; a future `coalesce-list-of-str` would use [].
        """
        names = sorted(
            (name for name in resolved_arguments if _VALUE_ARG_RE.match(name)),
            key=lambda n: int(_VALUE_ARG_RE.match(n).group(1)),  # type: ignore[union-attr]
        )
        for name in names:
            arg = resolved_arguments[name]
            if not isinstance(arg, StrResolvedInstructionArgument):
                raise InvalidInstructionArgumentError(
                    f"coalesce-str operand '{name}' must be a str, got {type(arg).__name__}"
                )
            if arg.value:
                return {"Value": StrResolvedInstructionResult(result_name="Value", value=arg.value)}

        return {"Value": StrResolvedInstructionResult(result_name="Value", value="")}

    def _match_name(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        """Resolve the name of a resource a template has exactly one of, rejecting any other name.

        For a single-resource template (one EC2 host, one jupyter server) the name is fixed by the
        template rather than looked up, so a `name` the user typed can only be right or wrong. Wrong
        raises: answering for a resource that does not exist would report a confident status for it.
        An absent or empty `name` is not a mismatch: single-resource templates let users omit `--name`.

        Returns the expected name as `Name`.
        """
        expected = require_arg(resolved_arguments, "expected", StrResolvedInstructionArgument).value
        if not expected:
            raise InvalidInstructionArgumentError("match-name requires a non-empty 'expected' name")
        name = retrieve_optional_arg(resolved_arguments, "name", StrResolvedInstructionArgument, "").value
        kind = retrieve_optional_arg(resolved_arguments, "kind", StrResolvedInstructionArgument, "").value

        if name and name != expected:
            raise ResourceNotFoundError(kind or "resource", name, f"the only {kind or 'resource'} is '{expected}'")

        return {"Name": StrResolvedInstructionResult(result_name="Name", value=expected)}

    def _make_json_object(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        """Pack `field_<key>` str operands into one JSON object `{"<key>": value, ...}`.

        The manifest's results carry one scalar each, while a `show` payload is a single object; this
        assembles that object from values earlier steps produced. Keys keep their declaration order.
        """
        fields: dict[str, str] = {}
        for arg_name, arg in resolved_arguments.items():
            if not arg_name.startswith(_FIELD_ARG_PREFIX):
                continue
            key = arg_name.removeprefix(_FIELD_ARG_PREFIX)
            if not key:
                raise InvalidInstructionArgumentError(f"make-json-object operand '{arg_name}' has an empty key")
            if not isinstance(arg, StrResolvedInstructionArgument):
                raise InvalidInstructionArgumentError(
                    f"make-json-object operand '{arg_name}' must be a str, got {type(arg).__name__}"
                )
            fields[key] = arg.value.strip()

        return {"Value": StrResolvedInstructionResult(result_name="Value", value=json.dumps(fields))}

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        sub_instruction_name = CoreInstructionRunner._sub_instruction_name(instruction_name)
        try:
            instruction = CoreInstruction(sub_instruction_name)
        except ValueError:
            raise InstructionNotFoundError(f"Unknown core instruction: '{instruction_name}'") from None

        if instruction == CoreInstruction.CONCAT_LISTS_OF_STR:
            return self._concat_lists_of_str(resolved_arguments)
        elif instruction == CoreInstruction.COALESCE_STR:
            return self._coalesce_str(resolved_arguments)
        elif instruction == CoreInstruction.MATCH_NAME:
            return self._match_name(resolved_arguments)
        elif instruction == CoreInstruction.MAKE_JSON_OBJECT:
            return self._make_json_object(resolved_arguments)

        raise InstructionNotFoundError(f"Unknown core instruction: '{instruction_name}'")
