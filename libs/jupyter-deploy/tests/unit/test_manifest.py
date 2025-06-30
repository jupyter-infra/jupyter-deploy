import unittest
from pathlib import Path
from typing import Any

import yaml

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.manifest import JupyterDeployManifestV1


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
        self.assertEqual(
            manifest.get_command("server.status"),
            manifest.commands[0],  # type: ignore
        )

    def test_manifest_v1_not_found_command_raises_not_implemented_error(self) -> None:
        manifest = JupyterDeployManifestV1(
            **self.manifest_v1_parsed_content  # type: ignore
        )
        with self.assertRaises(NotImplementedError):
            manifest.get_command("cmd_does_not_exist")
