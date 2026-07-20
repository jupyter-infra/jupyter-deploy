from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.enum import StatusCategory
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.handlers.payloads import ClusterDetail, HealthLayer, HealthLayerResult
from jupyter_deploy.handlers.resource.resource_utils import collect_results
from jupyter_deploy.provider import manifest_command_runner as cmd_runner


class ClusterHandler(BaseProjectHandler):
    """Handler class to interact with the cluster running the deployment."""

    _output_handler: EngineOutputsHandler

    def __init__(self, display_manager: DisplayManager) -> None:
        super().__init__(display_manager=display_manager)

        if self.engine == EngineType.TERRAFORM:
            self._output_handler = tf_outputs.TerraformOutputsHandler(
                project_path=self.project_path, project_manifest=self.project_manifest
            )
            self._variable_handler = tf_variables.TerraformVariablesHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
                display_manager=self.display_manager,
            )
        else:
            raise NotImplementedError(f"OutputsHandler implementation not found for engine: {self.engine}")

    def login(self) -> str:
        """Configure local client to access to the cluster, returns the output message."""
        command = self.project_manifest.get_command("cluster.login")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs={})
        return runner.get_result_value(command, "cluster.login.output", str)

    def get_cluster_status(self) -> str:
        """Returns the control plane state string."""
        command = self.project_manifest.get_command("cluster.status")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs={})
        return runner.get_result_value(command, "cluster.status", str)

    def get_load_balancer_health(self) -> HealthLayerResult:
        """Returns a HealthLayerResult for the load-balancer layer."""
        command = self.project_manifest.get_command("cluster.loadbalancer.health")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs={})

        state = runner.get_result_value(command, "cluster.loadbalancer.health.state", str)
        lb_label = runner.get_result_value(command, "cluster.loadbalancer.health.label", str)
        scheme = runner.get_result_value(command, "cluster.loadbalancer.health.scheme", str)

        if state == "not-found":
            return HealthLayerResult(
                layer=HealthLayer.LOAD_BALANCER,
                name=lb_label,
                status_category=StatusCategory.DEGRADED,
                status_text="Not Found",
                detail="no load balancer found",
                sub_component="-",
            )

        if state != "active":
            return HealthLayerResult(
                layer=HealthLayer.LOAD_BALANCER,
                name=lb_label,
                status_category=StatusCategory.DEGRADED if state == "failed" else StatusCategory.IN_PROGRESS,
                status_text=state.title(),
                detail=scheme,
                sub_component="-",
            )

        return HealthLayerResult(
            layer=HealthLayer.LOAD_BALANCER,
            name=lb_label,
            status_category=StatusCategory.HEALTHY,
            status_text=state.title(),
            detail=scheme,
            sub_component="-",
        )

    def health(self) -> HealthLayerResult:
        """Returns a HealthLayerResult for the cluster layer."""
        info = self.show_cluster()
        cluster_label = info.label
        status = info.status
        version = info.version

        detail = f"v{version}" if version else ""

        if status == "ACTIVE":
            return HealthLayerResult(
                layer=HealthLayer.CLUSTER,
                name=cluster_label,
                status_category=StatusCategory.HEALTHY,
                status_text=status.title(),
                detail=detail,
                sub_component="-",
            )
        elif status in ("CREATING", "UPDATING"):
            return HealthLayerResult(
                layer=HealthLayer.CLUSTER,
                name=cluster_label,
                status_category=StatusCategory.IN_PROGRESS,
                status_text=status.title(),
                detail=detail,
                sub_component="-",
            )
        return HealthLayerResult(
            layer=HealthLayer.CLUSTER,
            name=cluster_label,
            status_category=StatusCategory.DEGRADED,
            status_text=status.title(),
            detail=detail,
            sub_component="-",
        )

    def show_cluster(self) -> ClusterDetail:
        """Returns cluster metadata."""
        command = self.project_manifest.get_command("cluster.show")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs={})
        results = collect_results(runner, command)
        return ClusterDetail(
            name=results.get("name", ""),
            label=results.get("label", ""),
            status=results.get("status", ""),
            endpoint=results.get("endpoint", ""),
            version=results.get("version", ""),
        )
