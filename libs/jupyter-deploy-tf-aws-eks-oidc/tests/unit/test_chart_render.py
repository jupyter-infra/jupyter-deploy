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


def _doc_chunks(rendered: str) -> dict[tuple[str, str], str]:
    """Split a multi-doc render into raw chunks keyed by (kind, name).

    Raw text (not parsed YAML) so per-document comparisons stay byte-level:
    parsing would erase exactly the class of drift the goldens exist to catch.
    """
    chunks: dict[tuple[str, str], str] = {}
    for chunk in rendered.split("\n---\n"):
        doc = yaml.safe_load(chunk)
        if not doc:
            continue
        # Boundary newlines belong to the multi-doc container, not the document:
        # the last doc of a file keeps its trailing newline, an inner one loses
        # it to the separator split.
        chunks[(doc["kind"], doc["metadata"]["name"])] = chunk.strip("\n")
    return chunks


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
class TestKarpenterNodepoolsGpuRender(unittest.TestCase):
    """The synthesized GPU entry adds a fenced pool without touching existing pools."""

    rendered: ClassVar[str]
    chunks: ClassVar[dict[tuple[str, str], str]]
    golden_chunks: ClassVar[dict[tuple[str, str], str]]
    gpu_pool: ClassVar[dict[str, Any]]
    cpu_pool: ClassVar[dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.rendered = _helm_template(
            "charts/karpenter-nodepools", "karpenter-nodepools", "values_karpenter_cpu_gpu.yaml"
        )
        cls.chunks = _doc_chunks(cls.rendered)
        cls.golden_chunks = _doc_chunks((DATA_DIR / "golden_karpenter_nodepools_cpu.yaml").read_text())
        cls.gpu_pool = yaml.safe_load(cls.chunks[("NodePool", "workspace-gpu")])
        cls.cpu_pool = yaml.safe_load(cls.chunks[("NodePool", "workspace-cpu")])

    def test_existing_docs_byte_identical(self) -> None:
        for key in [
            ("NodePool", "routing"),
            ("NodePool", "workspace-cpu"),
            ("EC2NodeClass", "routing"),
            ("EC2NodeClass", "workspace-cpu"),
        ]:
            self.assertEqual(
                self.golden_chunks[key],
                self.chunks[key],
                f"{key} rendered differently with the GPU entry present — Karpenter would "
                "drift-replace its nodes and restart the workspaces on them.",
            )

    def test_gpu_nodepool_role_label_and_taint(self) -> None:
        template = self.gpu_pool["spec"]["template"]
        self.assertEqual(template["metadata"]["labels"]["jupyter-deploy/role"], "workspaces-gpu")
        self.assertEqual(
            template["spec"]["taints"],
            [{"key": "jupyter-deploy/role", "value": "workspaces-gpu", "effect": "NoSchedule"}],
        )

    def test_gpu_nodepool_gpu_present_label(self) -> None:
        labels = self.gpu_pool["spec"]["template"]["metadata"]["labels"]
        self.assertEqual(labels.get("nvidia.com/gpu.present"), "true")

    def test_gpu_nodepool_gpu_limit(self) -> None:
        self.assertEqual(self.gpu_pool["spec"]["limits"].get("nvidia.com/gpu"), "4")
        self.assertNotIn("nvidia.com/gpu", self.cpu_pool["spec"]["limits"])

    def test_gpu_nodepool_instance_families(self) -> None:
        requirements = {req["key"]: req for req in self.gpu_pool["spec"]["template"]["spec"]["requirements"]}
        self.assertEqual(requirements["karpenter.k8s.aws/instance-family"]["values"], ["g4dn", "g5"])

    def test_gpu_ec2nodeclass_root_volume(self) -> None:
        nodeclass = yaml.safe_load(self.chunks[("EC2NodeClass", "workspace-gpu")])
        self.assertEqual(nodeclass["spec"]["blockDeviceMappings"][0]["ebs"]["volumeSize"], "100Gi")


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
