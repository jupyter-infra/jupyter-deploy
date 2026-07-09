from enum import Enum


class ProviderType(str, Enum):
    """Cloud provider types for template identity (e.g., jd init -P aws)."""

    AWS = "aws"


class ApiGroup(str, Enum):
    """API group for manifest instruction routing.

    Determines which instruction runner handles a given api-name prefix.
    Not to be confused with ProviderType which represents cloud providers
    for template identity (e.g., jd init -P aws).
    """

    AWS = "aws"
    K8S = "k8s"
    HELM = "helm"

    @classmethod
    def from_api_name(cls, api_name: str) -> "ApiGroup":
        """Return the ApiGroup matching the first segment of the api-name.

        Raises:
            ValueError: If no matching ApiGroup is found.
        """
        parts = api_name.split(".")
        source_lower = parts[0].lower()
        for source in cls:
            if source.value.lower() == source_lower:
                return source
        raise ValueError(f"No ApiGroup found for api name: {api_name}")
