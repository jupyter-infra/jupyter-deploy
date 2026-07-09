import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.exceptions import ComponentNotFoundError, InvalidComponentVerbError, ResourceNotFoundError
from jupyter_deploy.handlers.resource.component_handler import ComponentHandler
from jupyter_deploy.manifest import JupyterDeployComponentDefinitionV1, JupyterDeployComponentVerbV1


def _mock_component_deployment() -> JupyterDeployComponentDefinitionV1:
    return JupyterDeployComponentDefinitionV1(
        type="Deployment",
        scope="workspace_router_namespace",
        verbs={
            "status": JupyterDeployComponentVerbV1(method="k8s.apps.get-deployment-status"),
            "show": JupyterDeployComponentVerbV1(method="k8s.apps.get-deployment"),
            "logs": JupyterDeployComponentVerbV1(method="k8s.core.deployment-logs"),
            "restart": JupyterDeployComponentVerbV1(method="k8s.apps.rollout-restart"),
        },
    )


def _mock_component_cronjob() -> JupyterDeployComponentDefinitionV1:
    return JupyterDeployComponentDefinitionV1(
        type="CronJob",
        scope="workspace_router_namespace",
        query="app=jwt-rotator",
        verbs={
            "status": JupyterDeployComponentVerbV1(method="k8s.batch.get-cronjob-status"),
            "show": JupyterDeployComponentVerbV1(method="k8s.batch.get-cronjob"),
            "logs": JupyterDeployComponentVerbV1(method="k8s.batch.get-job-logs"),
            "trigger": JupyterDeployComponentVerbV1(method="k8s.batch.create-job-from-cronjob"),
        },
    )


def _mock_component_helmrelease() -> JupyterDeployComponentDefinitionV1:
    return JupyterDeployComponentDefinitionV1(
        **{  # type: ignore[arg-type]
            "type": "HelmRelease",
            "scope": "workspace_router_namespace",
            "resource-name": "jupyter-k8s-aws-oidc",
            "verbs": {
                "status": {"method": "helm.status"},
                "show": {"method": "helm.show"},
                "reconcile": {"method": "helm.reconcile"},
            },
        }
    )


def _mock_component_custom_resource() -> JupyterDeployComponentDefinitionV1:
    return JupyterDeployComponentDefinitionV1(
        **{  # type: ignore[arg-type]
            "type": "CustomResourceWithoutStatus",
            "scope": "workspace_shared_namespace",
            "resource-name": "jupyterlab",
            "crd-group": "workspace.jupyter.org",
            "crd-version": "v1alpha1",
            "crd-plural": "workspacetemplates",
            "verbs": {"status": {"method": "k8s.custom.get"}, "show": {"method": "k8s.custom.get"}},
        }
    )


def _mock_component_crd() -> JupyterDeployComponentDefinitionV1:
    # No crd-group/version/plural: the handler supplies them for the well-known CRD kind.
    return JupyterDeployComponentDefinitionV1(
        **{  # type: ignore[arg-type]
            "type": "CustomResourceDefinition",
            "resource-name": "workspaces.workspace.jupyter.org",
            "details": {"path": ".spec.versions[0].name"},
            "verbs": {"status": {"method": "k8s.custom.get-cluster"}, "show": {"method": "k8s.custom.get-cluster"}},
        }
    )


_NS_OUTPUTS = {
    "workspace_router_namespace": StrTemplateOutputDefinition(
        output_name="workspace_router_namespace", value="router-ns"
    )
}

