"""E2E tests for component commands on the EKS OIDC template."""

import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pytest_jupyter_deploy.cli import JDCliError
from pytest_jupyter_deploy.deployment import EndToEndDeployment


def _get_manifest_components(e2e_deployment: EndToEndDeployment) -> dict:
    """Read component definitions from the project manifest."""
    manifest = e2e_deployment.get_manifest()
    return manifest.get_components()


def _get_all_names(e2e_deployment: EndToEndDeployment) -> list[str]:
    return list(_get_manifest_components(e2e_deployment).keys())


def _get_deployment_names(e2e_deployment: EndToEndDeployment) -> list[str]:
    return [name for name, comp in _get_manifest_components(e2e_deployment).items() if comp.type == "Deployment"]


def _get_cronjob_names(e2e_deployment: EndToEndDeployment) -> list[str]:
    return [name for name, comp in _get_manifest_components(e2e_deployment).items() if comp.type == "CronJob"]


def _get_custom_resource_names(e2e_deployment: EndToEndDeployment) -> list[str]:
    return [
        name
        for name, comp in _get_manifest_components(e2e_deployment).items()
        if comp.type == "CustomResourceWithoutStatus"
    ]


def _get_crd_names(e2e_deployment: EndToEndDeployment) -> list[str]:
    return [
        name
        for name, comp in _get_manifest_components(e2e_deployment).items()
        if comp.type == "CustomResourceDefinition"
    ]


def _get_helmrelease_names(e2e_deployment: EndToEndDeployment) -> list[str]:
    return [name for name, comp in _get_manifest_components(e2e_deployment).items() if comp.type == "HelmRelease"]


def _poll_component_status(
    e2e_deployment: EndToEndDeployment, name: str, target_status: str, timeout_s: int = 120, interval_s: int = 5
) -> None:
    """Poll component status until it matches target_status or timeout is reached."""
    deadline = time.time() + timeout_s
    last_status = ""
    while time.time() < deadline:
        result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "status", "--name", name])
        last_status = result.stdout.strip().split(":")[-1].strip()
        if last_status == target_status:
            return
        time.sleep(interval_s)
    raise TimeoutError(
        f"Component '{name}' did not reach status '{target_status}' within {timeout_s}s (last: {last_status})"
    )


def _get_component_last_updated(e2e_deployment: EndToEndDeployment, name: str) -> datetime | None:
    """Get the last_updated timestamp of the sub_component from health JSON."""
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "health", "--components", "--json"])
    data = json.loads(result.stdout)
    for entry in data["layers"]:
        if entry["name"] == name and entry.get("sub_component"):
            sub = json.loads(entry["sub_component"])
            if sub.get("last_updated"):
                dt = datetime.fromisoformat(sub["last_updated"])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
    return None


# ── component list ──────────────────────────────────────────────────────────


def test_component_list(e2e_deployment: EndToEndDeployment) -> None:
    """Verify list shows table with all components.

    The table renders at a fixed terminal width, so long names/types may be truncated;
    exact-name coverage is in the --text and --json variants. Here we assert that a
    truncation-tolerant prefix of each name and display type appears in the output.
    """
    e2e_deployment.ensure_deployed()

    manifest_components = _get_manifest_components(e2e_deployment)
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "list"])
    output = result.stdout

    for name in manifest_components:
        assert name[:20] in output, f"Expected component '{name}' in list output"

    # The Type column shows the display type (type-display when set, else type).
    for comp in manifest_components.values():
        display_type = comp.type_display or comp.type
        assert display_type[:20] in output, f"Expected type '{display_type}' in list output"


def test_component_list_json(e2e_deployment: EndToEndDeployment) -> None:
    """Verify list --json returns valid JSON with all components and descriptions match manifest."""
    e2e_deployment.ensure_deployed()

    manifest_components = _get_manifest_components(e2e_deployment)
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "list", "--json"])
    components = json.loads(result.stdout)

    assert isinstance(components, list), f"Expected list, got {type(components)}"
    assert len(components) == len(manifest_components), (
        f"Expected {len(manifest_components)} components, got {len(components)}"
    )

    by_name = {c["name"]: c for c in components}
    for name, comp_def in manifest_components.items():
        assert name in by_name, f"Expected component '{name}' in JSON output"
        # list returns the display type (type-display when set, else the internal type).
        expected_type = comp_def.type_display or comp_def.type
        assert by_name[name]["type"] == expected_type, (
            f"Type mismatch for '{name}': expected '{expected_type}', got '{by_name[name]['type']}'"
        )
        actual_desc = by_name[name]["description"]
        assert actual_desc == comp_def.description, (
            f"Description mismatch for '{name}': expected '{comp_def.description}', got '{actual_desc}'"
        )


