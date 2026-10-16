"""E2E tests for CLI behavior on an undeployed project — proxy commands only.

Omitted: covered by the base template suite (`test_undeployed_project.py`, 4 tests)
  `jd open` / `jd show` / `jd show --info` / `jd show --variable` on an un-configured project.
  All four are CLI-layer graceful-failure behavior, template-independent, and each costs a
  `jd init` to assert.

Kept: the two `jd proxy` cases. The command group is new (#348) and its undeployed behavior is
covered nowhere — and it is the likeliest thing a user hits first, because on this template
`jd proxy start` is the access path, so running it before `jd up` is an easy mistake to make.
Both must fail with an actionable message, not a traceback: there are no outputs yet to resolve
an endpoint, a cert or a token from.
"""

import subprocess
from pathlib import Path

import pytest
from pytest_jupyter_deploy.cli import JDCli


@pytest.mark.proxy
@pytest.mark.no_deploy
def test_proxy_status_on_undeployed_project(initialized_project: tuple[Path, JDCli]) -> None:
    """`jd proxy status` on an undeployed project reports no proxy, without a traceback."""
    project_path, _ = initialized_project

    result = subprocess.run(
        ["jupyter-deploy", "proxy", "status"],
        capture_output=True,
        text=True,
        cwd=project_path,
    )
    assert result.returncode != 0, "jd proxy status should exit non-zero when no proxy is running"
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr


@pytest.mark.proxy
@pytest.mark.no_deploy
def test_proxy_start_fails_on_undeployed_project(initialized_project: tuple[Path, JDCli]) -> None:
    """`jd proxy start` before `jd up` fails gracefully — there is no endpoint to resolve.

    The proxy needs three things from the deployment's outputs (the instance endpoint, the cert
    to pin, the deployment id to bind the token to), so on an un-applied project it cannot start
    at all. It must say so rather than crash or, worse, bind a port that tunnels nowhere.
    """
    project_path, _ = initialized_project

    result = subprocess.run(
        ["jupyter-deploy", "proxy", "start"],
        capture_output=True,
        text=True,
        cwd=project_path,
        timeout=180,
    )
    assert result.returncode != 0, "jd proxy start should exit non-zero on an undeployed project"
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr
