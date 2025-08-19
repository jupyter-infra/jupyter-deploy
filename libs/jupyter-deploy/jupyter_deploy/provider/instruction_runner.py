from abc import ABC, abstractmethod

from rich import console as rich_console

from jupyter_deploy.provider.resolved_argdefs import ResolvedInstructionArgument
from jupyter_deploy.provider.resolved_resultdefs import ResolvedInstructionResult


class InterruptInstructionError(RuntimeError):
    """Error to indicate that the runner should interrupt the sequence."""

    pass


class InstructionRunner(ABC):
    """Abstract class to call provider APIs.

    Each provider should implement a runner class to manage sub-services
    runner classes.
    """

    @abstractmethod
    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
        console: rich_console.Console,
    ) -> dict[str, ResolvedInstructionResult]:
        return {}
