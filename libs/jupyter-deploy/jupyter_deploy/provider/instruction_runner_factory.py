from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.provider.enum import ProviderType
from jupyter_deploy.provider.instruction_runner import InstructionRunner


class InstructionRunnerFactory:
    """Factory class to handle lower level imports of cloud provider specific dependencies.

    This ensures that the base jupyter-deploy does not depend on any cloud provider SDK.
    """

    _provider_runner_map: dict[ProviderType, InstructionRunner] = {}

    @staticmethod
    def get_provider_instruction_runner(api_name: str, outputs_handler: EngineOutputsHandler) -> InstructionRunner:
        """Return the instruction runner for the cloud provider.

        Raises:
            NotImplementedError if the provider is not recognized.
            ValueError if the provider runner requires declared values that are missing in manifest.
        """
        provider = ProviderType.from_api_name(api_name)
        if provider_runner := InstructionRunnerFactory._provider_runner_map.get(provider):
            return provider_runner

        if provider == ProviderType.AWS:
            aws_region_def = outputs_handler.get_declared_output_def("aws_region", StrTemplateOutputDefinition)

            # do NOT move import to top level
            from jupyter_deploy.provider.aws import aws_runner

            provider_runner = aws_runner.AwsApiRunner(region_name=aws_region_def.value)
            InstructionRunnerFactory._provider_runner_map[provider] = provider_runner
            return provider_runner

        raise NotImplementedError(f"No runner implementation for provider: {provider}")
