import json
import subprocess
import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.enum import StatusCategory
from jupyter_deploy.exceptions import (
    InstructionError,
    InstructionNotFoundError,
    InvalidKubernetesClusterTargetError,
    ResourceNotFoundError,
)
from jupyter_deploy.provider.helm.helm_runner import HelmApiRunner
from jupyter_deploy.provider.resolved_argdefs import StrResolvedInstructionArgument

_RUN = "jupyter_deploy.provider.helm.helm_runner.cmd_utils.run_cmd_and_capture_output"


def _build_args(
    name: str = "workspace-router", scope: str = "jupyter-router", expected_cluster_config: str = ""
) -> dict:
    args = {
        "name": StrResolvedInstructionArgument(argument_name="name", value=name),
        "scope": StrResolvedInstructionArgument(argument_name="scope", value=scope),
    }
    if expected_cluster_config:
        args["expected_cluster_config"] = StrResolvedInstructionArgument(
            argument_name="expected_cluster_config", value=expected_cluster_config
        )
    return args


def _make_runner() -> HelmApiRunner:
    return HelmApiRunner(display_manager=Mock(), kubeconfig_path="/tmp/kubeconfig")


class TestHelmApiRunnerStatus(unittest.TestCase):
    @patch(_RUN)
    def test_deployed_is_healthy(self, mock_run: Mock) -> None:
        mock_run.return_value = json.dumps({"info": {"status": "deployed"}, "version": 3})
        runner = _make_runner()

        result = runner.execute_instruction("helm.status", _build_args())

        self.assertEqual(result["Status"].value, "deployed")
        self.assertEqual(result["StatusCategory"].value, StatusCategory.HEALTHY)
        # Details is the target namespace; with no `namespace` in the payload it falls back to scope.
        self.assertEqual(result["Details"].value, "jupyter-router")

    @patch(_RUN)
    def test_pending_is_in_progress(self, mock_run: Mock) -> None:
        mock_run.return_value = json.dumps({"info": {"status": "pending-upgrade"}, "version": 4})
        runner = _make_runner()

        result = runner.execute_instruction("helm.status", _build_args())

        self.assertEqual(result["StatusCategory"].value, StatusCategory.IN_PROGRESS)

    @patch(_RUN)
    def test_failed_is_degraded(self, mock_run: Mock) -> None:
        mock_run.return_value = json.dumps({"info": {"status": "failed"}, "version": 1})
        runner = _make_runner()

        result = runner.execute_instruction("helm.status", _build_args())

        self.assertEqual(result["StatusCategory"].value, StatusCategory.DEGRADED)

    @patch(_RUN)
    def test_release_not_found_raises(self, mock_run: Mock) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["helm"], stderr="Error: release: not found"
        )
        runner = _make_runner()

        with self.assertRaises(ResourceNotFoundError):
            runner.execute_instruction("helm.status", _build_args())


class TestHelmApiRunnerStatusDetailsAndSubComponent(unittest.TestCase):
    @patch(_RUN)
    def test_details_is_namespace_and_sub_component_is_resource_count(self, mock_run: Mock) -> None:
        manifest = "\n---\n".join(
            [
                "apiVersion: v1\nkind: Service\nmetadata:\n  name: traefik",
                "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: traefik",
                "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: cfg",
            ]
        )
        mock_run.return_value = json.dumps(
            {"info": {"status": "deployed"}, "version": 1, "namespace": "jupyter-k8s-router", "manifest": manifest}
        )
        runner = _make_runner()

        result = runner.execute_instruction("helm.status", _build_args())

        # Details carries the target namespace (no longer the revision).
        self.assertEqual(result["Details"].value, "jupyter-k8s-router")
        # SubComponent renders as "resources: <count>".
        sub = json.loads(result["SubComponent"].value)
        self.assertEqual(sub["name"], "resources")
        self.assertEqual(sub["status"], "3")

    @patch(_RUN)
    def test_ignores_empty_and_comment_manifest_docs(self, mock_run: Mock) -> None:
        # helm status leaves blank / comment-only docs between objects; they must not count.
        manifest = "\n---\n".join(
            [
                "# Source: chart/templates/svc.yaml\napiVersion: v1\nkind: Service\nmetadata:\n  name: a",
                "",
                "# just a comment, no object",
            ]
        )
        mock_run.return_value = json.dumps(
            {"info": {"status": "deployed"}, "version": 1, "namespace": "ns", "manifest": manifest}
        )
        runner = _make_runner()

        result = runner.execute_instruction("helm.status", _build_args())

        sub = json.loads(result["SubComponent"].value)
        self.assertEqual(sub["status"], "1")

    @patch(_RUN)
    def test_zero_resources_when_no_manifest(self, mock_run: Mock) -> None:
        mock_run.return_value = json.dumps({"info": {"status": "deployed"}, "version": 1, "namespace": "ns"})
        runner = _make_runner()

        result = runner.execute_instruction("helm.status", _build_args())

        sub = json.loads(result["SubComponent"].value)
        self.assertEqual(sub["status"], "0")

    @patch(_RUN)
    def test_details_falls_back_to_scope_when_namespace_absent(self, mock_run: Mock) -> None:
        # If helm status omits `namespace`, Details uses the scope (target namespace) passed in.
        mock_run.return_value = json.dumps({"info": {"status": "deployed"}, "version": 1, "manifest": ""})
        runner = _make_runner()

        result = runner.execute_instruction("helm.status", _build_args(scope="my-namespace"))

        self.assertEqual(result["Details"].value, "my-namespace")


