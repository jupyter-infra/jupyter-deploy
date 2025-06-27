from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition, TemplateOutputDefinition

S = TypeVar("S")


class ResolvedInstructionArgument(BaseModel, Generic[S]):
    """Wrapper class for a resolved value passed to instruction.

    The resolved value may come from the CLI arguments, project outputs,
    or results from other instructions.
    """

    model_config = ConfigDict(extra="allow")
    argument_name: str
    value: S


class StrResolvedInstructionArgument(ResolvedInstructionArgument[str]):
    """Wrapper class for a resolved value of type str passed to instruction."""

    pass


class ListStrResolvedInstructionArgument(ResolvedInstructionArgument[list[str]]):
    """Wrapper class for a resolved value of type list[str] passed to instruction."""

    pass


RIA = TypeVar("RIA", bound=ResolvedInstructionArgument)


def resolve_output_argdef(
    outdefs: dict[str, TemplateOutputDefinition], arg_name: str, source_key: str
) -> ResolvedInstructionArgument:
    """Instantiates the resolved argdef of the corresponding type."""

    if source_key not in outdefs:
        raise KeyError(f"Output name not found in outputs: {source_key}")
    outdef = outdefs[source_key]
    if isinstance(outdef, StrTemplateOutputDefinition):
        val = outdef.value
        if val is None:
            raise ValueError(f"Output name is not resolved: {source_key}")
        return StrResolvedInstructionArgument(argument_name=arg_name, value=val)

    raise NotImplementedError(f"No resolved value mapping for type: {type(outdef).__name__}")


def require_arg(resolved_args: dict[str, ResolvedInstructionArgument], arg_name: str, arg_type: type[RIA]) -> RIA:
    """Returns the resolved arg of the expected type from the args dict.

    Args:
        resolved_args: A dictionary of resolved arguments.
        arg_name: The name of the argument to retrieve.
        arg_type: The expected type of the argument, a subclass of ResolvedInstructionArgument.

    Raises:
        KeyError: If arg_name is not in resolved_args.
        TypeError: If the argument is not of the expected type.
    """
    if arg_name not in resolved_args:
        raise KeyError(f"Required argument '{arg_name}' not found in resolved arguments")

    arg = resolved_args[arg_name]

    if not isinstance(arg, arg_type):
        raise TypeError(f"Expected argument '{arg_name}' to be of type {arg_type.__name__}, got {type(arg).__name__}")

    return arg
