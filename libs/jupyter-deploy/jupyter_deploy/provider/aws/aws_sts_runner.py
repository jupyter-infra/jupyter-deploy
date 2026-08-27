import json
from datetime import UTC, datetime, timedelta
from enum import Enum

from jupyter_deploy.api.aws.sts import eks_token
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.exceptions import InstructionNotFoundError, InvalidInstructionArgumentError
from jupyter_deploy.provider.instruction_runner import InstructionRunner
from jupyter_deploy.provider.resolved_argdefs import (
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
)
from jupyter_deploy.provider.resolved_resultdefs import ResolvedInstructionResult, StrResolvedInstructionResult


class AwsStsInstruction(str, Enum):
    """AWS STS instructions accessible from manifest.commands[].sequence[].api-name."""

    MINT_CONNECT_TOKEN = "mint-connect-token"


class AwsStsRunner(InstructionRunner):
    """Runner class for AWS STS-derived credential instructions."""

    def __init__(self, display_manager: DisplayManager, region_name: str | None) -> None:
        """Store the region; token minting uses the default botocore credential chain."""
        super().__init__(display_manager)
        self.region_name = region_name

    def _mint_connect_token(
        self,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        binding_id_arg = require_arg(resolved_arguments, "binding_id", StrResolvedInstructionArgument)
        if not self.region_name:
            raise InvalidInstructionArgumentError("Cannot mint a connect token without an AWS region.")

        # Mint a short-lived presigned-STS token bound to `binding_id`, and assemble the
        # opaque header map the proxy injects verbatim: the bearer token plus the binding
        # header the server-side validator (aws-iam-authenticator) checks. The proxy and the
        # handler treat this map as opaque — header names live here, in the provider that
        # owns the token contract.
        expires_in = eks_token.DEFAULT_TOKEN_EXPIRY_SECONDS
        token = eks_token.get_eks_bearer_token(
            binding_id=binding_id_arg.value, region=self.region_name, expires_in_seconds=expires_in
        )
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        headers = {
            "Authorization": f"Bearer {token}",
            eks_token.BINDING_HEADER_NAME: binding_id_arg.value,
        }

        return {
            "Headers": StrResolvedInstructionResult(result_name="Headers", value=json.dumps(headers)),
            "ExpiresAt": StrResolvedInstructionResult(
                result_name="ExpiresAt", value=expires_at.isoformat().replace("+00:00", "Z")
            ),
        }

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        if instruction_name == AwsStsInstruction.MINT_CONNECT_TOKEN:
            return self._mint_connect_token(resolved_arguments=resolved_arguments)

        raise InstructionNotFoundError(f"No execution implementation for command: aws.sts.{instruction_name}")
