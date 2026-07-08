import json
import subprocess
from enum import Enum
from typing import Any

import yaml

from jupyter_deploy import cmd_utils
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.enum import StatusCategory
from jupyter_deploy.exceptions import InstructionError, InstructionNotFoundError, ResourceNotFoundError
from jupyter_deploy.provider.instruction_runner import InstructionRunner
from jupyter_deploy.provider.k8s.kubeconfig_verify import verify_kubeconfig_context
from jupyter_deploy.provider.resolved_argdefs import (
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
    retrieve_optional_arg,
)
from jupyter_deploy.provider.resolved_resultdefs import (
    ResolvedInstructionResult,
    StrResolvedInstructionResult,
)

# Helm release status strings (`.info.status`) mapped to jupyter-deploy health categories.
# See https://helm.sh/docs/helm/helm_status/.
_HEALTHY_STATUSES = frozenset({"deployed", "superseded"})
_IN_PROGRESS_STATUSES = frozenset({"pending-install", "pending-upgrade", "pending-rollback", "uninstalling"})

# The chart's `config` (user-supplied values) can contain plaintext credentials — e.g.
# github.clientSecret, oauth2Proxy.cookieSecret, dex.oauth2ProxyClientSecret. Redact any
# leaf whose key ends in these (case-insensitive) before showing the config.
_REDACTED = "****"
_SECRET_KEY_SUFFIXES = ("secret", "key", "password", "token")


class HelmInstruction(str, Enum):
    """Instructions supported by the Helm runner."""

    STATUS = "status"
    SHOW = "show"
    RECONCILE = "reconcile"


