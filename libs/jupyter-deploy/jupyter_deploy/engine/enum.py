from enum import Enum


class EngineType(str, Enum):
    """Enum to list the types of deployment engine."""

    TERRAFORM = "terraform"

    @classmethod
    def from_string(cls, source_str: str) -> "EngineType":
        """Return the enum value, ignoring case.

        Raises:
            ValueError: If no matching enum value is found.
        """
        source_lower = source_str.lower()
        for source in cls:
            if source.value.lower() == source_lower:
                return source
        raise ValueError(f"No EngineType found for '{source_str}'")
