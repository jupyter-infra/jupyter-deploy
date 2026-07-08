from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.provider.enum import ApiGroup
from jupyter_deploy.provider.instruction_runner import InstructionRunner


class InstructionRunnerFactory:
    """Factory class to handle lower level imports of cloud provider specific dependencies.

    This ensures that the base jupyter-deploy does not depend on any cloud provider SDK.
    """

    _api_group_runner_map: dict[ApiGroup, InstructionRunner] = {}

    @staticmethod
    def get_provider_instruction_runner(
        api_name: str, outputs_handler: EngineOutputsHandler, display_manager: DisplayManager
    ) -> InstructionRunner:
        """Return the instruction runner for the given API group.

        Raises:
            NotImplementedError if the API group is not recognized.
            ValueError if the runner requires declared values that are missing in manifest.
        """
        api_group = ApiGroup.from_api_name(api_name)
        if runner := InstructionRunnerFactory._api_group_runner_map.get(api_group):
            return runner

        if api_group == ApiGroup.AWS:
            aws_region_def = outputs_handler.get_declared_output_def("aws_region", StrTemplateOutputDefinition)

            # do NOT move import to top level
            from jupyter_deploy.provider.aws import aws_runner

            runner = aws_runner.AwsApiRunner(display_manager=display_manager, region_name=aws_region_def.value)
            InstructionRunnerFactory._api_group_runner_map[api_group] = runner
            return runner

        if api_group == ApiGroup.K8S:
            cluster_endpoint, cluster_ca_data, cluster_name, region, kubeconfig_path = (
                InstructionRunnerFactory._resolve_cluster_credentials(outputs_handler)
            )

            # do NOT move import to top level
            from jupyter_deploy.provider.k8s import k8s_runner

            runner = k8s_runner.K8sApiRunner(
                display_manager=display_manager,
                kubeconfig_path=kubeconfig_path,
                cluster_endpoint=cluster_endpoint,
                cluster_ca_data=cluster_ca_data,
                cluster_name=cluster_name,
                region=region,
            )
            InstructionRunnerFactory._api_group_runner_map[api_group] = runner
            return runner

        if api_group == ApiGroup.HELM:
            # helm/kubectl subprocesses authenticate via a kubeconfig (the path when set,
            # else the ambient config set up by `jd cluster login`). The expected-cluster
            # check, when a command declares it, is driven by an instruction argument.
            _, _, _, _, kubeconfig_path = InstructionRunnerFactory._resolve_cluster_credentials(outputs_handler)

            # do NOT move import to top level
            from jupyter_deploy.provider.helm import helm_runner

            runner = helm_runner.HelmApiRunner(
                display_manager=display_manager,
                kubeconfig_path=kubeconfig_path,
            )
            InstructionRunnerFactory._api_group_runner_map[api_group] = runner
            return runner

        raise NotImplementedError(f"No runner implementation for API group: {api_group}")

    @staticmethod
    def _resolve_cluster_credentials(
        outputs_handler: EngineOutputsHandler,
    ) -> tuple[str | None, str | None, str | None, str | None, str | None]:
        """Resolve EKS cluster credentials from template outputs.

        Returns a tuple of (cluster_endpoint, cluster_ca_data, cluster_name, region,
        kubeconfig_path). When the in-memory cluster credentials are incomplete, falls
        back to the declared kubeconfig_path output.
        """
        cluster_endpoint: str | None = None
        cluster_ca_data: str | None = None
        cluster_name: str | None = None
        region: str | None = None
        kubeconfig_path: str | None = None

        try:
            endpoint_def = outputs_handler.get_declared_output_def("cluster_endpoint", StrTemplateOutputDefinition)
            ca_def = outputs_handler.get_declared_output_def("cluster_ca_certificate", StrTemplateOutputDefinition)
            name_def = outputs_handler.get_declared_output_def("cluster_name", StrTemplateOutputDefinition)
            region_def = outputs_handler.get_declared_output_def("aws_region", StrTemplateOutputDefinition)
            cluster_endpoint = endpoint_def.value
            cluster_ca_data = ca_def.value
            cluster_name = name_def.value
            region = region_def.value
        except (NotImplementedError, KeyError, ValueError):
            pass

        if not all([cluster_endpoint, cluster_ca_data, cluster_name, region]):
            kubeconfig_def = outputs_handler.get_declared_output_def("kubeconfig_path", StrTemplateOutputDefinition)
            kubeconfig_path = kubeconfig_def.value

        return cluster_endpoint, cluster_ca_data, cluster_name, region, kubeconfig_path
