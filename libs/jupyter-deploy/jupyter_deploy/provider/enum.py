from enum import Enum


class ProviderType(str, Enum):
    """Enum to list the types of cloud providers."""

    AWS = "aws"

    @classmethod
    def from_api_name(cls, api_name: str) -> "ProviderType":
        """Return the enum value, ignoring case.

        Raises:
            ValueError: If no matching enum value is found.
        """
        parts = api_name.split(".")
        source_lower = parts[0].lower()
        for source in cls:
            if source.value.lower() == source_lower:
                return source
        raise ValueError(f"No ProviderType found for api name: {api_name}")
