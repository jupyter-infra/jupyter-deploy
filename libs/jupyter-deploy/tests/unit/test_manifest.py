import unittest
from pathlib import Path
from typing import Any

import yaml

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.enum import StoreType
from jupyter_deploy.exceptions import (
    CommandNotImplementedError,
    ComponentNotFoundError,
    ImageNotFoundError,
    InvalidStoreTypeError,
    SecretNotFoundError,
)
from jupyter_deploy.manifest import (
    InvalidServiceError,
    JupyterDeployComponentDefinitionV1,
    JupyterDeployImageDefinitionV1,
    JupyterDeployManifestV1,
    JupyterDeployProjectStoreV1,
)


class TestJupyterDeployManifestV1(unittest.TestCase):
    manifest_v1_content: str
    manifest_v1_parsed_content: Any

    @classmethod
    def setUpClass(cls) -> None:
        mock_manifest_path = Path(__file__).parent / "mock_manifest.yaml"
        with open(mock_manifest_path) as f:
            cls.manifest_v1_content = f.read()
        cls.manifest_v1_parsed_content = yaml.safe_load(cls.manifest_v1_content)

    def test_can_parse_manifest_v1(self) -> None:
        JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )

    def test_manifest_v1_get_engine(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        self.assertEqual(manifest.get_engine(), EngineType.TERRAFORM)

    def test_manifest_v1_get_declared_value_happy_path(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        self.assertEqual(
            manifest.get_declared_value("aws_region"),
            manifest.values[1],  # type: ignore
        )

    def test_manifest_v1_get_declared_value_raises_not_implement_error(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        with self.assertRaises(NotImplementedError):
            manifest.get_declared_value("i_am_not_declared")

    def test_manifest_v1_get_command_happy_path(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        manifest.get_command("server.status")  # should not raise

    def test_manifest_v1_not_found_command_raises_not_implemented_error(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        with self.assertRaises(NotImplementedError):
            manifest.get_command("cmd_does_not_exist")

    def test_manifest_v1_has_command_found(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        self.assertTrue(manifest.has_command("host.status"))

    def test_manifest_v1_has_command_not_found(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        self.assertFalse(manifest.has_command("i.do.not.exist"))

    def test_manifest_v1_get_secrets(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        secrets = manifest.get_secrets()
        self.assertEqual(len(secrets), 2)
        self.assertEqual(secrets[0].name, "oauth_app_client_secret")
        self.assertEqual(secrets[0].source_key, "secret_arn")

    def test_manifest_v1_get_secret_found(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        secret = manifest.get_secret("oauth_app_client_secret")
        self.assertEqual(secret.name, "oauth_app_client_secret")
        self.assertEqual(secret.source, "output")
        self.assertEqual(secret.source_key, "secret_arn")

    def test_manifest_v1_get_secret_raises_when_not_found(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        with self.assertRaises(SecretNotFoundError):
            manifest.get_secret("i_do_not_exist")

    def test_manifest_v1_get_secrets_empty_when_not_declared(self) -> None:
        manifest = JupyterDeployManifestV1(
            schema_version=1,
            template={"name": "test", "engine": "terraform", "version": "1.0.0"},  # type: ignore
        )
        self.assertEqual(manifest.get_secrets(), [])
        with self.assertRaises(SecretNotFoundError):
            manifest.get_secret("anything")

    def test_manifest_v1_has_secret_reveal_command(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        self.assertTrue(manifest.has_command("secret.reveal"))

    def test_manifest_v1_get_services(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        self.assertListEqual(manifest.get_services(), ["jupyter", "traefik", "oauth"])

    def test_manifest_v1_get_validated_service(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        for svc in ["jupyter", "traefik", "oauth"]:
            self.assertEqual(manifest.get_validated_service(svc), svc)

    def test_manifest_v1_get_validated_service_default_return_first_value(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        self.assertEqual(manifest.get_validated_service("default"), "jupyter")

    def test_manifest_v1_get_validated_service_all_allowed(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        self.assertEqual(manifest.get_validated_service("all", allow_all=True), "all")

    def test_manifest_v1_get_validated_service_all_disallowed(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        with self.assertRaises(InvalidServiceError):
            manifest.get_validated_service("all", allow_all=False)


class TestJupyterDeployProjectStoreV1(unittest.TestCase):
    def _make_manifest(self, project_store: dict[str, Any] | None = None) -> JupyterDeployManifestV1:
        data: dict[str, Any] = {
            "schema_version": 1,
            "template": {"name": "test-template", "engine": "terraform", "version": "1.0.0"},
        }
        if project_store is not None:
            data["project_store"] = project_store
        return JupyterDeployManifestV1(**data)  # type: ignore

    def test_parse_project_store_section(self) -> None:
        project_store = JupyterDeployProjectStoreV1(**{"store-type": "s3-ddb"})  # type: ignore
        self.assertEqual(project_store.store_type, "s3-ddb")

    def test_has_project_store_true(self) -> None:
        manifest = self._make_manifest(project_store={"store-type": "s3-ddb"})
        self.assertTrue(manifest.has_project_store())

    def test_has_project_store_false(self) -> None:
        manifest = self._make_manifest()
        self.assertFalse(manifest.has_project_store())

    def test_get_store_type_s3_only(self) -> None:
        project_store = JupyterDeployProjectStoreV1(**{"store-type": "s3-only"})  # type: ignore
        self.assertEqual(project_store.get_store_type(), StoreType.S3_ONLY)

    def test_get_store_type_s3_ddb(self) -> None:
        project_store = JupyterDeployProjectStoreV1(**{"store-type": "s3-ddb"})  # type: ignore
        self.assertEqual(project_store.get_store_type(), StoreType.S3_DDB)

    def test_get_store_type_invalid_raises(self) -> None:
        project_store = JupyterDeployProjectStoreV1(**{"store-type": "gcs"})  # type: ignore
        with self.assertRaises(InvalidStoreTypeError) as ctx:
            project_store.get_store_type()
        self.assertEqual(ctx.exception.store_type, "gcs")
        self.assertIn("s3-only", ctx.exception.valid_store_types)
        self.assertIn("s3-ddb", ctx.exception.valid_store_types)

    def test_compute_project_id(self) -> None:
        manifest = self._make_manifest()
        result = manifest.compute_project_id("dep-abc123")
        self.assertEqual(result, "test-template-dep-abc123")


class TestJupyterDeployManifestV1Components(unittest.TestCase):
    def _make_manifest(self, components: dict[str, Any] | None = None) -> JupyterDeployManifestV1:
        data: dict[str, Any] = {
            "schema_version": 1,
            "template": {"name": "test-template", "engine": "terraform", "version": "1.0.0"},
        }
        if components is not None:
            data["components"] = components
        return JupyterDeployManifestV1(**data)  # type: ignore

    def test_get_components_parses_manifest(self) -> None:
        manifest = self._make_manifest(
            components={
                "traefik": {
                    "type": "Deployment",
                    "scope": "router_namespace",
                    "verbs": {
                        "status": {"method": "k8s.apps.get-deployment-status"},
                        "restart": {"method": "k8s.apps.rollout-restart"},
                    },
                },
                "jwt-rotator": {
                    "type": "CronJob",
                    "scope": "router_namespace",
                    "verbs": {
                        "status": {"method": "k8s.batch.get-cronjob-status"},
                        "trigger": {"method": "k8s.batch.create-job-from-cronjob"},
                    },
                },
            }
        )
        components = manifest.get_components()

        self.assertEqual(len(components), 2)
        self.assertIn("traefik", components)
        self.assertIn("jwt-rotator", components)

    def test_get_component_returns_definition(self) -> None:
        manifest = self._make_manifest(
            components={
                "traefik": {
                    "type": "Deployment",
                    "scope": "router_namespace",
                    "verbs": {"status": {"method": "k8s.apps.get-deployment-status"}},
                },
            }
        )
        component = manifest.get_component("traefik")

        self.assertIsInstance(component, JupyterDeployComponentDefinitionV1)
        self.assertEqual(component.type, "Deployment")
        self.assertEqual(component.scope, "router_namespace")
        self.assertIn("status", component.verbs)
        self.assertEqual(component.verbs["status"].method, "k8s.apps.get-deployment-status")

    def test_get_component_raises_not_found(self) -> None:
        manifest = self._make_manifest(
            components={
                "traefik": {
                    "type": "Deployment",
                    "scope": "ns",
                    "verbs": {"status": {"method": "k8s.apps.get-deployment-status"}},
                },
            }
        )
        with self.assertRaises(ComponentNotFoundError) as ctx:
            manifest.get_component("unknown")

        self.assertEqual(ctx.exception.component_name, "unknown")
        self.assertIn("traefik", ctx.exception.valid_components)

    def test_get_components_raises_when_none(self) -> None:
        manifest = self._make_manifest()

        with self.assertRaises(CommandNotImplementedError):
            manifest.get_components()

    def test_get_component_raises_when_none(self) -> None:
        manifest = self._make_manifest()

        with self.assertRaises(CommandNotImplementedError):
            manifest.get_component("traefik")


class TestJupyterDeployManifestV1Images(unittest.TestCase):
    def _make_manifest(self, images: dict[str, Any] | None = None) -> JupyterDeployManifestV1:
        data: dict[str, Any] = {
            "schema_version": 1,
            "template": {"name": "test-template", "engine": "terraform", "version": "1.0.0"},
        }
        if images is not None:
            data["images"] = images
        return JupyterDeployManifestV1(**data)  # type: ignore

    def test_get_images_parses_manifest(self) -> None:
        manifest = self._make_manifest(
            images={
                "jupyterlab": {
                    "description": "JupyterLab workspace image",
                    "repository-output": "ecr_repo_name",
                    "tag-output": "image_tag",
                },
                "worker": {
                    "description": "Background worker",
                    "repository-output": "worker_repo",
                    "tag-output": "worker_tag",
                },
            }
        )
        images = manifest.get_images()

        self.assertEqual(len(images), 2)
        self.assertIn("jupyterlab", images)
        self.assertIn("worker", images)

    def test_get_image_returns_definition(self) -> None:
        manifest = self._make_manifest(
            images={
                "jupyterlab": {
                    "description": "JupyterLab workspace image",
                    "repository-output": "ecr_repo_name",
                    "tag-output": "image_tag",
                },
            }
        )
        image = manifest.get_image("jupyterlab")

        self.assertIsInstance(image, JupyterDeployImageDefinitionV1)
        self.assertEqual(image.description, "JupyterLab workspace image")
        self.assertEqual(image.repository_output, "ecr_repo_name")
        self.assertEqual(image.tag_output, "image_tag")

    def test_get_image_raises_not_found(self) -> None:
        manifest = self._make_manifest(
            images={
                "jupyterlab": {
                    "description": "JupyterLab workspace image",
                    "repository-output": "ecr_repo_name",
                    "tag-output": "image_tag",
                },
            }
        )
        with self.assertRaises(ImageNotFoundError) as ctx:
            manifest.get_image("unknown")

        self.assertEqual(ctx.exception.image_name, "unknown")
        self.assertIn("jupyterlab", ctx.exception.valid_images)

    def test_get_images_raises_when_none(self) -> None:
        manifest = self._make_manifest()

        with self.assertRaises(CommandNotImplementedError):
            manifest.get_images()

    def test_get_image_raises_when_none(self) -> None:
        manifest = self._make_manifest()

        with self.assertRaises(CommandNotImplementedError):
            manifest.get_image("jupyterlab")
