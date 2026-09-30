"""AWS+proxy install track tests — validate the CLI works with the [aws,proxy] extra.

These tests run in the ``aws-proxy`` install track where ``jupyter-deploy[aws,proxy]`` is
installed (the client proxy resolves from prod PyPI). They guard the install contract that
``jd open`` / ``jd proxy`` rely on: the separate client-proxy package is present, and its
console script resolves the way :func:`resolve_console_script` looks for it (next to the
interpreter, then PATH). The positive counterpart to ``test_bare_installation`` — which
asserts the proxy is ABSENT without the extra.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestProxyInstallation(unittest.TestCase):
    def test_client_proxy_package_installed(self) -> None:
        # The [proxy] extra ships the separate client-proxy package. `jd` never imports it (it
        # shells out to the console script), but the package must be present for that script to exist.
        import jupyter_deploy_client_proxy  # noqa: F401

    def test_proxy_console_script_on_path(self) -> None:
        self.assertIsNotNone(shutil.which("jupyter-deploy-client-proxy"))

    def test_resolve_console_script_finds_proxy(self) -> None:
        # Mirror the exact resolution `jd` uses to launch the proxy: next to sys.executable, then
        # PATH. If it can't find the script, `jd open` fails at proxy launch — so assert we get a
        # real absolute path, not the bare-name last-resort fallback.
        from jupyter_deploy.proxy.proxy_manager import resolve_console_script

        resolved = resolve_console_script("jupyter-deploy-client-proxy")
        self.assertTrue(Path(resolved).is_absolute())
        self.assertTrue(Path(resolved).exists())

    def test_proxy_console_script_runs(self) -> None:
        # The entry point actually imports and runs — catches a broken module path in the
        # client-proxy [project.scripts] that a mere PATH check would miss.
        result = subprocess.run(
            ["jupyter-deploy-client-proxy", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class TestDefaultTemplateInit(unittest.TestCase):
    """`jd init` with no flags must resolve its default template and scaffold a project.

    This track is the only one that installs the default template, so it is the only place the
    happy path can be asserted. `jd init` writes files and makes no cloud call, which is what
    keeps it a smoke test. HOME is relocated per test: the default template also comes from a
    preferences file under the home directory, and these tests are about the built-in default.
    """

    def test_init_with_no_flags_scaffolds_the_default_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "project"
            project_dir.mkdir()

            result = subprocess.run(
                ["jd", "init", str(project_dir)],
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, "HOME": tmp_dir},
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = project_dir / "manifest.yaml"
            self.assertTrue(manifest.exists(), f"no manifest in {list(project_dir.iterdir())}")
            self.assertIn("tf-aws-ec2-jupyterlab", manifest.read_text())

    def test_init_reports_which_template_it_chose(self) -> None:
        # The user typed no template, so the CLI has to say which one it used -- otherwise the
        # choice is only discoverable by reading the scaffolded files.
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "project"
            project_dir.mkdir()

            result = subprocess.run(
                ["jd", "init", str(project_dir)],
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, "HOME": tmp_dir},
            )

            self.assertIn("No template specified", result.stdout)
            self.assertIn("aws:ec2:jupyterlab", result.stdout)