class TestHelmApiRunnerShow(unittest.TestCase):
    @patch(_RUN)
    def test_returns_resource_json(self, mock_run: Mock) -> None:
        info = {"info": {"status": "deployed"}, "version": 2}
        mock_run.return_value = json.dumps(info)
        runner = _make_runner()

        result = runner.execute_instruction("helm.show", _build_args(name="jupyter-k8s"))

        self.assertEqual(result["Name"].value, "jupyter-k8s")
        resource = json.loads(result["Resource"].value)
        # Original fields preserved; resources breakdown derived from the (absent) manifest.
        self.assertEqual(resource["info"], {"status": "deployed"})
        self.assertEqual(resource["version"], 2)
        self.assertEqual(resource["resources"], {})

    @patch(_RUN)
    def test_redacts_manifest_but_keeps_resource_breakdown(self, mock_run: Mock) -> None:
        # The rendered manifest is a huge YAML blob; show replaces it with a placeholder
        # but surfaces a per-kind count.
        manifest = "\n---\n".join(
            [
                "apiVersion: v1\nkind: Service\nmetadata:\n  name: traefik",
                "apiVersion: v1\nkind: Service\nmetadata:\n  name: web",
                "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: traefik",
            ]
        )
        info = {
            "info": {"status": "deployed"},
            "version": 2,
            "namespace": "jupyter-k8s-router",
            "manifest": manifest,
        }
        mock_run.return_value = json.dumps(info)
        runner = _make_runner()

        result = runner.execute_instruction("helm.show", _build_args(name="jupyter-k8s"))

        resource = json.loads(result["Resource"].value)
        self.assertEqual(resource["manifest"], "<redacted>")
        self.assertEqual(resource["resources"], {"Service": 2, "Deployment": 1})
        self.assertEqual(resource["namespace"], "jupyter-k8s-router")
        self.assertEqual(resource["info"], {"status": "deployed"})

    @patch(_RUN)
    def test_redacts_secret_like_config_keys(self, mock_run: Mock) -> None:
        info = {
            "info": {"status": "deployed"},
            "version": 1,
            "manifest": "",
            "config": {
                "domain": "example.com",
                "github": {"clientId": "Ov23li", "clientSecret": "supersecret"},
                "oauth2Proxy": {"cookieSecret": "cookie-val"},
                "dex": {"oauth2ProxyClientSecret": "dex-val"},
                "webApp": {"clusterAccess": {"caCertBase64": "not-a-secret", "apiKey": "k-val"}},
            },
        }
        mock_run.return_value = json.dumps(info)
        runner = _make_runner()

        result = runner.execute_instruction("helm.show", _build_args(name="jupyter-k8s"))

        cfg = json.loads(result["Resource"].value)["config"]
        # secret-like keys redacted (nested, various suffixes)
        self.assertEqual(cfg["github"]["clientSecret"], "****")
        self.assertEqual(cfg["oauth2Proxy"]["cookieSecret"], "****")
        self.assertEqual(cfg["dex"]["oauth2ProxyClientSecret"], "****")
        self.assertEqual(cfg["webApp"]["clusterAccess"]["apiKey"], "****")
        # non-secret keys preserved
        self.assertEqual(cfg["domain"], "example.com")
        self.assertEqual(cfg["github"]["clientId"], "Ov23li")
        self.assertEqual(cfg["webApp"]["clusterAccess"]["caCertBase64"], "not-a-secret")


