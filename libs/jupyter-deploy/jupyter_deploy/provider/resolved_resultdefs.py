from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

S = TypeVar("S")


class ResolvedInstructionResult(BaseModel, Generic[S]):
    """Wrapper class for a value returned by a successful instruction."""

    model_config = ConfigDict(extra="allow")
    result_name: str
    value: S


class StrResolvedInstructionResult(ResolvedInstructionResult[str]):
    """Wrapper class for string value returned by a successful instruction."""

    pass


class IntResolvedInstructionResult(ResolvedInstructionResult[int]):
    """Wrapper class for int value returned by a successful instruction."""

    pass


class ListStrResolvedInstructionResult(ResolvedInstructionResult[list[str]]):
    """Wrapper class for list of strings value returned by a successful instruction."""

    pass
