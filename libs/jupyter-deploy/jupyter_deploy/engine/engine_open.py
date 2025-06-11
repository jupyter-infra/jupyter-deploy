from abc import ABC, abstractmethod


class EngineOpenHandler(ABC):
    """Abstract base class for engine-specific open handlers."""

    @abstractmethod
    def get_url(self) -> str:
        pass
