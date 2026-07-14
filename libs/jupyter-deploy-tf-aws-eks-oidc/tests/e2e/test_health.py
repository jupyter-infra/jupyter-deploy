"""E2E tests for the jd health command on the EKS OIDC template."""

import json
import re

from pytest_jupyter_deploy.deployment import EndToEndDeployment

# A CR sub-component renders as a non-empty "label: value" pair (e.g. "access-resources: 2").
_LABELED_VALUE_RE = re.compile(r"^\S.*: \S.*$")

EXPECTED_CRONJOBS = [
    "jwt-rotator",
]


def test_health_all_layers(e2e_deployment: EndToEndDeployment) -> None:
    """Verify jd health runs all layers and reports status for each."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "health"])
    output = result.stdout

    for layer in ["cluster", "load-balancer", "components", "images"]:
        assert layer in output, f"Expected layer '{layer}' in health output"
    assert "Connection" in output, "Expected 'Connection' in health output"


def test_health_json(e2e_deployment: EndToEndDeployment) -> None:
    """Verify --json returns valid JSON with expected fields."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "health", "--json"])
    data = json.loads(result.stdout)

    assert "layers" in data, f"Expected 'layers' key, got: {list(data.keys())}"
    assert "connection" in data, f"Expected 'connection' key, got: {list(data.keys())}"

    layers = data["layers"]
    assert len(layers) >= 3, f"Expected at least 3 layer rows, got {len(layers)}"

    for entry in layers:
        assert "layer" in entry
        assert "name" in entry
        assert "status" in entry
        assert "status_category" in entry
        assert "detail" in entry
        assert "sub_component" in entry
        assert "skipped" in entry
        assert entry["status_category"] in ("healthy", "in-progress", "degraded")

    conn = data["connection"]
    assert "status_category" in conn
    assert "detail" in conn
    assert "skipped" in conn
    assert conn["status_category"] in ("healthy", "degraded")


