"""E2E golden-path user journey on the EKS OIDC template.

One browser session in production auth mode (Dex OAuth via the bot account)
walks the whole workspace lifecycle end to end: landing, create from the
default template, open and run a notebook, stop and start with a
data-persistence check, delete. List views (the default My Workspaces
ownership view and the All view) are asserted at each lifecycle step.
Individual slices of this journey are covered in test_web_app.py; this test
pins the composed flow a first-time user actually follows.
"""

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.notebook import delete_notebook, run_notebook_in_jupyterlab, upload_notebook
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set
from pytest_jupyter_deploy.workspaces.kubectl import ensure_workspace_no_longer_exists
from pytest_jupyter_deploy.workspaces.web_app import WebAppNavigator

from .conftest import WORKSPACE_NAMESPACE
from .test_utils import NOTEBOOKS_DIR

pytestmark = pytest.mark.usefixtures("kubernetes_cluster_login")

PERSISTENCE_FLAG = "e2e-golden-path-flag.txt"


@skip_if_testvars_not_set(["JD_E2E_USER", "JD_E2E_ORG", "JD_E2E_RBAC_TEAM"])
def test_golden_path_workspace_journey(
    e2e_deployment: EndToEndDeployment,
    dex_oauth_web_app: WebAppNavigator,
) -> None:
    """Login → create → list → open + notebook → stop/start with persistence → delete.

    1. OAuth login lands on the workspace list (heading visible)
    2. Create a workspace from the default template via the UI
    3. The workspace appears in My Workspaces (ownership view) and in All
    4. Open it from its card → JupyterLab loads → run kernel_simple.ipynb
    5. Create a file in the home volume, stop via the UI (card shows Start),
       start again, and the file is still there
    6. Delete via the UI → gone from the cluster and from both list views
    """
    e2e_deployment.ensure_deployed()

    with dex_oauth_web_app.default_workspace() as workspace_name:
        # create_default_workspace ends on the detail page
        dex_oauth_web_app.wait_for_running()

        # The bot user created the workspace, so it must appear in the default
        # My Workspaces (ownership) view as well as in All.
        dex_oauth_web_app.goto_workspace_list()
        my_card = dex_oauth_web_app.get_workspace_card(workspace_name)
        my_card.wait_for(state="visible", timeout=30000)
        assert my_card.is_visible(), f"Workspace '{workspace_name}' missing from the My Workspaces view"

        dex_oauth_web_app.goto_workspace_list(view_all=True)
        assert dex_oauth_web_app.get_workspace_card(workspace_name).is_visible(), (
            f"Workspace '{workspace_name}' missing from the All view"
        )

        # Open from the card → JupyterLab loads → the kernel executes a notebook.
        dex_oauth_web_app.goto_workspace_list()
        dex_oauth_web_app.open_workspace_from_card(workspace_name)
        dex_oauth_web_app.verify_jupyterlab_loaded()

        e2e_deployment.cli.wait_for_workspace_pod_exec_ready(workspace_name)
        server_path = upload_notebook(
            e2e_deployment,
            NOTEBOOKS_DIR / "kernel_simple.ipynb",
            "e2e-test/kernel_simple.ipynb",
            name=workspace_name,
            scope=WORKSPACE_NAMESPACE,
        )
        run_notebook_in_jupyterlab(dex_oauth_web_app.page, server_path, timeout_ms=120000)
        delete_notebook(e2e_deployment, server_path, name=workspace_name, scope=WORKSPACE_NAMESPACE)

        # Persistence marker in the home volume, then stop from the detail page.
        e2e_deployment.cli.run_exec_with_retry(
            ["jupyter-deploy", "server", "exec", "--name", workspace_name, "--", "touch", PERSISTENCE_FLAG]
        )
        dex_oauth_web_app.goto_workspace_detail(workspace_name)
        dex_oauth_web_app.stop_workspace()
        assert not dex_oauth_web_app.get_open_button().is_visible(), (
            "Open button should disappear when the workspace is Stopped"
        )

        dex_oauth_web_app.goto_workspace_list()
        assert dex_oauth_web_app.get_workspace_card_start_button(workspace_name).is_visible(), (
            f"Stopped workspace '{workspace_name}' card should offer Start"
        )

        # Start again; the home volume (and the file) must survive the cycle.
        dex_oauth_web_app.goto_workspace_detail(workspace_name)
        dex_oauth_web_app.start_workspace()
        e2e_deployment.cli.wait_for_workspace_pod_exec_ready(workspace_name)
        result = e2e_deployment.cli.run_exec_with_retry(
            ["jupyter-deploy", "server", "exec", "--name", workspace_name, "--", "ls", PERSISTENCE_FLAG]
        )
        assert PERSISTENCE_FLAG in result.stdout, (
            f"Home-volume file did not survive the stop/start cycle: {result.stdout}"
        )

        # Delete through the UI; the workspace leaves the cluster and both views.
        dex_oauth_web_app.delete_workspace_from_list(workspace_name)
        ensure_workspace_no_longer_exists(workspace_name)

        dex_oauth_web_app.goto_workspace_list(view_all=True)
        assert not dex_oauth_web_app.get_workspace_card(workspace_name).is_visible(), (
            f"Deleted workspace '{workspace_name}' still shows in the All view"
        )
        dex_oauth_web_app.goto_workspace_list()
        assert not dex_oauth_web_app.get_workspace_card(workspace_name).is_visible(), (
            f"Deleted workspace '{workspace_name}' still shows in the My Workspaces view"
        )
