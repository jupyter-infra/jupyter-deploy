"""Unit tests for EndToEndDeployment: project-dir resolution and the variables.yaml override writers."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import yaml
from jupyter_deploy import constants as jd_constants

from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.suite_config import SuiteConfig


class TestGetVariablesYamlPath(unittest.TestCase):
    def test_loads_the_suite_config_first(self) -> None:
        # spec=SuiteConfig: `project_dir` is only set by load(), so reading it earlier raises, as it
        # did when an override writer was the first call on a fresh deployment.
        suite_config = Mock(spec=SuiteConfig)
        suite_config.load.side_effect = lambda: setattr(suite_config, "project_dir", Path("/proj"))

        path = EndToEndDeployment(suite_config).get_variables_yaml_path()

        suite_config.load.assert_called_once_with()
        self.assertEqual(path, Path("/proj") / jd_constants.VARIABLES_FILENAME)


class TestOverrideValues(unittest.TestCase):
    def test_update_then_delete_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            variables_yaml = Path(tmp) / jd_constants.VARIABLES_FILENAME
            variables_yaml.write_text(
                "schema_version: 2\nrequired:\n  domain: example.com\nrequired_sensitive: {}\n"
                "overrides:\n  a: 1\n  b: 2\n"
            )
            suite_config = Mock(spec=SuiteConfig)
            suite_config.project_dir = Path(tmp)
            deployment = EndToEndDeployment(suite_config)

            deployment.update_override_value("c", True)
            deployment.delete_override_value("a")
            deployment.delete_override_value("missing")

            self.assertEqual(yaml.safe_load(variables_yaml.read_text())["overrides"], {"b": 2, "c": True})
            self.assertIsNone(deployment.read_override_value("a"))
            self.assertEqual(yaml.safe_load(variables_yaml.read_text())["required"], {"domain": "example.com"})