class TestHelmApiRunnerReconcile(unittest.TestCase):
    @patch(_RUN)
    def test_pipes_manifest_to_kubectl_apply(self, mock_run: Mock) -> None:
        manifest = "apiVersion: v1\nkind: Service\n"
        mock_run.side_effect = [manifest, "service/foo configured"]
        runner = _make_runner()

        result = runner.execute_instruction("helm.reconcile", _build_args())

        self.assertEqual(result["Output"].value, "service/foo configured")
        # first call fetches the manifest via helm
        helm_cmd = mock_run.call_args_list[0].args[0]
        self.assertEqual(helm_cmd[:1], ["helm"])
        self.assertIn("manifest", helm_cmd)
        # second call applies it via kubectl with the manifest on stdin
        apply_call = mock_run.call_args_list[1]
        self.assertEqual(apply_call.args[0][:1], ["kubectl"])
        self.assertIn("apply", apply_call.args[0])
        self.assertEqual(apply_call.kwargs["stdin_input"], manifest)
        # apply must NOT force a namespace: the manifest can span several namespaces and
        # each object carries its own; forcing one makes kubectl reject the others.
        self.assertNotIn("--namespace", apply_call.args[0])
        self.assertNotIn("-n", apply_call.args[0])

    @patch(_RUN)
    def test_empty_manifest_raises(self, mock_run: Mock) -> None:
        mock_run.return_value = "   \n"
        runner = _make_runner()

        with self.assertRaises(InstructionError):
            runner.execute_instruction("helm.reconcile", _build_args())


class TestHelmApiRunnerKubeconfig(unittest.TestCase):
    @patch(_RUN)
    def test_passes_kubeconfig_flag_when_path_set(self, mock_run: Mock) -> None:
        mock_run.return_value = json.dumps({"info": {"status": "deployed"}, "version": 1})
        runner = HelmApiRunner(display_manager=Mock(), kubeconfig_path="/tmp/kubeconfig")

        runner.execute_instruction("helm.status", _build_args())

        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd[:3], ["helm", "--kubeconfig", "/tmp/kubeconfig"])

    @patch(_RUN)
    def test_uses_ambient_config_when_no_path(self, mock_run: Mock) -> None:
        # Mirrors the k8s runner's kubectl subprocesses: no path -> rely on ambient kubeconfig.
        mock_run.return_value = json.dumps({"info": {"status": "deployed"}, "version": 1})
        runner = HelmApiRunner(display_manager=Mock())

        runner.execute_instruction("helm.status", _build_args())

        cmd = mock_run.call_args.args[0]
        self.assertNotIn("--kubeconfig", cmd)
        self.assertEqual(cmd[0], "helm")


_ARN = "arn:aws:eks:us-west-2:1:cluster/jupyter-deploy-eks-abcd1234"


class TestHelmApiRunnerContextVerification(unittest.TestCase):
    @patch(_RUN)
    def test_verifies_context_before_running_when_declared(self, mock_run: Mock) -> None:
        # First call is the context check (kubectl config current-context); it matches,
        # then the helm status call returns the release info.
        mock_run.side_effect = [_ARN, json.dumps({"info": {"status": "deployed"}, "version": 1})]
        runner = _make_runner()

        runner.execute_instruction("helm.status", _build_args(expected_cluster_config=_ARN))

        first_cmd = mock_run.call_args_list[0].args[0]
        self.assertEqual(first_cmd[:3], ["kubectl", "config", "current-context"])

    @patch(_RUN)
    def test_aborts_on_wrong_cluster(self, mock_run: Mock) -> None:
        mock_run.return_value = "arn:aws:eks:us-west-2:1:cluster/some-other-cluster"
        runner = _make_runner()

        with self.assertRaises(InvalidKubernetesClusterTargetError):
            runner.execute_instruction("helm.reconcile", _build_args(expected_cluster_config=_ARN))
        # only the context check ran; no helm/kubectl mutation was attempted
        self.assertEqual(mock_run.call_count, 1)

    @patch(_RUN)
    def test_skips_verification_when_not_declared(self, mock_run: Mock) -> None:
        # No expected_cluster_config arg -> no context check, straight to helm.
        mock_run.return_value = json.dumps({"info": {"status": "deployed"}, "version": 1})
        runner = _make_runner()

        runner.execute_instruction("helm.status", _build_args())

        first_cmd = mock_run.call_args_list[0].args[0]
        self.assertEqual(first_cmd[0], "helm")


class TestHelmApiRunnerDispatch(unittest.TestCase):
    def test_unknown_instruction_raises(self) -> None:
        runner = _make_runner()

        with self.assertRaises(InstructionNotFoundError):
            runner.execute_instruction("helm.rollback", _build_args())
