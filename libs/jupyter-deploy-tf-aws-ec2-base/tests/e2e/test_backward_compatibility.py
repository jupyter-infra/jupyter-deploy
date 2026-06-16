"""E2E tests for variables.yaml backward compatibility (v1 → v2 migration)."""

import pytest
import yaml
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.undeployed_project import undeployed_project


@pytest.mark.cli
@skip_if_testvars_not_set(
    [
        "JD_E2E_VAR_DOMAIN",
        "JD_E2E_VAR_EMAIL",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_ID",
        "JD_E2E_VAR_OAUTH_ALLOWED_TEAMS",
        "JD_E2E_VAR_OAUTH_ALLOWED_USERNAMES",
        "JD_E2E_VAR_SUBDOMAIN",
        "JD_E2E_VAR_OAUTH_APP_CLIENT_SECRET",
    ]
)
def test_variables_yaml_v1_still_readable_but_produces_v2(e2e_deployment: EndToEndDeployment) -> None:
    """Verify that jd config reads a v1 variables.yaml and upgrades it to v2 on write.

    Flow:
    1. Initialize a project (produces v2)
    2. Overwrite variables.yaml with a valid v1-format file
    3. Run `jd config` — should succeed
    4. Verify the resulting variables.yaml is v2 (no `defaults` section)
    """
    with undeployed_project(e2e_deployment.suite_config) as (project_path, cli):
        # Prepare a valid configuration, then downgrade to v1
        e2e_deployment.suite_config.prepare_configuration("base", target_dir=project_path)

        variables_path = project_path / "variables.yaml"
        with open(variables_path) as f:
            config = yaml.safe_load(f)

        v1_config = {
            "schema_version": 1,
            "required": config.get("required", {}),
            "required_sensitive": config.get("required_sensitive", {}),
            "overrides": config.get("overrides", {}),
            "defaults": {"instance_type": "t3.medium", "region": "us-west-2"},
        }
        with open(variables_path, "w") as f:
            yaml.dump(v1_config, f, sort_keys=False)

        # Run jd config on the v1 file — should succeed and upgrade
        result = cli.run_command(["jupyter-deploy", "config"])
        assert "Your project is ready" in result.stdout

        # Verify the file is now v2
        with open(variables_path) as f:
            upgraded = yaml.safe_load(f)
        assert upgraded["schema_version"] == 2, f"Expected schema_version 2, got {upgraded['schema_version']}"
        assert "defaults" not in upgraded, "v2 should not have a 'defaults' section"
        assert "overrides" in upgraded
