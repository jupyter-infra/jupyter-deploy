import subprocess
import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import ConfigurationError, InstructionNotFoundError
from jupyter_deploy.provider.aws.aws_eks_runner import AwsEksRunner
from jupyter_deploy.provider.resolved_argdefs import StrResolvedInstructionArgument


class _ResourceNotFoundException(ClientError):
    pass


class TestAwsEksRunner(unittest.TestCase):
    @patch("jupyter_deploy.provider.aws.aws_eks_runner.boto3")
    def test_describe_cluster_returns_results(self, mock_boto3: Mock) -> None:
        mock_client: Mock = Mock()
        mock_boto3.client.return_value = mock_client
        mock_client.describe_cluster.return_value = {
            "cluster": {
                "name": "my-cluster",
                "status": "ACTIVE",
                "endpoint": "https://abc.eks.amazonaws.com",
                "version": "1.31",
                "certificateAuthority": {"data": "LS0tRkFLRS1DQS0tLQ=="},
            }
        }

        runner = AwsEksRunner(NullDisplay(), region_name="us-west-2")
        result = runner.execute_instruction(
            instruction_name="describe-cluster",
            resolved_arguments={
                "cluster_name": StrResolvedInstructionArgument(argument_name="cluster_name", value="my-cluster"),
            },
        )

        self.assertEqual(result["ClusterName"].value, "my-cluster")
        self.assertEqual(result["Status"].value, "ACTIVE")
        self.assertEqual(result["Endpoint"].value, "https://abc.eks.amazonaws.com")
        self.assertEqual(result["Version"].value, "1.31")
        self.assertEqual(result["CertificateAuthority"].value, "LS0tRkFLRS1DQS0tLQ==")
        mock_client.describe_cluster.assert_called_once_with(name="my-cluster")

    @patch("jupyter_deploy.provider.aws.aws_eks_runner.boto3")
    def test_describe_cluster_without_ca_returns_empty_string(self, mock_boto3: Mock) -> None:
        mock_client: Mock = Mock()
        mock_boto3.client.return_value = mock_client
        mock_client.describe_cluster.return_value = {
            "cluster": {
                "name": "my-cluster",
                "status": "CREATING",
            }
        }

        runner = AwsEksRunner(NullDisplay(), region_name="us-west-2")
        result = runner.execute_instruction(
            instruction_name="describe-cluster",
            resolved_arguments={
                "cluster_name": StrResolvedInstructionArgument(argument_name="cluster_name", value="my-cluster"),
            },
        )

        self.assertEqual(result["CertificateAuthority"].value, "")

    @patch("jupyter_deploy.provider.aws.aws_eks_runner.eks_cluster")
    @patch("jupyter_deploy.provider.aws.aws_eks_runner.boto3")
    def test_list_nodegroups_returns_comma_separated(self, mock_boto3: Mock, mock_eks_cluster: Mock) -> None:
        mock_eks_cluster.list_nodegroups.return_value = (["ng-1", "ng-2"], None)

        runner = AwsEksRunner(NullDisplay(), region_name="us-west-2")
        result = runner.execute_instruction(
            instruction_name="list-nodegroups",
            resolved_arguments={
                "cluster_name": StrResolvedInstructionArgument(argument_name="cluster_name", value="my-cluster"),
            },
        )

        self.assertEqual(result["Nodegroups"].value, "ng-1,ng-2")
        self.assertEqual(result["NextToken"].value, "")

    @patch("jupyter_deploy.provider.aws.aws_eks_runner.eks_cluster")
    @patch("jupyter_deploy.provider.aws.aws_eks_runner.boto3")
    def test_list_nodegroups_returns_next_token(self, mock_boto3: Mock, mock_eks_cluster: Mock) -> None:
        mock_eks_cluster.list_nodegroups.return_value = (["ng-1"], "token-abc")

        runner = AwsEksRunner(NullDisplay(), region_name="us-west-2")
        result = runner.execute_instruction(
            instruction_name="list-nodegroups",
            resolved_arguments={
                "cluster_name": StrResolvedInstructionArgument(argument_name="cluster_name", value="my-cluster"),
            },
        )

        self.assertEqual(result["Nodegroups"].value, "ng-1")
        self.assertEqual(result["NextToken"].value, "token-abc")

    @patch("jupyter_deploy.provider.aws.aws_eks_runner.boto3")
    def test_describe_nodegroup_returns_results(self, mock_boto3: Mock) -> None:
        mock_client: Mock = Mock()
        mock_boto3.client.return_value = mock_client
        mock_client.describe_nodegroup.return_value = {
            "nodegroup": {
                "nodegroupName": "ng-1",
                "status": "ACTIVE",
            }
        }

        runner = AwsEksRunner(NullDisplay(), region_name="us-west-2")
        result = runner.execute_instruction(
            instruction_name="describe-nodegroup",
            resolved_arguments={
                "cluster_name": StrResolvedInstructionArgument(argument_name="cluster_name", value="my-cluster"),
                "nodegroup_name": StrResolvedInstructionArgument(argument_name="nodegroup_name", value="ng-1"),
            },
        )

        self.assertEqual(result["NodegroupName"].value, "ng-1")
        self.assertEqual(result["Status"].value, "ACTIVE")
        mock_client.describe_nodegroup.assert_called_once_with(clusterName="my-cluster", nodegroupName="ng-1")

    @patch("jupyter_deploy.provider.aws.aws_eks_runner.run_cmd_and_capture_output")
    @patch("jupyter_deploy.provider.aws.aws_eks_runner.boto3")
    def test_update_kubeconfig_runs_aws_cli(self, mock_boto3: Mock, mock_run: Mock) -> None:
        mock_run.return_value = "Updated context arn:aws:eks:us-west-2:123:cluster/my-cluster\n"

        runner = AwsEksRunner(NullDisplay(), region_name="us-west-2")
        result = runner.execute_instruction(
            instruction_name="update-kubeconfig",
            resolved_arguments={
                "cluster_name": StrResolvedInstructionArgument(argument_name="cluster_name", value="my-cluster"),
            },
        )

        self.assertEqual(result["Output"].value, "Updated context arn:aws:eks:us-west-2:123:cluster/my-cluster")
        mock_run.assert_called_once_with(
            ["aws", "eks", "update-kubeconfig", "--name", "my-cluster", "--region", "us-west-2"]
        )

    @patch("jupyter_deploy.provider.aws.aws_eks_runner.boto3")
    def test_update_kubeconfig_raises_when_region_is_none(self, mock_boto3: Mock) -> None:
        runner = AwsEksRunner(NullDisplay(), region_name=None)

        with self.assertRaises(ConfigurationError):
            runner.execute_instruction(
                instruction_name="update-kubeconfig",
                resolved_arguments={
                    "cluster_name": StrResolvedInstructionArgument(argument_name="cluster_name", value="my-cluster"),
                },
            )

    @patch("jupyter_deploy.provider.aws.aws_eks_runner.run_cmd_and_capture_output")
    @patch("jupyter_deploy.provider.aws.aws_eks_runner.boto3")
    def test_update_kubeconfig_raises_on_command_failure(self, mock_boto3: Mock, mock_run: Mock) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, "aws")

        runner = AwsEksRunner(NullDisplay(), region_name="us-west-2")
        with self.assertRaises(subprocess.CalledProcessError):
            runner.execute_instruction(
                instruction_name="update-kubeconfig",
                resolved_arguments={
                    "cluster_name": StrResolvedInstructionArgument(argument_name="cluster_name", value="bad-cluster"),
                },
            )

    @patch("jupyter_deploy.provider.aws.aws_eks_runner.eks_cluster")
    @patch("jupyter_deploy.provider.aws.aws_eks_runner.boto3")
    def test_describe_cluster_not_found_returns_not_found_status(
        self, mock_boto3: Mock, mock_eks_cluster: Mock
    ) -> None:
        mock_client: Mock = Mock()
        mock_client.exceptions.ResourceNotFoundException = _ResourceNotFoundException
        mock_boto3.client.return_value = mock_client
        mock_eks_cluster.describe_cluster.side_effect = _ResourceNotFoundException(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Cluster not found"}},
            "DescribeCluster",
        )

        runner = AwsEksRunner(NullDisplay(), region_name="us-west-2")
        result = runner.execute_instruction(
            instruction_name="describe-cluster",
            resolved_arguments={
                "cluster_name": StrResolvedInstructionArgument(argument_name="cluster_name", value="gone-cluster"),
            },
        )

        self.assertEqual(result["Status"].value, "NOT_FOUND")
        self.assertEqual(result["ClusterName"].value, "gone-cluster")
        self.assertEqual(result["Label"].value, "AWS EKS cluster")
        self.assertEqual(result["Endpoint"].value, "")
        self.assertEqual(result["Version"].value, "")

    @patch("jupyter_deploy.provider.aws.aws_eks_runner.eks_cluster")
    @patch("jupyter_deploy.provider.aws.aws_eks_runner.boto3")
    def test_describe_cluster_other_client_error_bubbles_up(self, mock_boto3: Mock, mock_eks_cluster: Mock) -> None:
        mock_client: Mock = Mock()
        mock_client.exceptions.ResourceNotFoundException = _ResourceNotFoundException
        mock_boto3.client.return_value = mock_client
        mock_eks_cluster.describe_cluster.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access Denied"}},
            "DescribeCluster",
        )

        runner = AwsEksRunner(NullDisplay(), region_name="us-west-2")

        with self.assertRaises(ClientError) as ctx:
            runner.execute_instruction(
                instruction_name="describe-cluster",
                resolved_arguments={
                    "cluster_name": StrResolvedInstructionArgument(argument_name="cluster_name", value="my-cluster"),
                },
            )

        self.assertEqual(ctx.exception.response["Error"]["Code"], "AccessDeniedException")

    @patch("jupyter_deploy.provider.aws.aws_eks_runner.boto3")
    def test_unknown_instruction_raises_error(self, mock_boto3: Mock) -> None:
        runner = AwsEksRunner(NullDisplay(), region_name="us-west-2")

        with self.assertRaises(InstructionNotFoundError):
            runner.execute_instruction(
                instruction_name="unknown-instruction",
                resolved_arguments={},
            )