def test_component_list_text(e2e_deployment: EndToEndDeployment) -> None:
    """Verify list --text returns comma-separated component names matching manifest."""
    e2e_deployment.ensure_deployed()

    manifest_components = _get_manifest_components(e2e_deployment)
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "list", "--text"])
    names = result.stdout.strip().split(",")

    assert len(names) == len(manifest_components), (
        f"Expected {len(manifest_components)} names, got {len(names)}: {names}"
    )
    for name in manifest_components:
        assert name in names, f"Expected component '{name}' in text output"


# ── component status ────────────────────────────────────────────────────────


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_status_happy_case(e2e_deployment: EndToEndDeployment) -> None:
    """Verify status returns a non-empty result for each component."""
    e2e_deployment.ensure_deployed()

    for name in _get_all_names(e2e_deployment):
        result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "status", "--name", name])
        assert f"{name} status:" in result.stdout, f"Expected '{name} status:' in output:\n{result.stdout}"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_custom_resource_component_status_present(e2e_deployment: EndToEndDeployment) -> None:
    """Verify CustomResourceWithoutStatus components report a present/default verdict via health."""
    e2e_deployment.ensure_deployed()

    cr_names = _get_custom_resource_names(e2e_deployment)
    assert cr_names, "Expected CustomResourceWithoutStatus components (oauth-access-strategy, jupyterlab-template)"

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "health", "--components", "--json"])
    data = json.loads(result.stdout)
    by_name = {entry["name"]: entry for entry in data["layers"]}

    for name in cr_names:
        assert name in by_name, f"Expected CR component '{name}' in health output"
        entry = by_name[name]
        # Existence-based health: a deployed CR is healthy and reports 'Present'.
        assert entry["status_category"] == "healthy", f"{name}: {entry}"
        assert entry["status"] == "Present", f"{name} unexpected status: {entry['status']}"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_cluster_custom_resource_crd_status_present(e2e_deployment: EndToEndDeployment) -> None:
    """Verify the Workspace CRDs report present via cluster-scoped existence checks."""
    e2e_deployment.ensure_deployed()

    crd_names = _get_crd_names(e2e_deployment)
    assert crd_names, "Expected CustomResourceDefinition components for the Workspace CRDs"

    for name in crd_names:
        result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "status", "--name", name])
        assert f"{name} status: Present" in result.stdout, f"Expected '{name}' Present:\n{result.stdout}"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_cluster_custom_resource_crd_show(e2e_deployment: EndToEndDeployment) -> None:
    """Verify show returns the CRD object for a cluster-scoped component."""
    e2e_deployment.ensure_deployed()

    crd_names = _get_crd_names(e2e_deployment)
    assert crd_names, "Expected CustomResourceDefinition components for the Workspace CRDs"

    name = crd_names[0]
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "show", "--name", name, "--json"])
    data = json.loads(result.stdout)
    assert "resource" in data, f"Expected 'resource' in JSON response, got: {list(data.keys())}"
    assert data["resource"]["kind"] == "CustomResourceDefinition"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_helmrelease_component_status_deployed(e2e_deployment: EndToEndDeployment) -> None:
    """Verify each HelmRelease component reports its deployed status."""
    e2e_deployment.ensure_deployed()

    helm_names = _get_helmrelease_names(e2e_deployment)
    assert helm_names, "Expected HelmRelease components for the platform charts"

    for name in helm_names:
        result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "status", "--name", name])
        # helm reports `deployed` for a healthy release; a superseded revision would also be acceptable.
        assert f"{name} status:" in result.stdout, f"Expected status line for '{name}':\n{result.stdout}"
        assert "deployed" in result.stdout, f"Expected '{name}' to be deployed:\n{result.stdout}"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_status_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify status for a non-existent component fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "status", "--name", "i-do-not-exist"])


