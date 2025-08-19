from enum import Enum

from rich import console as rich_console

from jupyter_deploy.provider.aws.aws_ec2_runner import AwsEc2Runner
from jupyter_deploy.provider.aws.aws_ssm_runner import AwsSsmRunner
from jupyter_deploy.provider.instruction_runner import InstructionRunner
from jupyter_deploy.provider.resolved_argdefs import ResolvedInstructionArgument
from jupyter_deploy.provider.resolved_resultdefs import ResolvedInstructionResult


class AwsService(str, Enum):
    """AWS services mapped to jupyter-deploy instructions."""

    EC2 = "ec2"
    SSM = "ssm"


class AwsApiRunner(InstructionRunner):
    """Wrapper class to provide access to AWS APIs.

    Requires the user to install jupyter-deploy[aws].
    """

    def __init__(self, region_name: str | None) -> None:
        """Instantiate the map of AWS services runner."""
        self.region_name = region_name
        self.service_runners: dict[str, InstructionRunner] = {}

    @staticmethod
    def _get_service_and_sub_instruction_name(instruction_name: str) -> tuple[str, str]:
        """Return a tuple of service-name, instruction-name."""
        # expect aws.<service-name>.<instruction>

        parts = instruction_name.split(".")

        if len(parts) < 2 or not parts[1] or not parts[2]:
            raise ValueError(
                f"Invalid instruction: {instruction_name}; should be of the form aws.service-name.instruction-name"
            )
        return parts[1], ".".join(parts[2:])

    def _get_service_runner(self, service_name: str) -> InstructionRunner:
        service_runner = self.service_runners.get(service_name)

        if service_runner:
            return service_runner

        if service_name == AwsService.SSM:
            service_runner = AwsSsmRunner(region_name=self.region_name)
            self.service_runners[service_name] = service_runner
            return service_runner
        elif service_name == AwsService.EC2:
            service_runner = AwsEc2Runner(region_name=self.region_name)
            self.service_runners[service_name] = service_runner
            return service_runner

        raise NotImplementedError(f"Unrecognized AWS service name: {service_name}")

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
        console: rich_console.Console,
    ) -> dict[str, ResolvedInstructionResult]:
        service_name, sub_instruction_name = AwsApiRunner._get_service_and_sub_instruction_name(instruction_name)
        service_runner = self._get_service_runner(service_name)
        return service_runner.execute_instruction(
            instruction_name=sub_instruction_name,
            resolved_arguments=resolved_arguments,
            console=console,
        )
