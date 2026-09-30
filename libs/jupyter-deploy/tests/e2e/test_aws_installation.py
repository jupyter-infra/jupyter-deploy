"""AWS install track tests — validate the CLI works with the [aws] extra.

These tests run in the ``aws`` install track where ``jupyter-deploy[aws]``
is installed alongside the base template.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestAwsInstallation(unittest.TestCase):
    def test_boto3_importable(self) -> None:
        import boto3  # noqa: F401

    def test_botocore_importable(self) -> None:
        import botocore  # noqa: F401

    def test_provider_factory_resolves(self) -> None:
        from jupyter_deploy.provider.aws import aws_runner  # noqa: F401


def default_template_installed() -> bool:
    """Whether some installed package provides the template `jd init` defaults to."""
    from jupyter_deploy import constants, template_utils

    return any(constants.DEFAULT_TEMPLATE in templates for templates in template_utils.TEMPLATES.values())


@unittest.skipIf(default_template_installed(), "the default template is installed in this track")
class TestDefaultTemplateNotInstalled(unittest.TestCase):
    """The aws and aws-k8s tracks install the base template but NOT the default one, which is the
    shape of an existing project upgrading to a CLI whose default template changed.

    `jd init` must therefore fail with an actionable message rather than a traceback: it is the
    first thing such a user sees. HOME is relocated so that a preferences file cannot resolve the
    default for them.

    Skipped rather than filtered by track, because the aws-proxy track collects this file too and
    does install the default template -- and because the workspace has every template installed,
    so a bare `uv run pytest` would otherwise fail here.
    """

    def _run_bare_init(self, tmp_dir: str) -> subprocess.CompletedProcess[str]:
        project_dir = Path(tmp_dir) / "project"
        project_dir.mkdir()
        return subprocess.run(
            ["jd", "init", str(project_dir)],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "HOME": tmp_dir},
        )

    def test_init_fails_without_the_default_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = self._run_bare_init(tmp_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("is not installed", result.stdout)

    def test_init_names_the_package_that_provides_the_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = self._run_bare_init(tmp_dir)

        self.assertIn("uv add", result.stdout)
        self.assertIn("jupyter-deploy-tf-aws-ec2-jupyterlab", result.stdout)

    def test_init_offers_the_installed_template_as_a_preference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = self._run_bare_init(tmp_dir)

        self.assertIn("aws:ec2:base", result.stdout)
        self.assertIn("jd preferences set --default-template", result.stdout)