# ── component show ──────────────────────────────────────────────────────────


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_show_deployment(e2e_deployment: EndToEndDeployment) -> None:
    """Verify show returns output for a Deployment component."""
    e2e_deployment.ensure_deployed()

    name = _get_deployment_names(e2e_deployment)[0]
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "show", "--name", name])
    assert result.stdout.strip(), "Expected non-empty output for component show"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_show_deployment_json(e2e_deployment: EndToEndDeployment) -> None:
    """Verify show --json returns valid JSON with expected fields for a Deployment."""
    e2e_deployment.ensure_deployed()

    name = _get_deployment_names(e2e_deployment)[0]
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "show", "--name", name, "--json"])
    data = json.loads(result.stdout)
    assert "name" in data, f"Expected 'name' in JSON response, got: {list(data.keys())}"
    assert "resource" in data, f"Expected 'resource' in JSON response, got: {list(data.keys())}"
    assert data["name"] == name


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_show_job(e2e_deployment: EndToEndDeployment) -> None:
    """Verify show returns output for a CronJob component."""
    e2e_deployment.ensure_deployed()

    name = _get_cronjob_names(e2e_deployment)[0]
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "show", "--name", name, "--json"])
    data = json.loads(result.stdout)
    assert "name" in data, f"Expected 'name' in JSON response, got: {list(data.keys())}"
    assert "resource" in data, f"Expected 'resource' in JSON response, got: {list(data.keys())}"
    assert data["name"] == name


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_show_custom_resource(e2e_deployment: EndToEndDeployment) -> None:
    """Verify show --json returns the resource for a CustomResourceWithoutStatus component."""
    e2e_deployment.ensure_deployed()

    cr_names = _get_custom_resource_names(e2e_deployment)
    assert cr_names, "Expected at least one CustomResourceWithoutStatus component"

    name = cr_names[0]
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "show", "--name", name, "--json"])
    data = json.loads(result.stdout)
    assert "name" in data, f"Expected 'name' in JSON response, got: {list(data.keys())}"
    assert "resource" in data, f"Expected 'resource' in JSON response, got: {list(data.keys())}"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_helmrelease_component_show(e2e_deployment: EndToEndDeployment) -> None:
    """Verify show --json returns the helm release info for a HelmRelease component.

    Targets the router release specifically because it carries the GitHub OAuth client
    secret in its chart config — the case that must be redacted.
    """
    e2e_deployment.ensure_deployed()

    name = "workspace-router-chart"
    assert name in _get_helmrelease_names(e2e_deployment), f"Expected a HelmRelease component named '{name}'"

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "show", "--name", name, "--json"])
    data = json.loads(result.stdout)
    # `name` is the helm release name (the component's resource-name), not the component name.
    assert data["name"] == "jupyter-k8s-aws-oidc", f"Unexpected release name for '{name}': {data['name']}"
    # The resource is the `helm status --output json` payload (with the manifest redacted).
    resource = json.loads(data["resource"]) if isinstance(data["resource"], str) else data["resource"]
    assert resource.get("info", {}).get("status") == "deployed", f"Unexpected release info for '{name}': {resource}"
    assert "version" in resource, f"Expected a revision 'version' in release info for '{name}'"

    # The rendered manifest is replaced with a placeholder, not the full YAML blob.
    assert resource.get("manifest") == "<redacted>", (
        f"Expected manifest to be redacted, got: {resource.get('manifest')}"
    )

    # `resources` is a per-kind breakdown of the managed objects.
    resources = resource.get("resources")
    assert isinstance(resources, dict), f"Expected 'resources' to be a dict, got: {resources!r}"
    assert resources, f"Expected a non-empty per-kind resource breakdown for '{name}'"

    # The GitHub OAuth client secret must be redacted, never exposed in plaintext.
    client_secret = resource.get("config", {}).get("github", {}).get("clientSecret")
    assert client_secret == "****", f"Expected github.clientSecret to be redacted, got: {client_secret!r}"


def test_component_show_description(e2e_deployment: EndToEndDeployment) -> None:
    """Verify show --description returns the manifest description."""
    e2e_deployment.ensure_deployed()

    manifest_components = _get_manifest_components(e2e_deployment)
    first_name = next(iter(manifest_components))
    expected_desc = manifest_components[first_name].description

    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "component", "show", "--name", first_name, "--description"]
    )
    assert expected_desc in result.stdout, f"Expected description '{expected_desc}' in output:\n{result.stdout}"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_show_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify show for a non-existent component fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "show", "--name", "i-do-not-exist"])


