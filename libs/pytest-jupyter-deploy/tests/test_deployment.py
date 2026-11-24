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
    def test_restore_writes_back_set_keys_and_resets_unset_ones(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            variables_yaml = Path(tmp) / jd_constants.VARIABLES_FILENAME
            variables_yaml.write_text(
                "schema_version: 2\nrequired:\n  domain: example.com\nrequired_sensitive: {}\noverrides:\n  a: 1\n"
            )
            suite_config = Mock(spec=SuiteConfig)
            suite_config.project_dir = Path(tmp)
            deployment = EndToEndDeployment(suite_config)
            deployment.ensure_deployed_with = Mock()  # type: ignore[method-assign]

            snapshot = deployment.snapshot_overrides(["a", "b"])
            deployment.update_override_value("a", 2)
            deployment.update_override_value("b", True)
            deployment.restore_overrides(snapshot)

            self.assertEqual(snapshot, {"a": 1, "b": None})
            self.assertEqual(deployment.read_override_value("a"), 1)
            deployment.ensure_deployed_with.assert_called_once_with(["--reset-variable", "b"], timeout_seconds=None)

    def test_config_refused_with_override_restores_the_file_either_way(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            variables_yaml = Path(tmp) / jd_constants.VARIABLES_FILENAME
            variables_yaml.write_text(
                "schema_version: 2\nrequired:\n  domain: example.com\nrequired_sensitive: {}\noverrides:\n  a: 1\n"
            )
            suite_config = Mock(spec=SuiteConfig)
            suite_config.project_dir = Path(tmp)
            deployment = EndToEndDeployment(suite_config)
            deployment._cli = Mock()
            deployment._cli.run_command_expecting_failure.return_value = "refused"

            self.assertEqual(deployment.config_refused_with_override("a", 2), "refused")
            self.assertEqual(deployment.config_refused_with_override("b", True), "refused")

            deployment._cli.run_command_expecting_failure.assert_called_with(["jupyter-deploy", "config"])
            self.assertEqual(deployment.read_override_value("a"), 1)
            self.assertIsNone(deployment.read_override_value("b"))

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
