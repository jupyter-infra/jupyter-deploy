"""Render pins for the local helm charts.

Renders each chart with `helm template` against fixture values in
chart_render_data/ that mirror what the terraform layer injects, and compares
the output to committed goldens. The karpenter golden is compared byte for
byte: Karpenter hashes a NodePool's spec.template, so any byte change to a
rendered pool drift-replaces its nodes and restarts the workspaces on them.
Regenerate goldens deliberately with:
JD_UPDATE_GOLDENS=1 uv run pytest tests/unit/test_chart_render.py
"""

import os
import shutil
import subprocess
import unittest
from pathlib import Path
from typing import Any, ClassVar

import yaml

from jupyter_deploy_tf_aws_eks_oidc.template import TEMPLATE_PATH

DATA_DIR = Path(__file__).parent / "chart_render_data"
_HELM = shutil.which("helm")

# CI must never skip these silently (the byte-identity guarantee would vanish
# without a red build); laptops without helm may.
_SKIP_WITHOUT_HELM = unittest.skipIf(_HELM is None and not os.environ.get("CI"), "helm not installed")


def _helm_template(chart_dir: str, release_name: str, values_file: str | None) -> str:
    cmd = ["helm", "template", release_name, str(TEMPLATE_PATH / chart_dir)]
    if values_file is not None:
        cmd.extend(["-f", str(DATA_DIR / values_file)])
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AssertionError(f"helm template failed for {chart_dir}: {result.stderr}")
    return result.stdout


def _workspace_template_docs(rendered: str) -> list[dict[str, Any]]:
    docs = [doc for doc in yaml.safe_load_all(rendered) if doc]
    return [doc for doc in docs if doc.get("kind") == "WorkspaceTemplate"]


class GoldenComparisonTestCase(unittest.TestCase):
    def compare_to_golden(self, rendered: str, golden_name: str) -> None:
        golden_path = DATA_DIR / golden_name
        if os.environ.get("JD_UPDATE_GOLDENS"):
            golden_path.write_text(rendered)
            return
        self.assertEqual(
            golden_path.read_text(),
            rendered,
            f"{golden_name} drifted from the chart render. If the change is deliberate and its "
            "node-replacement impact is understood, regenerate with JD_UPDATE_GOLDENS=1.",
        )


@_SKIP_WITHOUT_HELM
class TestKarpenterNodepoolsCpuRender(GoldenComparisonTestCase):
    """Default (flag-off) karpenter-nodepools render is byte-stable."""

    rendered: ClassVar[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.rendered = _helm_template("charts/karpenter-nodepools", "karpenter-nodepools", "values_karpenter_cpu.yaml")

    def test_render_matches_golden(self) -> None:
        self.compare_to_golden(self.rendered, "golden_karpenter_nodepools_cpu.yaml")


@_SKIP_WITHOUT_HELM
class TestWorkspaceDefaultsDefaultRender(GoldenComparisonTestCase):
    """Default workspace-defaults render carries exactly the jupyterlab template."""

    rendered: ClassVar[str]
    templates: ClassVar[list[dict[str, Any]]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.rendered = _helm_template(
            "charts/workspace-defaults", "workspace-defaults", "values_workspace_defaults_default.yaml"
        )
        cls.templates = _workspace_template_docs(cls.rendered)

    def test_single_template_rendered(self) -> None:
        names = [doc["metadata"]["name"] for doc in self.templates]
        self.assertEqual(names, ["jupyterlab"])

    def test_jupyterlab_doc_matches_golden(self) -> None:
        self.compare_to_golden(self.rendered, "golden_workspace_defaults_default.yaml")

    def test_jupyterlab_spec_matches_golden_semantically(self) -> None:
        golden = _workspace_template_docs((DATA_DIR / "golden_workspace_defaults_default.yaml").read_text())
        self.assertEqual(len(golden), 1)
        self.assertEqual(golden[0], self.templates[0])
