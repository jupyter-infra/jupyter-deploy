from enum import Enum


class InstructionArgumentSource(str, Enum):
    """Enum to list the possible sources for an instruction argument."""

    TEMPLATE_OUTPUT = "output"
    CLI_ARGUMENT = "cli"
    INSTRUCTION_RESULT = "result"

    @classmethod
    def from_string(cls, source_str: str) -> "InstructionArgumentSource":
        """Return the enum value, ignoring case.

        Raises:
            ValueError: If no matching enum value is found.
        """
        source_lower = source_str.lower()
        for source in cls:
            if source.value.lower() == source_lower:
                return source
        raise ValueError(f"No InstructionArgumentSource found for '{source_str}'")


class ResultSource(str, Enum):
    """Enum to list the possible sources for an result."""

    TEMPLATE_OUTPUT = "output"
    INSTRUCTION_RESULT = "result"

    @classmethod
    def from_string(cls, source_str: str) -> "ResultSource":
        """Return the enum value, ignoring case.

        Raises:
            ValueError: If no matching enum value is found.
        """
        source_lower = source_str.lower()
        for source in cls:
            if source.value.lower() == source_lower:
                return source
        raise ValueError(f"No ResultSource found for '{source_str}'")


class ValueSource(str, Enum):
    """Enum to list the possible sources for a declared value."""

    TEMPLATE_OUTPUT = "output"

    @classmethod
    def from_string(cls, source_str: str) -> "ValueSource":
        """Return the enum value, ignoring case.

        Raises:
            ValueError: If no matching enum value is found.
        """
        source_lower = source_str.lower()
        for source in cls:
            if source.value.lower() == source_lower:
                return source
        raise ValueError(f"No ValueSource found for '{source_str}'")


class UpdateSource(str, Enum):
    """Enum to list the possible sources for an result."""

    INSTRUCTION_RESULT = "result"

    @classmethod
    def from_string(cls, source_str: str) -> "UpdateSource":
        """Return the enum value, ignoring case.

        Raises:
            ValueError: If no matching enum value is found.
        """
        source_lower = source_str.lower()
        for source in cls:
            if source.value.lower() == source_lower:
                return source
        raise ValueError(f"No UpdateSource found for '{source_str}'")


class TransformType(str, Enum):
    """List of transforms applicable to results value."""

    NO_TRANSFORM = "no-transform"
    COMMA_SEPARATED_STR_TO_LIST_STR = "comma-separated-str-to-list-str"

    @classmethod
    def from_string(cls, target_str: str | None) -> "TransformType":
        """Return the enum value, ignoring case, dashes and underlines.

        Raises:
            ValueError: If no matching enum value is found.
        """
        if not target_str:
            return cls.NO_TRANSFORM

        target_lower = target_str.lower()

        # first try to match lower case only
        for transform in cls:
            if transform.value.lower() == target_lower:
                return transform

        # then try to match without dashes or underlines
        repl_target = target_lower.replace("-", "").replace("_", "")
        for transform in cls:
            repl_transform = transform.value.lower().replace("-", "").replace("_", "")
            if repl_transform == repl_target:
                return transform

        raise ValueError(f"No transform found for '{target_str}'")


class JupyterDeployTool(str, Enum):
    """List of tools verifiable by jupyter deploy."""

    AWS_CLI = "aws-cli"
    AWS_SSM_PLUGIN = "aws-ssm-plugin"
    JQ = "jq"
    TERRAFORM = "terraform"

    @classmethod
    def from_string(cls, target_str: str) -> "JupyterDeployTool":
        """Return the enum value, ignoring case, dashes and underlines.

        Raises:
            ValueError: If no matching enum value is found.
        """
        target_lower = target_str.lower()

        # first try to match lower case only
        for source in cls:
            if source.value.lower() == target_lower:
                return source

        # then try to match without dashes or underlines
        repl_target = target_lower.replace("-", "").replace("_", "")
        for source in cls:
            repl_source = source.value.lower().replace("-", "").replace("_", "")
            if repl_source == repl_target:
                return source

        raise ValueError(f"No tool found for '{target_str}'")
