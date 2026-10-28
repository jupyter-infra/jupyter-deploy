"""Unit tests for EndToEndDeployment: project-dir resolution must not depend on call order."""

import unittest
from pathlib import Path
from unittest.mock import Mock

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
