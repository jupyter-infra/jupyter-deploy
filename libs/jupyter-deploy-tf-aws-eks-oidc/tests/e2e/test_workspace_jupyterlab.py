"""E2E tests for JupyterLab notebook execution on the EKS OIDC template.

Verifies that a workspace serves a functional JupyterLab: uploads a simple
notebook, runs it via the browser, and checks all cells execute without error.
Requires OIDC auth + playwright.
"""

from pathlib import Path

from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.notebook import delete_notebook, run_notebook_in_jupyterlab, upload_notebook
from pytest_jupyter_deploy.oauth2_proxy.dex import DexGitHubOAuth2ProxyApplication
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.workspaces.kubectl import kubectl_get_workspace_access_url

from .conftest import WORKSPACE_NAMESPACE

NOTEBOOKS_DIR = Path(__file__).parent / "notebooks"


@skip_if_testvars_not_set(["JD_E2E_USER"])
def test_run_simple_notebook(
    e2e_deployment: EndToEndDeployment,
    dex_oauth_app: DexGitHubOAuth2ProxyApplication,
    e2e_workspace: str,
) -> None:
    """Upload and run a simple notebook in a workspace via JupyterLab UI."""
    e2e_deployment.ensure_deployed()

    # Navigate to workspace JupyterLab and authenticate
    access_url = kubectl_get_workspace_access_url(e2e_workspace, WORKSPACE_NAMESPACE)
    dex_oauth_app.verify_workspace_accessible(access_url)

    # Upload notebook
    notebook_path = NOTEBOOKS_DIR / "kernel_simple.ipynb"
    server_path = upload_notebook(
        e2e_deployment,
        notebook_path,
        "e2e-test/kernel_simple.ipynb",
        name=e2e_workspace,
        scope=WORKSPACE_NAMESPACE,
    )

    # Run the actual notebook
    run_notebook_in_jupyterlab(dex_oauth_app.page, server_path, timeout_ms=120000)

    # Cleanup
    delete_notebook(e2e_deployment, server_path, name=e2e_workspace, scope=WORKSPACE_NAMESPACE)
