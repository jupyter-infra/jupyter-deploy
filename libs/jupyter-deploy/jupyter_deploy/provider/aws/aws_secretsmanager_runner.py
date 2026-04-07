from enum import Enum

import boto3
from mypy_boto3_secretsmanager.client import SecretsManagerClient

from jupyter_deploy.api.aws.secretsmanager import secretsmanager_secret
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.exceptions import InstructionNotFoundError
from jupyter_deploy.provider.instruction_runner import InstructionRunner
from jupyter_deploy.provider.resolved_argdefs import (
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
)
from jupyter_deploy.provider.resolved_resultdefs import ResolvedInstructionResult, StrResolvedInstructionResult


class AwsSecretsManagerInstruction(str, Enum):
    """AWS Secrets Manager instructions accessible from manifest.commands[].sequence[].api-name."""

    GET_SECRET_VALUE = "get-secret-value"


class AwsSecretsManagerRunner(InstructionRunner):
    """Runner class for AWS Secrets Manager service API instructions."""

    client: SecretsManagerClient

    def __init__(self, display_manager: DisplayManager, region_name: str | None) -> None:
        super().__init__(display_manager)
        self.client: SecretsManagerClient = boto3.client("secretsmanager", region_name=region_name)

    def _get_secret_value(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        secret_id_arg = require_arg(resolved_arguments, "secret_id", StrResolvedInstructionArgument)
        secret_id = secret_id_arg.value

        self.display_manager.info(f"Fetching secret: {secret_id}")
        response = secretsmanager_secret.get_secret_value(self.client, secret_id=secret_id)
        self.display_manager.info(f"Successfully fetched secret: {secret_id}")

        return {
            "SecretString": StrResolvedInstructionResult(
                result_name="SecretString",
                value=response["SecretString"],
            ),
        }

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        try:
            instruction = AwsSecretsManagerInstruction(instruction_name)
        except ValueError:
            raise InstructionNotFoundError(f"Unknown Secrets Manager instruction: '{instruction_name}'") from None

        if instruction == AwsSecretsManagerInstruction.GET_SECRET_VALUE:
            return self._get_secret_value(resolved_arguments)

        raise InstructionNotFoundError(f"Unknown Secrets Manager instruction: '{instruction_name}'")