# ── component logs ──────────────────────────────────────────────────────────


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_logs_no_args(e2e_deployment: EndToEndDeployment) -> None:
    """Verify logs returns output for a Deployment component with no extra args."""
    e2e_deployment.ensure_deployed()

    name = _get_deployment_names(e2e_deployment)[0]
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "logs", "--name", name])
    assert result.stdout.strip(), f"Expected non-empty log output for {name}"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_logs_valid_flags(e2e_deployment: EndToEndDeployment) -> None:
    """Verify logs with valid kubectl flags (--tail) works and produces less output."""
    e2e_deployment.ensure_deployed()

    name = _get_deployment_names(e2e_deployment)[0]
    full_result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "logs", "--name", name])
    tail_result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "component", "logs", "--name", name, "--", "--tail=5"]
    )
    assert tail_result.stdout.strip(), "Expected non-empty output with --tail=5"
    assert len(tail_result.stdout) <= len(full_result.stdout), "Expected --tail=5 to produce less or equal output"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_logs_bad_flag(e2e_deployment: EndToEndDeployment) -> None:
    """Verify logs with an invalid kubectl flag fails with a clean error."""
    e2e_deployment.ensure_deployed()

    name = _get_deployment_names(e2e_deployment)[0]
    with pytest.raises(JDCliError) as exc_info:
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "logs", "--name", name, "--", "--head=20"])
    assert "unknown flag" in str(exc_info.value).lower(), (
        f"Expected 'unknown flag' in error message, got: {exc_info.value}"
    )


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_logs_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify logs for a non-existent component fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "logs", "--name", "i-do-not-exist"])


# ── component restart ───────────────────────────────────────────────────────


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_restart(e2e_deployment: EndToEndDeployment) -> None:
    """Verify restart completes: polls until Ready, verifies pod age < 5 minutes."""
    e2e_deployment.ensure_deployed()

    name = _get_deployment_names(e2e_deployment)[-1]
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "restart", "--name", name])
    assert "Restarted" in result.stdout, f"Expected 'Restarted' in output:\n{result.stdout}"

    _poll_component_status(e2e_deployment, name, "Ready", timeout_s=120)

    last_updated = _get_component_last_updated(e2e_deployment, name)
    assert last_updated is not None, f"Could not determine last_updated for '{name}'"
    age_minutes = (datetime.now(UTC) - last_updated).total_seconds() / 60.0
    assert age_minutes < 5, f"Expected pod last_updated < 5 minutes after restart, got {age_minutes:.1f}m"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_restart_wrong_type(e2e_deployment: EndToEndDeployment) -> None:
    """Verify restart fails for a CronJob component (wrong type)."""
    e2e_deployment.ensure_deployed()

    name = _get_cronjob_names(e2e_deployment)[0]
    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "restart", "--name", name])


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_restart_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify restart for a non-existent component fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "restart", "--name", "i-do-not-exist"])


# ── component trigger ───────────────────────────────────────────────────────


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_trigger(e2e_deployment: EndToEndDeployment) -> None:
    """Verify trigger creates a Job, polls until Idle, verifies last run < 2 minutes."""
    e2e_deployment.ensure_deployed()

    name = _get_cronjob_names(e2e_deployment)[0]
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "trigger", "--name", name])
    assert name in result.stdout, f"Expected '{name}' in output:\n{result.stdout}"
    assert "Created job" in result.stdout, f"Expected 'Created job' in output:\n{result.stdout}"

    _poll_component_status(e2e_deployment, name, "Idle", timeout_s=120)

    last_updated = _get_component_last_updated(e2e_deployment, name)
    assert last_updated is not None, f"Could not determine last_updated for '{name}'"
    age_minutes = (datetime.now(UTC) - last_updated).total_seconds() / 60.0
    assert age_minutes < 2, f"Expected last run last_updated < 2 minutes after trigger, got {age_minutes:.1f}m"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_trigger_wrong_type(e2e_deployment: EndToEndDeployment) -> None:
    """Verify trigger fails for a Deployment component (wrong type)."""
    e2e_deployment.ensure_deployed()

    name = _get_deployment_names(e2e_deployment)[0]
    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "trigger", "--name", name])


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_trigger_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify trigger for a non-existent component fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "trigger", "--name", "i-do-not-exist"])


# ── component reconcile ──────────────────────────────────────────────────────

# The workspace-defaults chart ships the `jupyterlab` WorkspaceTemplate carrying the
# `workspace.jupyter.org/default-template` label. Removing that label out-of-band and
# reconciling the release must restore it — a safe, revertible drift on a managed object.
_RECONCILE_RELEASE_COMPONENT = "workspace-defaults-chart"
_DEFAULT_TEMPLATE_KIND = "workspacetemplate"
_DEFAULT_TEMPLATE_NAME = "jupyterlab"
_DEFAULT_TEMPLATE_LABEL = "workspace.jupyter.org/default-template"
_PATCHES_DIR = Path(__file__).parent / "patches"


def _resolve_component_namespace(e2e_deployment: EndToEndDeployment, name: str) -> str:
    """Resolve a component's namespace from its manifest scope output."""
    comp = _get_manifest_components(e2e_deployment)[name]
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "show", "--output", comp.scope, "--text"])
    return result.stdout.strip()


