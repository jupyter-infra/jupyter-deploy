"""E2E tests for component commands on the EKS OIDC template."""

import json
import time
from datetime import UTC, datetime

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
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "health", "--json"])
    data = json.loads(result.stdout)
    for comp in data["components"]:
        if comp["name"] == name and comp.get("sub_component"):
            sub = json.loads(comp["sub_component"])
            if sub.get("last_updated"):
                dt = datetime.fromisoformat(sub["last_updated"])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
    return None


# ── component health ────────────────────────────────────────────────────────


def test_component_health(e2e_deployment: EndToEndDeployment) -> None:
    """Verify health dashboard shows all components with populated fields."""
    e2e_deployment.ensure_deployed()

    components = _get_manifest_components(e2e_deployment)
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "health"])
    output = result.stdout

    for name in components:
        assert name in output, f"Expected component '{name}' in health output"

    types = {comp.type for comp in components.values()}
    for comp_type in types:
        assert comp_type in output, f"Expected type '{comp_type}' in health output"


def test_component_health_json(e2e_deployment: EndToEndDeployment) -> None:
    """Verify health --json returns valid JSON with all components and expected keys."""
    e2e_deployment.ensure_deployed()

    manifest_components = _get_manifest_components(e2e_deployment)
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "health", "--json"])
    data = json.loads(result.stdout)

    assert "components" in data, f"Expected 'components' key, got: {list(data.keys())}"
    components = data["components"]
    assert len(components) == len(manifest_components), (
        f"Expected {len(manifest_components)} components, got {len(components)}"
    )

    names = [c["name"] for c in components]
    for name in manifest_components:
        assert name in names, f"Expected component '{name}' in JSON output"

    expected_types = {comp.type for comp in manifest_components.values()}
    for comp in components:
        assert comp["status"], f"Component '{comp['name']}' has empty status"
        assert comp["type"] in expected_types, f"Component '{comp['name']}' has unexpected type: {comp['type']}"
        assert comp["status_category"] in ("healthy", "in-progress", "degraded"), (
            f"Component '{comp['name']}' has unexpected status_category: {comp['status_category']}"
        )
        assert comp["details"], f"Component '{comp['name']}' has empty details"


# ── component list ──────────────────────────────────────────────────────────


def test_component_list(e2e_deployment: EndToEndDeployment) -> None:
    """Verify list shows table with all components."""
    e2e_deployment.ensure_deployed()

    manifest_components = _get_manifest_components(e2e_deployment)
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "list"])
    output = result.stdout

    for name in manifest_components:
        assert name in output, f"Expected component '{name}' in list output"

    for comp_type in {comp.type for comp in manifest_components.values()}:
        assert comp_type in output, f"Expected type '{comp_type}' in list output"


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
        assert by_name[name]["type"] == comp_def.type, (
            f"Type mismatch for '{name}': expected '{comp_def.type}', got '{by_name[name]['type']}'"
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


def test_component_status_happy_case(e2e_deployment: EndToEndDeployment) -> None:
    """Verify status returns a non-empty result for each component."""
    e2e_deployment.ensure_deployed()

    for name in _get_all_names(e2e_deployment):
        result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "status", "--name", name])
        assert f"{name} status:" in result.stdout, f"Expected '{name} status:' in output:\n{result.stdout}"


def test_component_status_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify status for a non-existent component fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "status", "--name", "i-do-not-exist"])


# ── component show ──────────────────────────────────────────────────────────


def test_component_show_deployment(e2e_deployment: EndToEndDeployment) -> None:
    """Verify show returns output for a Deployment component."""
    e2e_deployment.ensure_deployed()

    name = _get_deployment_names(e2e_deployment)[0]
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "show", "--name", name])
    assert result.stdout.strip(), "Expected non-empty output for component show"


def test_component_show_deployment_json(e2e_deployment: EndToEndDeployment) -> None:
    """Verify show --json returns valid JSON with expected fields for a Deployment."""
    e2e_deployment.ensure_deployed()

    name = _get_deployment_names(e2e_deployment)[0]
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "show", "--name", name, "--json"])
    data = json.loads(result.stdout)
    assert "name" in data, f"Expected 'name' in JSON response, got: {list(data.keys())}"
    assert "resource" in data, f"Expected 'resource' in JSON response, got: {list(data.keys())}"
    assert data["name"] == name


def test_component_show_job(e2e_deployment: EndToEndDeployment) -> None:
    """Verify show returns output for a CronJob component."""
    e2e_deployment.ensure_deployed()

    name = _get_cronjob_names(e2e_deployment)[0]
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "show", "--name", name, "--json"])
    data = json.loads(result.stdout)
    assert "name" in data, f"Expected 'name' in JSON response, got: {list(data.keys())}"
    assert "resource" in data, f"Expected 'resource' in JSON response, got: {list(data.keys())}"
    assert data["name"] == name


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


def test_component_show_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify show for a non-existent component fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "show", "--name", "i-do-not-exist"])


# ── component logs ──────────────────────────────────────────────────────────


@pytest.mark.usefixtures("cluster_login")
def test_component_logs_no_args(e2e_deployment: EndToEndDeployment) -> None:
    """Verify logs returns output for a Deployment component with no extra args."""
    e2e_deployment.ensure_deployed()

    name = _get_deployment_names(e2e_deployment)[0]
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "component", "logs", "--name", name])
    assert result.stdout.strip(), f"Expected non-empty log output for {name}"


@pytest.mark.usefixtures("cluster_login")
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


@pytest.mark.usefixtures("cluster_login")
def test_component_logs_bad_flag(e2e_deployment: EndToEndDeployment) -> None:
    """Verify logs with an invalid kubectl flag fails with a clean error."""
    e2e_deployment.ensure_deployed()

    name = _get_deployment_names(e2e_deployment)[0]
    with pytest.raises(JDCliError) as exc_info:
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "logs", "--name", name, "--", "--head=20"])
    assert "unknown flag" in str(exc_info.value).lower(), (
        f"Expected 'unknown flag' in error message, got: {exc_info.value}"
    )


@pytest.mark.usefixtures("cluster_login")
def test_component_logs_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify logs for a non-existent component fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "logs", "--name", "i-do-not-exist"])


# ── component restart ───────────────────────────────────────────────────────


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


def test_component_restart_wrong_type(e2e_deployment: EndToEndDeployment) -> None:
    """Verify restart fails for a CronJob component (wrong type)."""
    e2e_deployment.ensure_deployed()

    name = _get_cronjob_names(e2e_deployment)[0]
    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "restart", "--name", name])


def test_component_restart_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify restart for a non-existent component fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "restart", "--name", "i-do-not-exist"])


# ── component trigger ───────────────────────────────────────────────────────


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


def test_component_trigger_wrong_type(e2e_deployment: EndToEndDeployment) -> None:
    """Verify trigger fails for a Deployment component (wrong type)."""
    e2e_deployment.ensure_deployed()

    name = _get_deployment_names(e2e_deployment)[0]
    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "trigger", "--name", name])


def test_component_trigger_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify trigger for a non-existent component fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError):
        e2e_deployment.cli.run_command(["jupyter-deploy", "component", "trigger", "--name", "i-do-not-exist"])
