import json
import unittest
from datetime import UTC, datetime
from unittest.mock import Mock, patch

from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import InstructionNotFoundError
from jupyter_deploy.provider.aws.aws_ecr_runner import AwsEcrRunner
from jupyter_deploy.provider.resolved_argdefs import ResolvedInstructionArgument, StrResolvedInstructionArgument


class TestAwsEcrRunner(unittest.TestCase):
    @patch("boto3.client")
    def test_instantiates_client(self, mock_boto3_client: Mock) -> None:
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        runner = AwsEcrRunner(NullDisplay(), region_name="us-west-2")

        mock_boto3_client.assert_called_once_with("ecr", region_name="us-west-2")
        self.assertEqual(runner.client, mock_client)

    def test_raises_on_unmatched_instruction_name(self) -> None:
        runner = AwsEcrRunner(NullDisplay(), region_name="us-west-2")

        with self.assertRaises(InstructionNotFoundError) as ctx:
            runner.execute_instruction(instruction_name="non-existent", resolved_arguments={})

        self.assertIn("non-existent", str(ctx.exception))


class TestDescribeRepository(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ecr.ecr_repository.describe_repository")
    def test_happy_path(self, mock_describe: Mock) -> None:
        runner = AwsEcrRunner(NullDisplay(), region_name="us-west-2")
        mock_describe.return_value = {
            "repositoryUri": "123456.dkr.ecr.us-west-2.amazonaws.com/my-app/jupyterlab",
            "repositoryArn": "arn:aws:ecr:us-west-2:123456:repository/my-app/jupyterlab",
            "repositoryName": "my-app/jupyterlab",
        }

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "repository_name": StrResolvedInstructionArgument(
                argument_name="repository_name", value="my-app/jupyterlab"
            ),
        }

        result = runner._describe_repository(resolved_arguments=resolved_args)

        mock_describe.assert_called_once_with(runner.client, repository_name="my-app/jupyterlab")
        self.assertEqual(result["RepositoryUri"].value, "123456.dkr.ecr.us-west-2.amazonaws.com/my-app/jupyterlab")
        self.assertEqual(result["RepositoryName"].value, "my-app/jupyterlab")

    @patch("jupyter_deploy.api.aws.ecr.ecr_repository.describe_repository")
    def test_raises_when_api_raises(self, mock_describe: Mock) -> None:
        runner = AwsEcrRunner(NullDisplay(), region_name="us-west-2")
        mock_describe.side_effect = RuntimeError("Repository not found")

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "repository_name": StrResolvedInstructionArgument(argument_name="repository_name", value="nonexistent"),
        }

        with self.assertRaises(RuntimeError):
            runner._describe_repository(resolved_arguments=resolved_args)


class TestListImageTags(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ecr.ecr_repository.list_image_tags")
    def test_happy_path(self, mock_list_tags: Mock) -> None:
        runner = AwsEcrRunner(NullDisplay(), region_name="us-west-2")
        mock_list_tags.return_value = [
            {
                "imageTags": ["v1", "latest"],
                "imageDigest": "sha256:abc123",
                "imagePushedAt": datetime(2026, 6, 18, 15, 49, 0, tzinfo=UTC),
            },
        ]

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "repository_name": StrResolvedInstructionArgument(
                argument_name="repository_name", value="my-app/jupyterlab"
            ),
        }

        result = runner._list_image_tags(resolved_arguments=resolved_args)

        mock_list_tags.assert_called_once_with(runner.client, repository_name="my-app/jupyterlab")
        tags = json.loads(result["Tags"].value)
        self.assertEqual(len(tags), 2)
        self.assertEqual(tags[0]["tag"], "v1")
        self.assertEqual(tags[1]["tag"], "latest")
        self.assertEqual(tags[0]["digest"], "sha256:abc123")

    @patch("jupyter_deploy.api.aws.ecr.ecr_repository.list_image_tags")
    def test_returns_empty_json_when_no_tags(self, mock_list_tags: Mock) -> None:
        runner = AwsEcrRunner(NullDisplay(), region_name="us-west-2")
        mock_list_tags.return_value = []

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "repository_name": StrResolvedInstructionArgument(
                argument_name="repository_name", value="my-app/jupyterlab"
            ),
        }

        result = runner._list_image_tags(resolved_arguments=resolved_args)
        tags = json.loads(result["Tags"].value)
        self.assertEqual(tags, [])

    @patch("jupyter_deploy.api.aws.ecr.ecr_repository.list_image_tags")
    def test_raises_when_api_raises(self, mock_list_tags: Mock) -> None:
        runner = AwsEcrRunner(NullDisplay(), region_name="us-west-2")
        mock_list_tags.side_effect = RuntimeError("API error")

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "repository_name": StrResolvedInstructionArgument(
                argument_name="repository_name", value="my-app/jupyterlab"
            ),
        }

        with self.assertRaises(RuntimeError):
            runner._list_image_tags(resolved_arguments=resolved_args)


class TestExecuteInstruction(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.ecr.ecr_repository.describe_repository")
    def test_routes_describe_repository(self, mock_describe: Mock) -> None:
        runner = AwsEcrRunner(NullDisplay(), region_name="us-west-2")
        mock_describe.return_value = {"repositoryUri": "", "repositoryArn": "", "repositoryName": ""}

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "repository_name": StrResolvedInstructionArgument(argument_name="repository_name", value="repo"),
        }

        runner.execute_instruction("describe-repository", resolved_args)
        mock_describe.assert_called_once()

    @patch("jupyter_deploy.api.aws.ecr.ecr_repository.list_image_tags")
    def test_routes_list_image_tags(self, mock_list: Mock) -> None:
        runner = AwsEcrRunner(NullDisplay(), region_name="us-west-2")
        mock_list.return_value = []

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "repository_name": StrResolvedInstructionArgument(argument_name="repository_name", value="repo"),
        }

        runner.execute_instruction("list-image-tags", resolved_args)
        mock_list.assert_called_once()