def _kubectl_get_label(kind: str, name: str, namespace: str, label: str) -> str | None:
    """Return the value of a label on a resource, or None if the label is absent."""
    jsonpath = "{.metadata.labels." + label.replace(".", "\\.") + "}"
    result = subprocess.run(
        ["kubectl", "get", kind, name, "-n", namespace, "-o", f"jsonpath={jsonpath}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout if result.stdout != "" else None


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_reconcile_noop_on_no_drift(e2e_deployment: EndToEndDeployment) -> None:
    """Verify reconcile is idempotent: re-running with no drift changes nothing.

    The first apply over helm-created objects reports `configured` (it writes the
    last-applied-configuration annotation), so idempotency is asserted on a second
    back-to-back reconcile: with nothing drifted, every object must report `unchanged`
    (never `configured`/`created`) and the release stays healthy.
    """
    e2e_deployment.ensure_deployed()

    # First reconcile settles the last-applied-configuration annotations.
    first = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "component", "reconcile", "--name", _RECONCILE_RELEASE_COMPONENT]
    )
    assert "Reconciled" in first.stdout, f"Expected 'Reconciled' in output:\n{first.stdout}"

    # Second reconcile with no intervening drift must be a genuine no-op.
    second = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "component", "reconcile", "--name", _RECONCILE_RELEASE_COMPONENT]
    )
    assert "Reconciled" in second.stdout, f"Expected 'Reconciled' in output:\n{second.stdout}"
    assert "configured" not in second.stdout and "created" not in second.stdout, (
        f"Expected an idempotent no-op reconcile (all 'unchanged'), got:\n{second.stdout}"
    )

    status = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "component", "status", "--name", _RECONCILE_RELEASE_COMPONENT]
    )
    assert "deployed" in status.stdout, f"Release not healthy after no-op reconcile:\n{status.stdout}"


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_reconcile_add_back_missing_label(e2e_deployment: EndToEndDeployment) -> None:
    """Verify reconcile re-asserts a chart-managed field removed out-of-band.

    Removes the `default-template` label from the jupyterlab WorkspaceTemplate (a
    kubectl patch helm's template-diff would never notice), reconciles the release,
    and asserts the label is restored — the core drift-recovery scenario of issue #294.
    """
    e2e_deployment.ensure_deployed()

    namespace = _resolve_component_namespace(e2e_deployment, _RECONCILE_RELEASE_COMPONENT)

    original = _kubectl_get_label(_DEFAULT_TEMPLATE_KIND, _DEFAULT_TEMPLATE_NAME, namespace, _DEFAULT_TEMPLATE_LABEL)
    assert original is not None, (
        f"Expected {_DEFAULT_TEMPLATE_NAME} to carry the {_DEFAULT_TEMPLATE_LABEL} label before the test"
    )

    # Remove the label out-of-band via a merge patch (value: null drops the key).
    patch = (_PATCHES_DIR / "remove-default-template-label.json").read_text()
    subprocess.run(
        [
            "kubectl",
            "patch",
            _DEFAULT_TEMPLATE_KIND,
            _DEFAULT_TEMPLATE_NAME,
            "-n",
            namespace,
            "--type=merge",
            "-p",
            patch,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert (
        _kubectl_get_label(_DEFAULT_TEMPLATE_KIND, _DEFAULT_TEMPLATE_NAME, namespace, _DEFAULT_TEMPLATE_LABEL) is None
    ), "Label should be removed before reconcile"

    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "component", "reconcile", "--name", _RECONCILE_RELEASE_COMPONENT]
    )
    assert "Reconciled" in result.stdout, f"Expected 'Reconciled' in output:\n{result.stdout}"

    restored = _kubectl_get_label(_DEFAULT_TEMPLATE_KIND, _DEFAULT_TEMPLATE_NAME, namespace, _DEFAULT_TEMPLATE_LABEL)
    assert restored == original, (
        f"Expected reconcile to restore label {_DEFAULT_TEMPLATE_LABEL}={original}, got {restored!r}"
    )


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_reconcile_wrong_type(e2e_deployment: EndToEndDeployment) -> None:
    """Verify reconcile fails for a Deployment component (wrong type)."""
    e2e_deployment.ensure_deployed()

    name = _get_deployment_names(e2e_deployment)[0]
    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "reconcile", "--name", name])


@pytest.mark.usefixtures("kubernetes_cluster_login")
def test_component_reconcile_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify reconcile for a non-existent component fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "reconcile", "--name", "i-do-not-exist"])
