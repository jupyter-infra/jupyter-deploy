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
