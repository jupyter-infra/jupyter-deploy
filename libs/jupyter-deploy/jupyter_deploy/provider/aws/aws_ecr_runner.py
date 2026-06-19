import json
from enum import Enum

import boto3
from mypy_boto3_ecr.client import ECRClient

from jupyter_deploy.api.aws.ecr import ecr_repository
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.exceptions import InstructionNotFoundError
from jupyter_deploy.provider.instruction_runner import InstructionRunner
from jupyter_deploy.provider.resolved_argdefs import (
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
)
from jupyter_deploy.provider.resolved_resultdefs import (
    ResolvedInstructionResult,
    StrResolvedInstructionResult,
)


class AwsEcrInstruction(str, Enum):
    """AWS ECR instructions accessible from manifest.commands[].sequence[].api-name."""

    DESCRIBE_REPOSITORY = "describe-repository"
    LIST_IMAGE_TAGS = "list-image-tags"


class AwsEcrRunner(InstructionRunner):
    """Runner class for AWS ECR service API instructions."""

    def __init__(self, display_manager: DisplayManager, region_name: str | None) -> None:
        super().__init__(display_manager)
        self.client: ECRClient = boto3.client("ecr", region_name=region_name)

    def _describe_repository(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        repository_name_arg = require_arg(resolved_arguments, "repository_name", StrResolvedInstructionArgument)

        self.display_manager.info(f"Describing ECR repository: {repository_name_arg.value}")
        repo = ecr_repository.describe_repository(self.client, repository_name=repository_name_arg.value)

        return {
            "RepositoryUri": StrResolvedInstructionResult(
                result_name="RepositoryUri", value=repo.get("repositoryUri", "")
            ),
            "RepositoryArn": StrResolvedInstructionResult(
                result_name="RepositoryArn", value=repo.get("repositoryArn", "")
            ),
            "RepositoryName": StrResolvedInstructionResult(
                result_name="RepositoryName", value=repo.get("repositoryName", "")
            ),
        }

    def _list_image_tags(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        repository_name_arg = require_arg(resolved_arguments, "repository_name", StrResolvedInstructionArgument)

        self.display_manager.info(f"Listing image tags for: {repository_name_arg.value}")
        image_details = ecr_repository.list_image_tags(self.client, repository_name=repository_name_arg.value)

        tags: list[dict[str, str]] = []
        for image in sorted(image_details, key=lambda i: str(i.get("imagePushedAt", "")), reverse=True):
            pushed_at = image.get("imagePushedAt")
            digest = image.get("imageDigest", "")
            for tag in image.get("imageTags", []):
                tags.append(
                    {
                        "tag": tag,
                        "pushed_at": pushed_at.isoformat() if pushed_at else "",
                        "digest": digest,
                    }
                )

        return {
            "Tags": StrResolvedInstructionResult(result_name="Tags", value=json.dumps(tags)),
        }

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        try:
            instruction = AwsEcrInstruction(instruction_name)
        except ValueError:
            raise InstructionNotFoundError(f"Unknown ECR instruction: '{instruction_name}'") from None

        if instruction == AwsEcrInstruction.DESCRIBE_REPOSITORY:
            return self._describe_repository(resolved_arguments)
        elif instruction == AwsEcrInstruction.LIST_IMAGE_TAGS:
            return self._list_image_tags(resolved_arguments)

        raise InstructionNotFoundError(f"Unknown ECR instruction: '{instruction_name}'")
