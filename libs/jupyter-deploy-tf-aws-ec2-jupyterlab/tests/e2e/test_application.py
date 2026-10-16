"""E2E tests for application functionality — notebook execution in JupyterLab.

This template reaches JupyterLab through the local client proxy (no public URL, no OAuth),
so access goes through ``client_proxy_app`` rather than ``github_oauth_app``: it starts
``jd proxy start`` and points the browser at the loopback URL. There is no browser sign-in
and no ``--ci-dir`` bot credentials — the proxy injects the STS-identity token itself.
"""

import contextlib
from pathlib import Path

import pytest
import requests
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.local_proxy import LocalProxyApplication
from pytest_jupyter_deploy.local_proxy.jupyterlab import api_session
from pytest_jupyter_deploy.notebook import delete_notebook, run_notebook_in_jupyterlab, upload_notebook

pytestmark = pytest.mark.proxy


def test_application_simple_python(
    e2e_deployment: EndToEndDeployment,
    client_proxy_app: LocalProxyApplication,
) -> None:
    """Run a simple Python notebook through the proxy-tunneled JupyterLab."""
    # `client_proxy_app` only ensures the project is DEPLOYED and starts the proxy — it
    # deliberately does not restart the server (that would heal the very failure the
    # full_deployment test in test_deployment.py exists to detect). Tests that merely need a
    # running server, rather than asserting one, ask for it here.
    e2e_deployment.ensure_server_running()
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


def test_application_kernel_survives_proxy_restart(
    e2e_deployment: EndToEndDeployment,
    client_proxy_app: LocalProxyApplication,
) -> None:
    """A running kernel survives stopping and restarting the local proxy.

    The proxy's second job, after "make the app reachable": be *disposable*. It is a local
    process a user will kill, lose to a laptop sleep, or restart to pick up new credentials —
    and each restart binds a NEW loopback port. None of that may cost the user their kernel,
    because the kernel lives on the remote instance and the proxy holds no session state of its
    own. If it did (sticky routing, session affinity, anything cached), a restart would silently
    orphan running work — the failure would look like Jupyter's fault, not the proxy's.
    """
    e2e_deployment.ensure_server_running()
    client_proxy_app.verify_jupyterlab_accessible()

    origin = e2e_deployment.cli.get_proxy_url()
    session, xsrf_headers = api_session(origin)
    with session:
        created = session.post(f"{origin}/api/kernels", headers=xsrf_headers, json={"name": "python3"}, timeout=60)
        created.raise_for_status()
        kernel_id = created.json()["id"]

    try:
        # A full stop/start, not a reload: the point is that the proxy is a new process on a new
        # port, with nothing carried over.
        #
        # `stop_proxy_if_running`, not `stop_proxy`: after a browser session the old proxy is
        # sometimes already gone (its graceful shutdown has to close live kernel websockets, and
        # a SIGKILL escalation leaves no shutdown log — see the WS-stability issue). Whether the
        # old proxy needed stopping or had already exited is immaterial to the property under
        # test; insisting on a successful stop would only make this assert the proxy's shutdown
        # timing instead of the kernel's independence from it.
        e2e_deployment.cli.stop_proxy_if_running()
        new_origin = e2e_deployment.cli.start_proxy(replace=True)
        assert new_origin != origin, "Expected the restarted proxy to bind a different port"

        client_proxy_app.attach()
        client_proxy_app.verify_jupyterlab_accessible()

        listed = requests.get(f"{new_origin}/api/kernels", timeout=60)
        listed.raise_for_status()
        assert kernel_id in [kernel["id"] for kernel in listed.json()], (
            f"Kernel {kernel_id} did not survive the proxy restart; the proxy is holding session state"
        )
    finally:
        with contextlib.suppress(Exception):
            origin_now = e2e_deployment.cli.get_proxy_url()
            cleanup_session, cleanup_headers = api_session(origin_now)
            with cleanup_session:
                cleanup_session.delete(f"{origin_now}/api/kernels/{kernel_id}", headers=cleanup_headers, timeout=30)
