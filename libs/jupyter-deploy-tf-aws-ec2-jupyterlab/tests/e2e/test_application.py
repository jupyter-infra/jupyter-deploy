"""E2E tests for application functionality — notebook execution in JupyterLab.

This template reaches JupyterLab through the local client proxy (no public URL, no OAuth),
so access goes through ``client_proxy_app`` rather than ``github_oauth_app``: it starts
``jd proxy start`` and points the browser at the loopback URL. There is no browser sign-in
and no ``--ci-dir`` bot credentials — the proxy injects the STS-identity token itself.
"""

from pathlib import Path

from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.local_proxy import LocalProxyApplication
from pytest_jupyter_deploy.notebook import delete_notebook, run_notebook_in_jupyterlab, upload_notebook


def test_application_simple_python(
    e2e_deployment: EndToEndDeployment,
    client_proxy_app: LocalProxyApplication,
) -> None:
    """Run a simple Python notebook through the proxy-tunneled JupyterLab."""
    # The client_proxy_app fixture already ensured the server is running and started the proxy.
    client_proxy_app.verify_jupyterlab_accessible()

    # Get path to the notebook
    notebook_dir = Path(__file__).parent / "notebooks"
    notebook_path = notebook_dir / "application_simple.ipynb"

    # Upload the notebook (returns a unique path to avoid jupyter-server-documents
    # Y-doc room collisions between test runs)
    server_path = upload_notebook(e2e_deployment, notebook_path, "e2e-test/application_simple.ipynb")

    # Run the notebook in the UI
    run_notebook_in_jupyterlab(client_proxy_app.page, server_path, timeout_ms=120000)

    # Clean up - delete the notebook
    delete_notebook(e2e_deployment, server_path)
