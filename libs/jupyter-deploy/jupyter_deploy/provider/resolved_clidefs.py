from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

S = TypeVar("S")


class ResolvedCliParameter(BaseModel, Generic[S]):
    """Wrapper class for a value passed to a CLI command by the user."""

    model_config = ConfigDict(extra="allow")
    parameter_name: str
    value: S


class StrResolvedCliParameter(ResolvedCliParameter[str]):
    """Wrapper class for string value passed to a CLI command by the user."""

    pass


class IntResolvedCliParameter(ResolvedCliParameter[int]):
    """Wrapper class for int value passed to a CLI command by the user."""

    pass


class ListStrResolvedCliParameter(ResolvedCliParameter[list[str]]):
    """Wrapper class for list of strings value passed to a CLI command by the user."""

    pass