def test_health_cluster_layer(e2e_deployment: EndToEndDeployment) -> None:
    """Verify --cluster reports healthy with version."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "health", "--cluster", "--json"])
    data = json.loads(result.stdout)

    layers = data["layers"]
    assert len(layers) == 1
    assert layers[0]["layer"] == "cluster"
    assert layers[0]["status_category"] == "healthy"
    assert layers[0]["name"] != ""
    assert layers[0]["status"] == "Active"
    assert layers[0]["detail"].startswith("v")
    assert layers[0]["skipped"] is False


def test_health_components_layer(e2e_deployment: EndToEndDeployment) -> None:
    """Verify --components returns one row per manifest component."""
    e2e_deployment.ensure_deployed()

    manifest = e2e_deployment.get_manifest()
    manifest_components = manifest.get_components()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "health", "--components", "--json"])
    data = json.loads(result.stdout)

    layers = data["layers"]
    assert len(layers) == len(manifest_components), f"Expected {len(manifest_components)} components, got {len(layers)}"

    names = {entry["name"] for entry in layers}
    for name in manifest_components:
        assert name in names, f"Expected component '{name}' in health output"

    # Components whose health is existence-based, keyed by manifest type.
    crd_names = {n for n, c in manifest_components.items() if c.type == "CustomResourceDefinition"}
    cr_names = {n for n, c in manifest_components.items() if c.type == "CustomResourceWithoutStatus"}
    helm_names = {n for n, c in manifest_components.items() if c.type == "HelmRelease"}
    daemonset_names = {n for n, c in manifest_components.items() if c.type == "DaemonSet"}
    # The eks-oidc template declares the 3 Workspace CRDs + the access-strategy and template CRs.
    assert len(crd_names) >= 3, f"Expected >= 3 CustomResourceDefinition components, got {sorted(crd_names)}"
    assert len(cr_names) >= 2, f"Expected >= 2 CustomResourceWithoutStatus components, got {sorted(cr_names)}"
    # The 5 platform charts are surfaced as HelmRelease components.
    assert len(helm_names) == 5, f"Expected 5 HelmRelease components, got {sorted(helm_names)}"
    # Core add-on DaemonSets (aws-node, kube-proxy) are surfaced as DaemonSet components (#298).
    assert {"aws-node", "kube-proxy"} <= daemonset_names, (
        f"Expected aws-node + kube-proxy DaemonSet components, got {sorted(daemonset_names)}"
    )

    for entry in layers:
        assert entry["layer"] == "components"
        name = entry["name"]
        if name in EXPECTED_CRONJOBS:
            assert entry["status_category"] in ("healthy", "in-progress"), (
                f"CronJob '{name}' unexpected status_category: {entry['status_category']}"
            )
        else:
            assert entry["status_category"] == "healthy", (
                f"Component '{name}' not healthy: status_category={entry['status_category']}"
            )
        assert entry["status"] != ""

        if name in crd_names:
            # CRD rows surface the served API version (e.g. v1alpha1) in details.
            assert entry["status"] == "Present", f"CRD '{name}' status: {entry['status']}"
            assert entry["detail"] == "v1alpha1", f"CRD '{name}' detail: {entry['detail']}"

        if name in cr_names:
            # Access-strategy / template rows surface their namespace in details and a labeled
            # value (access-resources count / access-strategy ref) in the sub-component cell.
            assert entry["status"] == "Present", f"CR '{name}' status: {entry['status']}"
            assert entry["detail"] != "", f"CR '{name}' should surface its namespace in detail"
            assert _LABELED_VALUE_RE.match(entry["sub_component"]), (
                f"CR '{name}' sub-component should be a 'label: value' pair, got: {entry['sub_component']!r}"
            )

        if name in helm_names:
            # HelmRelease rows report the release status, the target namespace in details,
            # and a "resources: <count>" sub-component with a positive object count. In JSON
            # output sub_component is the raw payload; the table renders it as "resources: N".
            assert entry["status"] == "deployed", f"HelmRelease '{name}' status: {entry['status']}"
            assert entry["detail"] != "", f"HelmRelease '{name}' should surface its namespace in detail"
            sub = json.loads(entry["sub_component"])
            assert sub["name"] == "resources", f"HelmRelease '{name}' sub-component label: {sub['name']!r}"
            assert int(sub["status"]) > 0, f"HelmRelease '{name}' should track at least one resource: {sub!r}"


def test_health_load_balancer_layer(e2e_deployment: EndToEndDeployment) -> None:
    """Verify --load-balancer reports active state."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "health", "--load-balancer", "--json"])
    data = json.loads(result.stdout)

    layers = data["layers"]
    assert len(layers) == 1
    assert layers[0]["layer"] == "load-balancer"
    assert layers[0]["status_category"] == "healthy"
    assert layers[0]["name"] != ""
    assert layers[0]["status"] == "Active"


def test_health_images_layer(e2e_deployment: EndToEndDeployment) -> None:
    """Verify --images reports one row per image, available with its latest tag."""
    e2e_deployment.ensure_deployed()

    manifest = e2e_deployment.get_manifest()
    manifest_images = manifest.get_images()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "health", "--images", "--json"])
    data = json.loads(result.stdout)

    layers = data["layers"]
    assert len(layers) == len(manifest_images), f"Expected {len(manifest_images)} images, got {len(layers)}"

    names = {entry["name"] for entry in layers}
    for name in manifest_images:
        assert name in names, f"Expected image '{name}' in health output"

    for entry in layers:
        assert entry["layer"] == "images"
        # Status reflects ECR presence; a deployed image must be available.
        assert entry["status"] == "Available"
        assert entry["status_category"] == "healthy"
        # Detail is the latest non-'latest' tag.
        assert entry["detail"] != "latest"


def test_health_connection_flag(e2e_deployment: EndToEndDeployment) -> None:
    """Verify --connection confirms URL responds with expected status."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "health", "--connection", "--json"])
    data = json.loads(result.stdout)

    assert "connection" in data, f"Expected 'connection' key, got: {list(data.keys())}"
    assert data["layers"] == [], "Expected empty 'layers' with --connection only"
    conn = data["connection"]
    assert conn["status_category"] == "healthy"
    assert "status=" in conn["detail"]
