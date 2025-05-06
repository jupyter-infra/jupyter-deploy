from enum import Enum


class EngineType(str, Enum):
    """Enum to list the types of deployment engine."""

    TERRAFORM = "terraform"
