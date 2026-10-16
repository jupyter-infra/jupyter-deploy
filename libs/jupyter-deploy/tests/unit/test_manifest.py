import unittest
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.enum import OpenMode, StoreType
from jupyter_deploy.exceptions import (
    CommandNotImplementedError,
    ComponentNotFoundError,
    ImageNotFoundError,
    InvalidStoreTypeError,
    SecretNotFoundError,
)
from jupyter_deploy.manifest import (
    VOLUME_READINESS_COMMAND,
    VOLUME_SHOW_COMMAND,
    InvalidServiceError,
    JupyterDeployComponentDefinitionV1,
    JupyterDeployFlagV1,
    JupyterDeployImageDefinitionV1,
    JupyterDeployInstructionV1,
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

    def test_supports_proxy_true_when_connect_info_declared(self) -> None:
        manifest = JupyterDeployManifestV1(
            **{  # type: ignore
                "schema_version": 1,
                "template": {"name": "t", "engine": "terraform", "version": "1.0.0"},
                "commands": [{"cmd": "proxy.connect-info", "sequence": []}],
            }
        )
        self.assertTrue(manifest.supports_proxy())

    def test_supports_proxy_false_when_connect_info_absent(self) -> None:
        manifest = JupyterDeployManifestV1(
            **{  # type: ignore
                "schema_version": 1,
                "template": {"name": "t", "engine": "terraform", "version": "1.0.0"},
                "commands": [{"cmd": "host.status", "sequence": []}],
            }
        )
        self.assertFalse(manifest.supports_proxy())

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

    def test_parses_custom_resource_fields_and_aliases(self) -> None:
        manifest = self._make_manifest(
            components={
                "oauth-access-strategy": {
                    "type": "CustomResourceWithoutStatus",
                    "type-display": "WorkspaceAccessStrategy",
                    "scope": "workspace_shared_namespace",
                    "resource-name": "oauth-access-strategy",
                    "crd-group": "workspace.jupyter.org",
                    "crd-version": "v1alpha1",
                    "crd-plural": "workspaceaccessstrategies",
                    "details": {"path": ".metadata.namespace"},
                    "sub-component": {"label": "access-resources", "count": ".spec.accessResourceTemplates"},
                    "verbs": {"status": {"method": "k8s.custom.get"}},
                },
            }
        )
        component = manifest.get_component("oauth-access-strategy")

        self.assertEqual(component.type, "CustomResourceWithoutStatus")
        self.assertEqual(component.type_display, "WorkspaceAccessStrategy")
        self.assertEqual(component.resource_name, "oauth-access-strategy")
        self.assertEqual(component.crd_group, "workspace.jupyter.org")
        self.assertEqual(component.crd_version, "v1alpha1")
        self.assertEqual(component.crd_plural, "workspaceaccessstrategies")
        assert component.details is not None
        self.assertEqual(component.details.path, ".metadata.namespace")
        assert component.sub_component is not None
        self.assertEqual(component.sub_component.label, "access-resources")
        self.assertEqual(component.sub_component.count, ".spec.accessResourceTemplates")

    def test_parses_cluster_scoped_component_without_scope(self) -> None:
        manifest = self._make_manifest(
            components={
                "workspace-crd": {
                    "type": "CustomResourceDefinition",
                    "resource-name": "workspaces.workspace.jupyter.org",
                    "details": {"label": "apiVersion", "join": [".spec.group", ".spec.versions[0].name"]},
                    "verbs": {"status": {"method": "k8s.custom.get-cluster"}},
                },
            }
        )
        component = manifest.get_component("workspace-crd")

        # Cluster-scoped components declare no namespace; scope defaults to None.
        self.assertIsNone(component.scope)
        assert component.details is not None
        self.assertEqual(component.details.join, [".spec.group", ".spec.versions[0].name"])

    def test_optional_fields_default_to_none(self) -> None:
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

        self.assertIsNone(component.type_display)
        self.assertIsNone(component.crd_group)
        self.assertIsNone(component.details)
        self.assertIsNone(component.sub_component)

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


class TestCommandFlagsAndWhenSchema(unittest.TestCase):
    """Pydantic-level (trivially-local) validation of flags/when — the first line of defense."""

    def test_when_accepts_plain_and_negated_flag(self) -> None:
        self.assertEqual(
            JupyterDeployInstructionV1.model_validate({"api-name": "a.b.c", "when": "is-mng"}).when, "is-mng"
        )
        self.assertEqual(
            JupyterDeployInstructionV1.model_validate({"api-name": "a.b.c", "when": "!is-mng"}).when, "!is-mng"
        )

    def test_when_rejects_empty_and_multiple_bangs(self) -> None:
        for bad in ("", "!", "!!is-mng", "is!mng"):
            with self.assertRaises(ValidationError):
                JupyterDeployInstructionV1.model_validate({"api-name": "a.b.c", "when": bad})

    def test_arguments_default_to_empty_list(self) -> None:
        instruction = JupyterDeployInstructionV1.model_validate({"api-name": "core.coalesce-str"})
        self.assertEqual(instruction.arguments, [])

    def test_flag_name_rejects_bang(self) -> None:
        with self.assertRaises(ValidationError):
            JupyterDeployFlagV1.model_validate(
                {
                    "name": "is!mng",
                    "conditions": [
                        {
                            "left": {"source": "cli", "source-key": "name"},
                            "operator": "in",
                            "right": {"source": "output", "source-key": "mng"},
                        }
                    ],
                }
            )


class TestManifestOpen(unittest.TestCase):
    def _manifest(self, open_section: dict | None) -> JupyterDeployManifestV1:
        data: dict = {
            "schema_version": 1,
            "template": {"name": "mock", "engine": "terraform", "version": "1.0.0"},
        }
        if open_section is not None:
            data["open"] = open_section
        return JupyterDeployManifestV1.model_validate(data)

    def test_get_open_defaults_to_url_mode(self) -> None:
        manifest = self._manifest(None)
        open_config = manifest.get_open()
        self.assertEqual(open_config.get_mode(), OpenMode.URL)
        self.assertEqual(open_config.path, "/")

    def test_get_open_proxy_mode(self) -> None:
        manifest = self._manifest({"mode": "proxy", "path": "/lab"})
        open_config = manifest.get_open()
        self.assertEqual(open_config.get_mode(), OpenMode.PROXY)
        self.assertEqual(open_config.path, "/lab")

    def test_unknown_open_mode_falls_back_to_url(self) -> None:
        manifest = self._manifest({"mode": "carrier-pigeon"})
        self.assertEqual(manifest.get_open().get_mode(), OpenMode.URL)


class TestJupyterDeployManifestV1Volumes(unittest.TestCase):
    def _make_manifest(self, volumes: dict[str, Any] | None = None) -> JupyterDeployManifestV1:
        data: dict[str, Any] = {
            "schema_version": 1,
            "template": {"name": "test-template", "engine": "terraform", "version": "1.0.0"},
        }
        if volumes is not None:
            data["volumes"] = volumes
        return JupyterDeployManifestV1(**data)  # type: ignore

    def test_get_volumes_parses_static_and_dynamic(self) -> None:
        manifest = self._make_manifest(
            volumes={
                "static": [
                    {
                        "name": "home",
                        "type": "ebs",
                        "mount-point": "/home/jovyan",
                        "description": "home volume",
                        "volume-id-value": "data_volume_id",
                        "backups-map": "volume_backup_ids",
                    }
                ],
                "dynamic": [
                    {
                        "group": "additional-ebs",
                        "type": "ebs",
                        "inventory-value": "additional_ebs_volumes",
                        "name-path": ".name",
                        "mount-point-path": ".mount_point",
                        "volume-id-path": ".volume_id",
                        "description-path": ".mount_point",
                        "backups-map": "volume_backup_ids",
                    }
                ],
            }
        )

        volumes = manifest.get_volumes()

        self.assertEqual(volumes.static[0].name, "home")
        self.assertEqual(volumes.static[0].mount_point, "/home/jovyan")
        self.assertEqual(volumes.static[0].volume_id_value, "data_volume_id")
        self.assertEqual(volumes.dynamic[0].group, "additional-ebs")
        self.assertEqual(volumes.dynamic[0].inventory_value, "additional_ebs_volumes")
        self.assertEqual(volumes.dynamic[0].name_path, ".name")

    def test_get_volumes_raises_when_the_template_declares_none(self) -> None:
        """`jd volume` must fail with "not implemented for this template", not an empty list."""
        with self.assertRaises(CommandNotImplementedError):
            self._make_manifest().get_volumes()

    def test_static_and_dynamic_both_default_to_empty(self) -> None:
        volumes = self._make_manifest(volumes={"static": [], "dynamic": []}).get_volumes()

        self.assertEqual(volumes.static, [])
        self.assertEqual(volumes.dynamic, [])

    def test_a_kind_without_a_backups_map_parses_to_empty(self) -> None:
        """Omitting backups-map declares "this kind has no backup mechanism"; it must not be required."""
        volumes = self._make_manifest(
            volumes={
                "dynamic": [
                    {
                        "group": "additional-efs",
                        "type": "efs",
                        "inventory-value": "additional_efs_volumes",
                        "name-path": ".name",
                        "volume-id-path": ".volume_id",
                    }
                ]
            }
        ).get_volumes()

        self.assertEqual(volumes.dynamic[0].backups_map, "")

    def test_optional_paths_default_to_empty(self) -> None:
        volumes = self._make_manifest(
            volumes={
                "dynamic": [
                    {
                        "group": "g",
                        "inventory-value": "v",
                        "name-path": ".name",
                        "volume-id-path": ".volume_id",
                    }
                ]
            }
        ).get_volumes()

        self.assertEqual(volumes.dynamic[0].mount_point_path, "")
        self.assertEqual(volumes.dynamic[0].description_path, "")
        self.assertEqual(volumes.dynamic[0].type, "")

    def test_static_volume_id_value_is_required(self) -> None:
        """There is no sensible default: without it the volume has no id to resolve."""
        with self.assertRaises(ValidationError):
            self._make_manifest(volumes={"static": [{"name": "home"}]})

    def test_dynamic_inventory_value_and_name_path_are_required(self) -> None:
        with self.assertRaises(ValidationError):
            self._make_manifest(volumes={"dynamic": [{"group": "g", "volume-id-path": ".volume_id"}]})

    def test_declaration_order_is_preserved(self) -> None:
        """The FIRST static entry is the default `--name`, so ordering is part of the contract."""
        volumes = self._make_manifest(
            volumes={
                "static": [
                    {"name": "home", "volume-id-value": "a"},
                    {"name": "scratch", "volume-id-value": "b"},
                ]
            }
        ).get_volumes()

        self.assertEqual([v.name for v in volumes.static], ["home", "scratch"])

    def test_a_duplicated_static_name_is_refused(self) -> None:
        """The name keys the backups map, so a duplicate restores one volume from another's backup."""
        with self.assertRaises(ValidationError) as ctx:
            self._make_manifest(
                volumes={
                    "static": [
                        {"name": "home", "volume-id-value": "a"},
                        {"name": "home", "volume-id-value": "b"},
                    ]
                }
            )

        self.assertIn("static name", str(ctx.exception))
        self.assertIn("home", str(ctx.exception))

    def test_a_duplicated_group_is_refused(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            self._make_manifest(
                volumes={
                    "dynamic": [
                        {"group": "extra", "inventory-value": "v1", "name-path": ".name", "volume-id-path": ".id"},
                        {"group": "extra", "inventory-value": "v2", "name-path": ".name", "volume-id-path": ".id"},
                    ]
                }
            )

        self.assertIn("group", str(ctx.exception))
        self.assertIn("extra", str(ctx.exception))

    def test_every_duplicated_name_is_named_at_once(self) -> None:
        """One message listing all of them, so a bulk mis-declaration is fixed in one pass."""
        with self.assertRaises(ValidationError) as ctx:
            self._make_manifest(
                volumes={
                    "static": [
                        {"name": "home", "volume-id-value": "a"},
                        {"name": "home", "volume-id-value": "b"},
                        {"name": "scratch", "volume-id-value": "c"},
                        {"name": "scratch", "volume-id-value": "d"},
                        {"name": "cache", "volume-id-value": "e"},
                    ]
                }
            )

        message = str(ctx.exception)
        self.assertIn("home", message)
        self.assertIn("scratch", message)
        self.assertNotIn("cache", message)

    def test_a_name_repeated_three_times_is_reported_once(self) -> None:
        """The count is not the point; a reader needs the offending name, not how often it appears."""
        with self.assertRaises(ValidationError) as ctx:
            self._make_manifest(
                volumes={
                    "static": [
                        {"name": "home", "volume-id-value": "a"},
                        {"name": "home", "volume-id-value": "b"},
                        {"name": "home", "volume-id-value": "c"},
                    ]
                }
            )

        self.assertEqual(str(ctx.exception).count("'home'"), 1)

    def test_a_static_name_may_equal_a_group(self) -> None:
        """Two namespaces: a group labels a set, a static name identifies one volume."""
        volumes = self._make_manifest(
            volumes={
                "static": [{"name": "home", "volume-id-value": "a"}],
                "dynamic": [{"group": "home", "inventory-value": "v", "name-path": ".name", "volume-id-path": ".id"}],
            }
        ).get_volumes()

        self.assertEqual(volumes.static[0].name, "home")
        self.assertEqual(volumes.dynamic[0].group, "home")


class TestJupyterDeployManifestV1VolumeReadiness(unittest.TestCase):
    """Declaring the command is the opt-in; there is no schema field for it.

    Same contract as `supports_proxy`: presence of a named command, not a flag. That keeps the four command
    names this feature runs consistent -- the other three are literals in the handler too -- and leaves a
    template no way to half-declare the check.
    """

    @staticmethod
    def _manifest(commands: list[dict[str, Any]]) -> JupyterDeployManifestV1:
        data: dict[str, Any] = {
            "schema_version": 1,
            "template": {"name": "test-template", "engine": "terraform", "version": "1.0.0"},
            "volumes": {"static": [{"name": "home", "volume-id-value": "v"}]},
            "commands": commands,
        }
        return JupyterDeployManifestV1(**data)  # type: ignore[arg-type]

    def test_declaring_the_command_opts_in(self) -> None:
        manifest = self._manifest(
            [{"cmd": VOLUME_READINESS_COMMAND, "sequence": [{"api-name": "aws.ec2.verify-instance-stopped"}]}]
        )
        self.assertTrue(manifest.supports_volume_readiness())

    def test_omitting_it_opts_out(self) -> None:
        """A template whose storage is always safe to restore is checked for nothing, not guessed at."""
        # Another volume command, empty: only the command NAME decides this, so an instruction here would
        # imply the sequence is consulted.
        manifest = self._manifest([{"cmd": VOLUME_SHOW_COMMAND, "sequence": []}])
        self.assertFalse(manifest.supports_volume_readiness())

    def test_a_template_with_no_commands_opts_out(self) -> None:
        self.assertFalse(self._manifest([]).supports_volume_readiness())