_CR_OUTPUTS = {
    "workspace_shared_namespace": StrTemplateOutputDefinition(
        output_name="workspace_shared_namespace", value="shared-ns"
    ),
}


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerGetComponentStatus(unittest.TestCase):
    def test_returns_status_for_deployment(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()
        mock_runner.get_result_value.return_value = "Ready"

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            mock_command: Mock = Mock()
            manifest.get_command.return_value = mock_command

            handler = ComponentHandler(display_manager=Mock())
            result = handler.get_component_status("traefik")

        self.assertEqual(result, "Ready")
        manifest.get_command.assert_called_once_with("component.deployment.status")
        mock_runner.run_command_sequence.assert_called_once()
        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["name"].value, "traefik")
        self.assertEqual(cli_paramdefs["scope"].value, "router-ns")

    def test_passes_query_for_cronjob(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_cronjob()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()
        mock_runner.get_result_value.return_value = "Idle"

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            handler.get_component_status("jwt-rotator")

        manifest.get_command.assert_called_once_with("component.cronjob.status")
        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["query"].value, "app=jwt-rotator")

    def test_error_bubbles_up(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value.run_command_sequence.side_effect = RuntimeError("API failure")
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            with self.assertRaises(RuntimeError):
                handler.get_component_status("traefik")

    def test_raises_component_not_found(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.side_effect = ComponentNotFoundError("unknown", ["traefik", "dex"])
        mock_manifest_fn.return_value = manifest

        handler = ComponentHandler(display_manager=Mock())

        with self.assertRaises(ComponentNotFoundError) as ctx:
            handler.get_component_status("unknown")

        self.assertEqual(ctx.exception.component_name, "unknown")
        self.assertIn("traefik", ctx.exception.valid_components)


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerListComponents(unittest.TestCase):
    def test_uses_type_display_when_set_else_type(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        cr = JupyterDeployComponentDefinitionV1(
            **{  # type: ignore[arg-type]
                "type": "CustomResourceWithoutStatus",
                "type-display": "WorkspaceTemplate",
                "scope": "ns",
                "verbs": {"status": {"method": "k8s.custom.get"}},
            }
        )
        manifest.get_components.return_value = {"jupyterlab-template": cr, "traefik": _mock_component_deployment()}
        mock_manifest_fn.return_value = manifest

        handler = ComponentHandler(display_manager=Mock())
        components = handler.list_components()

        by_name = {c["name"]: c for c in components}
        self.assertEqual(by_name["jupyterlab-template"]["type"], "WorkspaceTemplate")
        self.assertEqual(by_name["traefik"]["type"], "Deployment")  # falls back to type


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerVerbValidation(unittest.TestCase):
    def test_raises_invalid_verb_for_restart_on_cronjob(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_cronjob()
        mock_manifest_fn.return_value = manifest

        handler = ComponentHandler(display_manager=Mock())

        with self.assertRaises(InvalidComponentVerbError) as ctx:
            handler.restart_component("jwt-rotator")

        self.assertEqual(ctx.exception.verb, "restart")
        self.assertEqual(ctx.exception.component_type, "CronJob")
        self.assertIn("trigger", ctx.exception.valid_verbs)

    def test_raises_invalid_verb_for_trigger_on_deployment(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        handler = ComponentHandler(display_manager=Mock())

        with self.assertRaises(InvalidComponentVerbError) as ctx:
            handler.trigger_component("traefik")

        self.assertEqual(ctx.exception.verb, "trigger")
        self.assertEqual(ctx.exception.component_type, "Deployment")
        self.assertIn("restart", ctx.exception.valid_verbs)


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerGetAllStatus(unittest.TestCase):
    def test_returns_status_for_all_components(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_components.return_value = {
            "traefik": _mock_component_deployment(),
            "jwt-rotator": _mock_component_cronjob(),
        }
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()
        mock_runner.get_result_value.return_value = "Ready"
        mock_runner.get_result_value_with_fallback.return_value = "1/1 replicas"

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            results = handler.get_all_status()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "traefik")
        self.assertEqual(results[0]["status"], "Ready")
        self.assertEqual(results[1]["name"], "jwt-rotator")
        manifest.get_command.assert_any_call("component.deployment.status")
        manifest.get_command.assert_any_call("component.cronjob.status")

    def test_error_bubbles_up(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_components.return_value = {
            "traefik": _mock_component_deployment(),
        }
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        with patch(
            "jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner"
        ) as mock_runner_cls:
            mock_runner_cls.return_value.run_command_sequence.side_effect = RuntimeError("API failure")
            manifest.get_command.return_value = Mock()
            handler = ComponentHandler(display_manager=Mock())

            with self.assertRaises(RuntimeError):
                handler.get_all_status()


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerCustomResourceWithoutStatus(unittest.TestCase):
    def _setup(self, manifest_fn: Mock, outputs: Mock, component: JupyterDeployComponentDefinitionV1) -> Mock:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_components.return_value = {"default-template": component}
        manifest_fn.return_value = manifest
        outputs.return_value.get_full_project_outputs.return_value = _CR_OUTPUTS
        return manifest

    def test_present_when_get_succeeds(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest = self._setup(mock_manifest_fn, mock_outputs, _mock_component_custom_resource())

        mock_runner: Mock = Mock()
        mock_runner.get_result_value_with_fallback.return_value = ""

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()
            handler = ComponentHandler(display_manager=Mock())
            results = handler.get_all_status()

        self.assertEqual(results[0]["status"], "Present")
        self.assertEqual(results[0]["status_category"], "healthy")
        manifest.get_command.assert_called_with("component.customresourcewithoutstatus.status")
        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["name"].value, "jupyterlab")
        self.assertEqual(cli_paramdefs["group"].value, "workspace.jupyter.org")
        self.assertEqual(cli_paramdefs["version"].value, "v1alpha1")
        self.assertEqual(cli_paramdefs["plural"].value, "workspacetemplates")
        self.assertEqual(cli_paramdefs["scope"].value, "shared-ns")

    def test_renders_details_and_sub_component_from_resource(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        component = JupyterDeployComponentDefinitionV1(
            **{  # type: ignore[arg-type]
                "type": "CustomResourceWithoutStatus",
                "scope": "workspace_shared_namespace",
                "resource-name": "jupyterlab",
                "crd-group": "workspace.jupyter.org",
                "crd-version": "v1alpha1",
                "crd-plural": "workspacetemplates",
                "details": {"path": ".metadata.namespace"},
                "sub-component": {"label": "access-strategy", "path": ".spec.defaultAccessStrategy.name"},
                "verbs": {"status": {"method": "k8s.custom.get"}},
            }
        )
        manifest = self._setup(mock_manifest_fn, mock_outputs, component)

        mock_runner: Mock = Mock()
        resource_json = (
            '{"metadata": {"namespace": "jupyter-k8s-shared"},'
            ' "spec": {"appType": "jupyterlab", "defaultAccessStrategy": {"name": "oauth-access-strategy"}}}'
        )
        mock_runner.get_result_value_with_fallback.return_value = resource_json

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()
            handler = ComponentHandler(display_manager=Mock())
            results = handler.get_all_status()

        self.assertEqual(results[0]["details"], "jupyter-k8s-shared")
        self.assertEqual(results[0]["sub_component"], "access-strategy: oauth-access-strategy")

    def test_missing_when_resource_not_found(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest = self._setup(mock_manifest_fn, mock_outputs, _mock_component_custom_resource())

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value.run_command_sequence.side_effect = ResourceNotFoundError(
                resource_kind="WorkspaceTemplate", resource_name="jupyterlab", original_message="not found"
            )
            manifest.get_command.return_value = Mock()
            handler = ComponentHandler(display_manager=Mock())
            results = handler.get_all_status()

        self.assertEqual(results[0]["status"], "Not Found")
        self.assertEqual(results[0]["status_category"], "degraded")

    def test_get_component_status_present(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest = self._setup(mock_manifest_fn, mock_outputs, _mock_component_custom_resource())
        manifest.get_component.return_value = _mock_component_custom_resource()

        mock_runner: Mock = Mock()
        mock_runner.get_result_value_with_fallback.return_value = ""

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()
            handler = ComponentHandler(display_manager=Mock())
            status = handler.get_component_status("default-template")

        self.assertEqual(status, "Present")

    def test_get_component_status_missing(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest = self._setup(mock_manifest_fn, mock_outputs, _mock_component_custom_resource())
        manifest.get_component.return_value = _mock_component_custom_resource()

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value.run_command_sequence.side_effect = ResourceNotFoundError(
                resource_kind="WorkspaceTemplate", resource_name="jupyterlab", original_message="not found"
            )
            manifest.get_command.return_value = Mock()
            handler = ComponentHandler(display_manager=Mock())
            status = handler.get_component_status("default-template")

        self.assertEqual(status, "Not Found")

    def test_show_component_returns_resource(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest = self._setup(mock_manifest_fn, mock_outputs, _mock_component_custom_resource())
        manifest.get_component.return_value = _mock_component_custom_resource()

        mock_runner: Mock = Mock()
        mock_command = Mock()
        mock_command.cmd = "component.customresourcewithoutstatus.show"
        mock_command.results = []

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = mock_command
            handler = ComponentHandler(display_manager=Mock())
            handler.show_component("default-template")

        manifest.get_command.assert_called_with("component.customresourcewithoutstatus.show")
        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["name"].value, "jupyterlab")
        self.assertEqual(cli_paramdefs["plural"].value, "workspacetemplates")


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerCustomResourceDefinition(unittest.TestCase):
    def _setup(self, manifest_fn: Mock, outputs: Mock) -> Mock:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        component = _mock_component_crd()
        manifest.get_components.return_value = {"workspace-crd": component}
        manifest.get_component.return_value = component
        manifest_fn.return_value = manifest
        # Cluster-scoped components resolve no namespace output.
        outputs.return_value.get_full_project_outputs.return_value = {}
        return manifest

    def test_present_omits_scope_and_renders_details(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest = self._setup(mock_manifest_fn, mock_outputs)

        mock_runner: Mock = Mock()
        resource_json = '{"spec": {"group": "workspace.jupyter.org", "versions": [{"name": "v1alpha1"}]}}'
        mock_runner.get_result_value_with_fallback.return_value = resource_json

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()
            handler = ComponentHandler(display_manager=Mock())
            results = handler.get_all_status()

        self.assertEqual(results[0]["status"], "Present")
        self.assertEqual(results[0]["status_category"], "healthy")
        self.assertEqual(results[0]["details"], "v1alpha1")
        manifest.get_command.assert_called_with("component.customresourcedefinition.status")
        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertNotIn("scope", cli_paramdefs)
        self.assertEqual(cli_paramdefs["name"].value, "workspaces.workspace.jupyter.org")
        self.assertEqual(cli_paramdefs["group"].value, "apiextensions.k8s.io")
        self.assertEqual(cli_paramdefs["plural"].value, "customresourcedefinitions")

    def test_not_found_when_crd_missing(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest = self._setup(mock_manifest_fn, mock_outputs)

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value.run_command_sequence.side_effect = ResourceNotFoundError(
                resource_kind="CustomResourceDefinition",
                resource_name="workspaces.workspace.jupyter.org",
                original_message="not found",
            )
            manifest.get_command.return_value = Mock()
            handler = ComponentHandler(display_manager=Mock())
            results = handler.get_all_status()

        self.assertEqual(results[0]["status"], "Not Found")
        self.assertEqual(results[0]["status_category"], "degraded")


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerShowComponent(unittest.TestCase):
    def test_calls_show_command_with_correct_args(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()
        mock_runner.get_result_value.return_value = ""

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            mock_command: Mock = Mock()
            mock_command.results = []
            manifest.get_command.return_value = mock_command

            handler = ComponentHandler(display_manager=Mock())
            handler.show_component("traefik")

        manifest.get_command.assert_called_once_with("component.deployment.show")
        mock_runner.run_command_sequence.assert_called_once()
        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["name"].value, "traefik")
        self.assertEqual(cli_paramdefs["scope"].value, "router-ns")

    def test_error_bubbles_up(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value.run_command_sequence.side_effect = RuntimeError("API failure")
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            with self.assertRaises(RuntimeError):
                handler.show_component("traefik")


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerGetComponentLogs(unittest.TestCase):
    def test_calls_logs_command_with_extra(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()
        mock_runner.get_result_value.return_value = "log line"

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            result = handler.get_component_logs("traefik", extra=["--tail=50", "--since=1h"])

        self.assertEqual(result, "log line")
        manifest.get_command.assert_called_once_with("component.deployment.logs")
        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["name"].value, "traefik")
        self.assertEqual(cli_paramdefs["scope"].value, "router-ns")
        self.assertEqual(cli_paramdefs["extra"].value, "--tail=50 --since=1h")

    def test_passes_empty_extra_when_none(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()
        mock_runner.get_result_value.return_value = ""

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            handler.get_component_logs("traefik")

        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["extra"].value, "")

    def test_error_bubbles_up(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value.run_command_sequence.side_effect = RuntimeError("API failure")
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            with self.assertRaises(RuntimeError):
                handler.get_component_logs("traefik")


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerRestartComponent(unittest.TestCase):
    def test_calls_restart_command(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            handler.restart_component("traefik")

        manifest.get_command.assert_called_once_with("component.deployment.restart")
        mock_runner.run_command_sequence.assert_called_once()
        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["name"].value, "traefik")
        self.assertEqual(cli_paramdefs["scope"].value, "router-ns")

    def test_error_bubbles_up(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value.run_command_sequence.side_effect = RuntimeError("API failure")
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            with self.assertRaises(RuntimeError):
                handler.restart_component("traefik")


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerTriggerComponent(unittest.TestCase):
    def test_calls_trigger_command_and_returns_job_name(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_cronjob()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()
        mock_runner.get_result_value.return_value = "jwt-rotator-manual-20250514"

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            result = handler.trigger_component("jwt-rotator")

        self.assertEqual(result, "jwt-rotator-manual-20250514")
        manifest.get_command.assert_called_once_with("component.cronjob.trigger")
        mock_runner.run_command_sequence.assert_called_once()
        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["name"].value, "jwt-rotator")
        self.assertEqual(cli_paramdefs["scope"].value, "router-ns")
        self.assertEqual(cli_paramdefs["query"].value, "app=jwt-rotator")

    def test_error_bubbles_up(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_cronjob()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value.run_command_sequence.side_effect = RuntimeError("API failure")
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            with self.assertRaises(RuntimeError):
                handler.trigger_component("jwt-rotator")


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerReconcileComponent(unittest.TestCase):
    def test_calls_reconcile_command_and_returns_output(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_helmrelease()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()
        mock_runner.get_result_value_with_fallback.return_value = "service/foo configured"

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            result = handler.reconcile_component("workspace-router-chart")

        self.assertEqual(result, "service/foo configured")
        manifest.get_command.assert_called_once_with("component.helmrelease.reconcile")
        mock_runner.run_command_sequence.assert_called_once()
        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        # resource-name overrides the component key when building the release name
        self.assertEqual(cli_paramdefs["name"].value, "jupyter-k8s-aws-oidc")
        self.assertEqual(cli_paramdefs["scope"].value, "router-ns")

    def test_raises_invalid_verb_for_reconcile_on_deployment(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        handler = ComponentHandler(display_manager=Mock())

        with self.assertRaises(InvalidComponentVerbError) as ctx:
            handler.reconcile_component("traefik")

        self.assertEqual(ctx.exception.verb, "reconcile")
        self.assertEqual(ctx.exception.component_type, "Deployment")

    def test_error_bubbles_up(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_helmrelease()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value.run_command_sequence.side_effect = RuntimeError("API failure")
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            with self.assertRaises(RuntimeError):
                handler.reconcile_component("workspace-router-chart")
