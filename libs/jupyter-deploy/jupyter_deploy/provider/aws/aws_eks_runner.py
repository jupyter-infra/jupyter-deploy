from enum import Enum

import boto3
from mypy_boto3_eks.client import EKSClient

from jupyter_deploy.api.aws.eks import eks_cluster
from jupyter_deploy.cmd_utils import run_cmd_and_capture_output
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.exceptions import ConfigurationError, InstructionNotFoundError
from jupyter_deploy.provider.instruction_runner import InstructionRunner
from jupyter_deploy.provider.resolved_argdefs import (
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
    retrieve_optional_arg,
)
from jupyter_deploy.provider.resolved_resultdefs import (
    ResolvedInstructionResult,
    StrResolvedInstructionResult,
)


class AwsEksInstruction(str, Enum):
    """AWS EKS instructions accessible from manifest.commands[].sequence[].api-name."""

    DESCRIBE_CLUSTER = "describe-cluster"
    LIST_NODEGROUPS = "list-nodegroups"
    DESCRIBE_NODEGROUP = "describe-nodegroup"
    UPDATE_KUBECONFIG = "update-kubeconfig"


class AwsEksRunner(InstructionRunner):
    """Runner class for AWS EKS service API instructions."""

    def __init__(self, display_manager: DisplayManager, region_name: str | None) -> None:
        super().__init__(display_manager)
        self.client: EKSClient = boto3.client("eks", region_name=region_name)
        self.region_name = region_name

    def _describe_cluster(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        cluster_name_arg = require_arg(resolved_arguments, "cluster_name", StrResolvedInstructionArgument)

        self.display_manager.info(f"Describing EKS cluster: {cluster_name_arg.value}")
        try:
            cluster = eks_cluster.describe_cluster(self.client, cluster_name=cluster_name_arg.value)
        except self.client.exceptions.ResourceNotFoundException:
            return {
                "ClusterName": StrResolvedInstructionResult(result_name="ClusterName", value=cluster_name_arg.value),
                "Label": StrResolvedInstructionResult(result_name="Label", value="AWS EKS cluster"),
                "Status": StrResolvedInstructionResult(result_name="Status", value="NOT_FOUND"),
                "Endpoint": StrResolvedInstructionResult(result_name="Endpoint", value=""),
                "Version": StrResolvedInstructionResult(result_name="Version", value=""),
                "CertificateAuthority": StrResolvedInstructionResult(result_name="CertificateAuthority", value=""),
            }

        ca_data = ""
        if cert_auth := cluster.get("certificateAuthority"):
            ca_data = cert_auth.get("data", "")

        return {
            "ClusterName": StrResolvedInstructionResult(result_name="ClusterName", value=cluster.get("name", "")),
            "Label": StrResolvedInstructionResult(result_name="Label", value="AWS EKS cluster"),
            "Status": StrResolvedInstructionResult(result_name="Status", value=cluster.get("status", "")),
            "Endpoint": StrResolvedInstructionResult(result_name="Endpoint", value=cluster.get("endpoint", "")),
            "Version": StrResolvedInstructionResult(result_name="Version", value=cluster.get("version", "")),
            "CertificateAuthority": StrResolvedInstructionResult(result_name="CertificateAuthority", value=ca_data),
        }

    def _list_nodegroups(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        cluster_name_arg = require_arg(resolved_arguments, "cluster_name", StrResolvedInstructionArgument)
        pagination_token_arg = retrieve_optional_arg(
            resolved_arguments, "pagination_token", StrResolvedInstructionArgument, ""
        )

        self.display_manager.info(f"Listing node groups for cluster: {cluster_name_arg.value}")
        nodegroups, next_token = eks_cluster.list_nodegroups(
            self.client,
            cluster_name=cluster_name_arg.value,
            starting_token=pagination_token_arg.value or None,  # coerce "" to None for the API
        )

        return {
            "Nodegroups": StrResolvedInstructionResult(result_name="Nodegroups", value=",".join(nodegroups)),
            "NextToken": StrResolvedInstructionResult(result_name="NextToken", value=next_token or ""),
        }

    def _describe_nodegroup(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        cluster_name_arg = require_arg(resolved_arguments, "cluster_name", StrResolvedInstructionArgument)
        nodegroup_name_arg = require_arg(resolved_arguments, "nodegroup_name", StrResolvedInstructionArgument)

        self.display_manager.info(f"Describing node group: {nodegroup_name_arg.value}")
        nodegroup = eks_cluster.describe_nodegroup(
            self.client, cluster_name=cluster_name_arg.value, nodegroup_name=nodegroup_name_arg.value
        )

        return {
            "NodegroupName": StrResolvedInstructionResult(
                result_name="NodegroupName", value=nodegroup.get("nodegroupName", "")
            ),
            "Status": StrResolvedInstructionResult(result_name="Status", value=nodegroup.get("status", "")),
        }

    def _update_kubeconfig(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        cluster_name_arg = require_arg(resolved_arguments, "cluster_name", StrResolvedInstructionArgument)
        if not self.region_name:
            raise ConfigurationError("AWS region is required for update-kubeconfig")
        region = self.region_name

        self.display_manager.info(f"Updating kubeconfig for cluster: {cluster_name_arg.value}")
        cmd = ["aws", "eks", "update-kubeconfig", "--name", cluster_name_arg.value, "--region", region]
        output = run_cmd_and_capture_output(cmd)

        return {
            "Output": StrResolvedInstructionResult(result_name="Output", value=output.strip()),
        }

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        try:
            instruction = AwsEksInstruction(instruction_name)
        except ValueError:
            raise InstructionNotFoundError(f"Unknown EKS instruction: '{instruction_name}'") from None

        if instruction == AwsEksInstruction.DESCRIBE_CLUSTER:
            return self._describe_cluster(resolved_arguments)
        elif instruction == AwsEksInstruction.LIST_NODEGROUPS:
            return self._list_nodegroups(resolved_arguments)
        elif instruction == AwsEksInstruction.DESCRIBE_NODEGROUP:
            return self._describe_nodegroup(resolved_arguments)
        elif instruction == AwsEksInstruction.UPDATE_KUBECONFIG:
            return self._update_kubeconfig(resolved_arguments)

        raise InstructionNotFoundError(f"Unknown EKS instruction: '{instruction_name}'")