class HelmApiRunner(InstructionRunner):
    """Routes helm.<instruction> to the `helm` (and `kubectl`) CLIs.

    Helm is not a reconciler: `helm upgrade` only acts on the diff between the previous
    and new rendered manifests, so an object deleted out-of-band is never recreated.
    `reconcile` re-applies the release's stored manifest with `kubectl apply` to re-assert
    desired state — recreating drifted or deleted managed objects on demand.
    """

    def __init__(self, display_manager: DisplayManager, kubeconfig_path: str | None = None) -> None:
        super().__init__(display_manager)
        self._kubeconfig_path = kubeconfig_path

    def _run(
        self, base_cmd: str, args: list[str], expected_cluster_config: str = "", stdin_input: str | None = None
    ) -> str:
        """Run a `helm`/`kubectl` subprocess, return stdout.

        Follows the same auth pattern as the k8s runner's kubectl subprocesses: pass
        `--kubeconfig` when a path is configured, otherwise rely on the ambient kubeconfig
        (set up by `jd cluster login` / `aws eks update-kubeconfig`). When the command
        declares an `expected_cluster_config`, the active context is verified against it
        first to avoid acting on the wrong cluster.

        Raises:
            InvalidKubernetesClusterTargetError: If the active kubeconfig context targets the wrong cluster.
            ResourceNotFoundError: If helm reports the release does not exist.
            InstructionError: For any other non-zero exit.
        """
        verify_kubeconfig_context(expected_cluster_config or None, self._kubeconfig_path)

        cmds = [base_cmd]
        if self._kubeconfig_path:
            cmds += ["--kubeconfig", self._kubeconfig_path]
        cmds += args
        try:
            return cmd_utils.run_cmd_and_capture_output(cmds, stdin_input=stdin_input)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else ""
            stderr_lower = stderr.lower()
            if "release: not found" in stderr_lower or ("not found" in stderr_lower and "release" in stderr_lower):
                raise ResourceNotFoundError(
                    resource_kind="helm release",
                    resource_name=args[1] if len(args) > 1 else "",
                    original_message=stderr,
                ) from None
            raise InstructionError(stderr or f"command failed: {' '.join(cmds)}") from None

    def _get_release_info(self, name: str, namespace: str, expected_cluster_config: str) -> dict[str, Any]:
        raw = self._run(
            "helm",
            ["status", name, "--namespace", namespace, "--output", "json"],
            expected_cluster_config=expected_cluster_config,
        )
        try:
            info: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as e:
            raise InstructionError(f"Could not parse helm status for release '{name}': {e}") from None
        return info

    @staticmethod
    def _count_manifest_resources_by_kind(manifest: str) -> dict[str, int]:
        """Count the Kubernetes objects a release tracks, grouped by `kind`.

        Parses the YAML stream and tallies documents that declare a `kind`; this ignores
        the empty/comment-only documents that `helm status` leaves between objects, so it
        is more accurate than splitting on `---`. Returns e.g. {"Service": 6, "Deployment": 5}.
        """
        counts: dict[str, int] = {}
        try:
            for doc in yaml.safe_load_all(manifest):
                if isinstance(doc, dict) and doc.get("kind"):
                    kind = str(doc["kind"])
                    counts[kind] = counts.get(kind, 0) + 1
        except yaml.YAMLError:
            return {}
        return counts

    @classmethod
    def _count_manifest_resources(cls, manifest: str) -> int:
        """Total number of Kubernetes objects a release tracks (sum over kinds)."""
        return sum(cls._count_manifest_resources_by_kind(manifest).values())

    @classmethod
    def _redact_secrets(cls, value: Any) -> Any:
        """Recursively redact secret-like values in a config tree.

        A leaf is redacted when its key ends in a secret-like suffix (case-insensitive),
        e.g. `clientSecret`, `cookieSecret`, `oauth2ProxyClientSecret`. Dicts and lists are
        walked; other values are returned unchanged.
        """
        if isinstance(value, dict):
            redacted: dict[str, Any] = {}
            for k, v in value.items():
                key_lower = str(k).lower()
                if isinstance(v, str) and any(key_lower.endswith(s) for s in _SECRET_KEY_SUFFIXES):
                    redacted[k] = _REDACTED
                else:
                    redacted[k] = cls._redact_secrets(v)
            return redacted
        if isinstance(value, list):
            return [cls._redact_secrets(item) for item in value]
        return value

    @staticmethod
    def _expected_cluster_config(resolved_arguments: dict[str, ResolvedInstructionArgument]) -> str:
        # Optional per-command arg: when set, the active kubeconfig context must match it.
        arg = retrieve_optional_arg(resolved_arguments, "expected_cluster_config", StrResolvedInstructionArgument, "")
        return arg.value

    def _status(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)

        self.display_manager.info(f"Getting helm release status: {name_arg.value}")
        info = self._get_release_info(
            name_arg.value, scope_arg.value, self._expected_cluster_config(resolved_arguments)
        )

        status = str(info.get("info", {}).get("status", "unknown"))
        if status in _HEALTHY_STATUSES:
            status_category = StatusCategory.HEALTHY
        elif status in _IN_PROGRESS_STATUSES:
            status_category = StatusCategory.IN_PROGRESS
        else:
            status_category = StatusCategory.DEGRADED

        # Details surfaces the chart's target namespace; the sub-component reports how many
        # Kubernetes objects the release tracks, rendered as "resources: <count>".
        details = str(info.get("namespace", "") or scope_arg.value)
        resource_count = self._count_manifest_resources(str(info.get("manifest", "")))
        sub_component = json.dumps({"name": "resources", "status": str(resource_count)})

        return {
            "Status": StrResolvedInstructionResult(result_name="Status", value=status),
            "StatusCategory": StrResolvedInstructionResult(result_name="StatusCategory", value=status_category),
            "Details": StrResolvedInstructionResult(result_name="Details", value=details),
            "SubComponent": StrResolvedInstructionResult(result_name="SubComponent", value=sub_component),
        }

    def _show(self, resolved_arguments: dict[str, ResolvedInstructionArgument]) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)

        self.display_manager.info(f"Getting helm release details: {name_arg.value}")
        info = self._get_release_info(
            name_arg.value, scope_arg.value, self._expected_cluster_config(resolved_arguments)
        )

        # Replace the rendered `manifest` — a huge YAML blob that dominates the output — with
        # a placeholder (`helm get manifest` / `jd component reconcile` show it in full), and
        # surface a per-kind breakdown of the managed objects instead, e.g.
        # `resources: {"Service": 6, "Deployment": 5, ...}`.
        resource = dict(info)
        resource["resources"] = self._count_manifest_resources_by_kind(str(info.get("manifest", "")))
        resource["manifest"] = "<redacted>"
        # `config` holds user-supplied chart values, which can include plaintext secrets.
        if "config" in resource:
            resource["config"] = self._redact_secrets(resource["config"])

        return {
            "Name": StrResolvedInstructionResult(result_name="Name", value=name_arg.value),
            "Resource": StrResolvedInstructionResult(result_name="Resource", value=json.dumps(resource)),
        }

    def _reconcile(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        name_arg = require_arg(resolved_arguments, "name", StrResolvedInstructionArgument)
        scope_arg = require_arg(resolved_arguments, "scope", StrResolvedInstructionArgument)
        expected_cluster_config = self._expected_cluster_config(resolved_arguments)

        self.display_manager.info(f"Reconciling helm release: {name_arg.value}")
        manifest = self._run(
            "helm",
            ["get", "manifest", name_arg.value, "--namespace", scope_arg.value],
            expected_cluster_config=expected_cluster_config,
        )
        if not manifest.strip():
            raise InstructionError(f"helm returned an empty manifest for release '{name_arg.value}'.")

        # Re-apply the stored rendered manifest to re-assert desired state. Unlike
        # `helm upgrade` (template-diff), `kubectl apply` acts against the live cluster,
        # so objects deleted out-of-band are recreated.
        #
        # Do NOT pass `--namespace`: a release can ship objects into several namespaces
        # (e.g. workspace-defaults renders into the shared namespace AND per-workspace
        # namespaces), and each object in the stored manifest already carries its own
        # namespace. Forcing one namespace makes kubectl reject objects that declare a
        # different one.
        applied = self._run(
            "kubectl",
            ["apply", "-f", "-"],
            expected_cluster_config=expected_cluster_config,
            stdin_input=manifest,
        )

        return {
            "Output": StrResolvedInstructionResult(result_name="Output", value=applied.strip()),
        }

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        # Instruction names arrive fully qualified (e.g. "helm.reconcile"); strip the group prefix.
        sub_instruction = instruction_name.split(".", 1)[1] if "." in instruction_name else instruction_name
        try:
            instruction = HelmInstruction(sub_instruction)
        except ValueError:
            raise InstructionNotFoundError(f"Unknown helm instruction: '{instruction_name}'") from None

        if instruction == HelmInstruction.STATUS:
            return self._status(resolved_arguments)
        elif instruction == HelmInstruction.SHOW:
            return self._show(resolved_arguments)
        elif instruction == HelmInstruction.RECONCILE:
            return self._reconcile(resolved_arguments)

        raise InstructionNotFoundError(f"Unknown helm instruction: '{instruction_name}'")
