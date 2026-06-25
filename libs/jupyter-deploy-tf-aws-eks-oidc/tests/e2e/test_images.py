"""E2E tests for image commands on the EKS OIDC template."""

import json

import pytest
from pytest_jupyter_deploy.cli import JDCliError
from pytest_jupyter_deploy.deployment import EndToEndDeployment

pytestmark = pytest.mark.cli

# ── image list ─────────────────────────────────────────────────────────────


def test_image_list(e2e_deployment: EndToEndDeployment) -> None:
    """Verify list shows table with image names."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "image", "list"])
    assert "jupyterlab" in result.stdout


def test_image_list_json(e2e_deployment: EndToEndDeployment) -> None:
    """Verify list --json returns valid JSON with expected structure."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "image", "list", "--json"])
    images = json.loads(result.stdout)

    assert isinstance(images, list)
    assert len(images) >= 1
    assert images[0]["name"] == "jupyterlab"
    assert "description" in images[0]


def test_image_list_text(e2e_deployment: EndToEndDeployment) -> None:
    """Verify list --text returns comma-separated image names."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "image", "list", "--text"])
    names = result.stdout.strip().split(",")
    assert "jupyterlab" in names


# ── image status ───────────────────────────────────────────────────────────


def test_image_status(e2e_deployment: EndToEndDeployment) -> None:
    """Verify status reports the image as available."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "image", "status"])
    assert "jupyterlab status:" in result.stdout
    assert "Available" in result.stdout


def test_image_status_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify status for a non-existent image fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError) as exc_info:
        e2e_deployment.cli.run_command(["jupyter-deploy", "image", "status", "--name", "nonexistent"])
    assert "nonexistent" in str(exc_info.value)


# ── image show ─────────────────────────────────────────────────────────────


def test_image_show(e2e_deployment: EndToEndDeployment) -> None:
    """Verify show displays image details."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "image", "show"])
    assert "jupyterlab" in result.stdout
    assert "ecr" in result.stdout.lower()


def test_image_show_json(e2e_deployment: EndToEndDeployment) -> None:
    """Verify show --json returns valid JSON with expected fields."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "image", "show", "--json"])
    data = json.loads(result.stdout)

    assert data["name"] == "jupyterlab"
    assert "repository_uri" in data
    assert "scanner_type" in data
    assert "scan_status" in data
    assert data["scanner_type"] in ("Inspector Enhanced", "ECR Basic")


def test_image_show_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify show for a non-existent image fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError) as exc_info:
        e2e_deployment.cli.run_command(["jupyter-deploy", "image", "show", "--name", "nonexistent"])
    assert "nonexistent" in str(exc_info.value)


# ── image tags ─────────────────────────────────────────────────────────────


def test_image_tags(e2e_deployment: EndToEndDeployment) -> None:
    """Verify tags shows available tags for the image."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "image", "tags"])
    assert "v1" in result.stdout or "latest" in result.stdout


def test_image_tags_json(e2e_deployment: EndToEndDeployment) -> None:
    """Verify tags --json returns valid JSON with tag details."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "image", "tags", "--json"])
    tags = json.loads(result.stdout)

    assert isinstance(tags, list)
    assert len(tags) >= 1
    assert "tag" in tags[0]
    assert "pushed_at" in tags[0]
    assert "digest" in tags[0]


def test_image_tags_text(e2e_deployment: EndToEndDeployment) -> None:
    """Verify tags --text returns comma-separated tag names."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "image", "tags", "--text"])
    tag_names = result.stdout.strip().split(",")
    assert len(tag_names) >= 1
    assert any(t in tag_names for t in ["v1", "latest"])


# ── image vulnerabilities ──────────────────────────────────────────────────


def test_image_vulnerabilities(e2e_deployment: EndToEndDeployment) -> None:
    """Verify vulnerabilities returns scan results."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "image", "vulnerabilities"])
    assert "Summary" in result.stdout
    assert "CRITICAL" in result.stdout or "No HIGH or CRITICAL" in result.stdout


def test_image_vulnerabilities_json(e2e_deployment: EndToEndDeployment) -> None:
    """Verify vulnerabilities --json returns valid JSON with expected structure."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "image", "vulnerabilities", "--json"])
    data = json.loads(result.stdout)

    assert data["image"] == "jupyterlab"
    assert "tag" in data
    assert "vulnerabilities" in data
    assert "summary" in data
    assert "critical" in data["summary"]
    assert "high" in data["summary"]
    assert isinstance(data["vulnerabilities"], list)
    # Each vulnerability carries an EPSS field (float when the scanner provides it, else null).
    for vuln in data["vulnerabilities"]:
        assert "epss_score" in vuln
        assert vuln["epss_score"] is None or isinstance(vuln["epss_score"], int | float)


def test_image_vulnerabilities_with_tag(e2e_deployment: EndToEndDeployment) -> None:
    """Verify vulnerabilities with explicit --tag works."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "image", "vulnerabilities", "--tag", "v1", "--json"])
    data = json.loads(result.stdout)
    assert data["tag"] == "v1"


def test_image_vulnerabilities_tag_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify vulnerabilities with non-existent tag fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError) as exc_info:
        e2e_deployment.cli.run_command(["jupyter-deploy", "image", "vulnerabilities", "--tag", "v999"])
    assert "v999" in str(exc_info.value)


def test_image_vulnerabilities_image_not_found(e2e_deployment: EndToEndDeployment) -> None:
    """Verify vulnerabilities with non-existent image name fails gracefully."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError) as exc_info:
        e2e_deployment.cli.run_command(["jupyter-deploy", "image", "vulnerabilities", "--name", "nonexistent"])
    assert "nonexistent" in str(exc_info.value)
