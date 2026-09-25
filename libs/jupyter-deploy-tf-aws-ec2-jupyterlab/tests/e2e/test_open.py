"""E2E tests for `jd open` in proxy mode — both attached and detached.

`jd open` routes through the proxy rather than hitting the DNS with a public URL. There
is nothing to hand to a browser until a local proxy exists, so `jd open` *owns* the proxy
lifecycle (it replaces any running proxy, where `jd proxy start` refuses to) and, unless
``--detached`` is passed, stays in the foreground for as long as the tunnel is up.

Omitted: covered by the base template suite (`test_open.py::test_open_show_correct_url`)
  The public-URL flow — resolving `open_url` and asserting an https:// address. It cannot
  apply here: there is no such output and the URL is loopback http by design.

Omitted: covered by the base template suite (`test_open_rejects_server_name_on_a_single_app_template`)
  Rejecting `--server-name`. The guard is in `OpenHandler.open` and both templates lack the
  `open.server` command, so one suite is enough. Note what that leaves untested here: passing
  a name is what makes `is_proxy_open` false in proxy mode, so a change to that condition could
  start a proxy and ignore the flag, and only a jupyterlab test would see it.

Deliberately elsewhere:
  - "jd open fails cleanly while the host is stopped" is asserted in ``test_host.py``, which
    owns the suite's single EC2 stop/start cycle.

Every test here sets $BROWSER to a no-op: the container has no launchable browser, and
`jd open` exits non-zero (OpenWebBrowserError) when the launch fails, which would otherwise
make every assertion here a test of the container's browser rather than of `jd open`.
"""

import re

import pexpect
import pytest
import requests
from pytest_jupyter_deploy.cli import NOOP_BROWSER, JDCli, JDCliError
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.local_proxy import LocalProxyApplication
from pytest_jupyter_deploy.local_proxy.jupyterlab import AUTH_PROBE_PATH


def test_open_detached_opens_jupyterlab_in_a_browser(
    e2e_deployment: EndToEndDeployment, client_proxy_app: LocalProxyApplication
) -> None:
    """`jd open -d` yields a URL a browser can actually load JupyterLab from.

    The whole user-facing flow in one test, driven exactly as a user drives it: `jd open -d` owns the
    proxy lifecycle, prints a loopback URL, and hands the shell back — then a real browser navigates
    to *that* URL and the JupyterLab shell has to render.

    Navigating rather than issuing a `GET` is the point. A 200 from ``requests`` proves the tunnel
    carries one HTTP request; it says nothing about whether the app is usable, which additionally
    needs the static assets and the kernel websocket to come through the proxy. Those are exactly the
    parts a header-rewriting or subprotocol-dropping bug breaks while `/api/status` stays green.
    """
    e2e_deployment.ensure_server_running()
    e2e_deployment.cli.stop_proxy_if_running()
    try:
        url = client_proxy_app.open_via_cli(detached=True)
        assert url.startswith("http://127.0.0.1:"), f"Expected a loopback URL from `jd open -d`, got: {url}"

        client_proxy_app.verify_jupyterlab_accessible()

        assert e2e_deployment.cli.get_proxy_status() == "running", "A detached proxy must outlive `jd open -d`"
    finally:
        e2e_deployment.cli.stop_proxy_if_running()


def test_open_url_is_loopback_http_not_https(e2e_deployment: EndToEndDeployment) -> None:
    """The opened URL is ``http://127.0.0.1:<port><manifest path>`` — not https, not a hostname.

    A guard on ``_is_secure_open_url``, which had to be relaxed from "https only" to also
    accept http loopback for this template. The relaxation must stay exactly that narrow: an
    http URL is only safe because it never leaves the machine, so a non-loopback http URL —
    or a hostname smuggled in through the manifest path — must not be openable.
    """
    e2e_deployment.ensure_server_running()
    e2e_deployment.cli.stop_proxy_if_running()
    try:
        url = e2e_deployment.cli.open_app(detached=True)

        assert url.startswith("http://127.0.0.1:"), f"Expected a loopback http URL, got: {url}"
        expected_path = e2e_deployment.get_manifest().get_open().path
        assert url.endswith(expected_path), f"Expected the URL to end with the manifest path {expected_path}: {url}"
    finally:
        e2e_deployment.cli.stop_proxy_if_running()


