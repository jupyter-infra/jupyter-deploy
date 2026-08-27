import json
import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import InstructionNotFoundError, InvalidInstructionArgumentError
from jupyter_deploy.provider.aws.aws_sts_runner import AwsStsInstruction, AwsStsRunner
from jupyter_deploy.provider.resolved_argdefs import ResolvedInstructionArgument, StrResolvedInstructionArgument


class TestMintConnectToken(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.sts.eks_token.get_eks_bearer_token")
    def test_returns_opaque_headers_and_expiry(self, mock_get_token: Mock) -> None:
        runner = AwsStsRunner(NullDisplay(), region_name="us-west-2")
        mock_get_token.return_value = "k8s-aws-v1.xxx"

        resolved_args: dict[str, ResolvedInstructionArgument] = {
            "binding_id": StrResolvedInstructionArgument(argument_name="binding_id", value="dep-abc"),
        }

        result = runner._mint_connect_token(resolved_arguments=resolved_args)

        # The token is bound to the deployment id and minted in the runner's region.
        mock_get_token.assert_called_once()
        _, kwargs = mock_get_token.call_args
        self.assertEqual(kwargs["binding_id"], "dep-abc")
        self.assertEqual(kwargs["region"], "us-west-2")

        headers = json.loads(result["Headers"].value)
        self.assertEqual(headers["Authorization"], "Bearer k8s-aws-v1.xxx")
        self.assertEqual(headers["x-k8s-aws-id"], "dep-abc")
        self.assertTrue(result["ExpiresAt"].value.endswith("Z"))

    @patch("jupyter_deploy.api.aws.sts.eks_token.get_eks_bearer_token")
    def test_routes_via_execute_instruction(self, mock_get_token: Mock) -> None:
        runner = AwsStsRunner(NullDisplay(), region_name="us-west-2")
        mock_get_token.return_value = "k8s-aws-v1.xxx"

        result = runner.execute_instruction(
            instruction_name=AwsStsInstruction.MINT_CONNECT_TOKEN,
            resolved_arguments={
                "binding_id": StrResolvedInstructionArgument(argument_name="binding_id", value="dep-abc")
            },
        )
        self.assertIn("Headers", result)

    def test_raises_without_region(self) -> None:
        runner = AwsStsRunner(NullDisplay(), region_name=None)
        with self.assertRaises(InvalidInstructionArgumentError):
            runner._mint_connect_token(
                resolved_arguments={
                    "binding_id": StrResolvedInstructionArgument(argument_name="binding_id", value="dep-abc")
                }
            )

    def test_raises_on_missing_binding_id(self) -> None:
        runner = AwsStsRunner(NullDisplay(), region_name="us-west-2")
        with self.assertRaises(KeyError):
            runner._mint_connect_token(resolved_arguments={})

    @patch("jupyter_deploy.api.aws.sts.eks_token.get_eks_bearer_token")
    def test_raises_when_token_mint_raises(self, mock_get_token: Mock) -> None:
        runner = AwsStsRunner(NullDisplay(), region_name="us-west-2")
        mock_get_token.side_effect = Exception("STS signing failed")

        with self.assertRaises(Exception) as ctx:
            runner._mint_connect_token(
                resolved_arguments={
                    "binding_id": StrResolvedInstructionArgument(argument_name="binding_id", value="dep-abc")
                }
            )
        self.assertIn("STS signing failed", str(ctx.exception))

    def test_unknown_instruction_raises(self) -> None:
        runner = AwsStsRunner(NullDisplay(), region_name="us-west-2")
        with self.assertRaises(InstructionNotFoundError):
            runner.execute_instruction(instruction_name="nope", resolved_arguments={})
