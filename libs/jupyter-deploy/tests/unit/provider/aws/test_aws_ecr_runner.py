import json
import unittest
from datetime import UTC, datetime
from unittest.mock import Mock, patch

import botocore.exceptions

from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import ImageTagNotFoundError, InstructionNotFoundError
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


class TestDescribeImage(unittest.TestCase):
    def _resolved_args(self) -> dict[str, ResolvedInstructionArgument]:
        return {
            "repository_name": StrResolvedInstructionArgument(
                argument_name="repository_name", value="my-app/jupyterlab"
            ),
            "image_tag": StrResolvedInstructionArgument(argument_name="image_tag", value="v1"),
        }

    @patch("jupyter_deploy.api.aws.ecr.ecr_repository.describe_image")
    def test_emits_available_on_success(self, mock_describe: Mock) -> None:
        runner = AwsEcrRunner(NullDisplay(), region_name="us-west-2")
        mock_describe.return_value = {"imageTags": ["v1"]}

        result = runner._describe_image(resolved_arguments=self._resolved_args())

        mock_describe.assert_called_once_with(runner.client, repository_name="my-app/jupyterlab", image_tag="v1")
        self.assertEqual(result["Status"].value, "Available")
        self.assertEqual(result["StatusCategory"].value, "healthy")

    def test_raises_image_tag_not_found_when_image_missing(self) -> None:
        runner = AwsEcrRunner(NullDisplay(), region_name="us-west-2")

        class FakeImageNotFound(Exception):
            pass

        runner.client = Mock()
        runner.client.exceptions.ImageNotFoundException = FakeImageNotFound

        with (
            patch("jupyter_deploy.api.aws.ecr.ecr_repository.describe_image", side_effect=FakeImageNotFound()),
            self.assertRaises(ImageTagNotFoundError),
        ):
            runner._describe_image(resolved_arguments=self._resolved_args())

    def test_other_errors_bubble_up(self) -> None:
        runner = AwsEcrRunner(NullDisplay(), region_name="us-west-2")

        class FakeImageNotFound(Exception):
            pass

        # Only ImageNotFoundException is translated; any other error (e.g. permission denied)
        # propagates unchanged rather than being mistaken for a missing tag.
        runner.client = Mock()
        runner.client.exceptions.ImageNotFoundException = FakeImageNotFound

        access_denied = botocore.exceptions.ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "not authorized"}},
            "DescribeImages",
        )
        with (
            patch("jupyter_deploy.api.aws.ecr.ecr_repository.describe_image", side_effect=access_denied),
            self.assertRaises(botocore.exceptions.ClientError),
        ):
            runner._describe_image(resolved_arguments=self._resolved_args())


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

    @patch("jupyter_deploy.api.aws.ecr.ecr_repository.describe_image")
    def test_routes_describe_image(self, mock_describe: Mock) -> None:
        runner = AwsEcrRunner(NullDisplay(), region_name="us-west-2")
        mock_describe.return_value = {"imageTags": ["v1"]}

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "repository_name": StrResolvedInstructionArgument(argument_name="repository_name", value="repo"),
            "image_tag": StrResolvedInstructionArgument(argument_name="image_tag", value="v1"),
        }

        runner.execute_instruction("describe-image", resolved_args)
        mock_describe.assert_called_once()