def test_open_attached_runs_foreground_until_interrupted(e2e_deployment: EndToEndDeployment) -> None:
    """Attached `jd open` blocks, serves the app, prints the Ctrl-C hint, and leaves nothing behind.

    The attached proxy shares the terminal's process group, so Ctrl-C reaches it too and it
    shuts down gracefully with its parent. "Leaves nothing behind" is the load-bearing half:
    an attached proxy that survived its `jd open` would wedge the next `jd proxy start` with
    ProxyAlreadyRunningError and keep a tunnel open the user believes they closed.

    The reachability probe runs while the command is still blocked, which is the only window in
    which an attached proxy can be observed serving at all. Asserting the URL was printed is not
    enough: a well-formed URL that answers nothing is exactly the failure a user would report as
    "`jd open` did nothing".
    """
    e2e_deployment.ensure_server_running()
    e2e_deployment.cli.stop_proxy_if_running()

    with e2e_deployment.cli.spawn_interactive_session(
        "jupyter-deploy open", timeout=180, env={"BROWSER": NOOP_BROWSER}
    ) as session:
        # Match the label only, never `Opening app at:\s+http://…`: on a tty rich styles the URL
        # as its own span, so the rendered bytes are
        # `\x1b[32mOpening app at: \x1b[0m\x1b[4;94mhttp://127.0.0.1:PORT/lab\x1b[0m` and any
        # pattern spanning the two tokens fails on the escapes between them. The URL is recovered
        # from the ANSI-stripped transcript below instead.
        session.expect("Opening app at")
        # The hint is the proof it is about to block rather than return.
        session.expect("Interrupt this command")
        # `isinstance` rather than `or ""`: pexpect types both as `str | type[EOF] | type[TIMEOUT]`,
        # and the class arms are truthy, so `or ""` would not narrow them for the concatenation.
        before = session.before if isinstance(session.before, str) else ""
        after = session.after if isinstance(session.after, str) else ""
        transcript = JDCli.strip_ansi(before + after)

        origin = re.search(r"http://127\.0\.0\.1:\d+", transcript)
        assert origin, f"Attached `jd open` did not print a loopback URL:\n{transcript[-1500:]}"

        # One GET, no polling: `jd open` only prints the URL after the app answers, so a proxy
        # that is up cannot still be warming up here.
        response = requests.get(f"{origin.group(0)}{AUTH_PROBE_PATH}", timeout=60)
        assert response.status_code == 200, (
            f"App not reachable at the URL attached `jd open` printed "
            f"({origin.group(0)}{AUTH_PROBE_PATH}): {response.status_code}"
        )

        session.sendintr()
        session.expect(pexpect.EOF, timeout=60)

    # Deliberately not asserting a specific exit code: `jd open` catches the KeyboardInterrupt
    # to let the proxy shut down gracefully, so the observable contract is that it exited and
    # took the proxy with it — not the code it exited with.
    with pytest.raises(JDCliError):
        e2e_deployment.cli.get_proxy_status()


def test_open_replaces_a_running_proxy(e2e_deployment: EndToEndDeployment) -> None:
    """`jd open -d` replaces an already-running proxy, unlike `jd proxy start` which refuses.

    The asymmetry is intentional and worth pinning: `jd open` owns the lifecycle (a user
    re-running it expects a working tab, not an error), while the explicit `jd proxy start`
    refuses to tear down a proxy another tab may be using.
    """
    e2e_deployment.ensure_server_running()
    e2e_deployment.cli.stop_proxy_if_running()
    e2e_deployment.cli.start_proxy()
    try:
        original_pid = e2e_deployment.cli.get_proxy_details()["pid"]

        e2e_deployment.cli.open_app(detached=True)

        details = e2e_deployment.cli.get_proxy_details()
        assert details["pid"] != original_pid, "jd open -d should have replaced the running proxy, not reused it"
        assert details["running"] is True, f"The replacement proxy is not running: {details}"
    finally:
        e2e_deployment.cli.stop_proxy_if_running()
