"""E2E tests for `jd server` — the three services THIS template declares.

Every verb is wired through this template's own SSM documents and its own service set
(``jupyter``, ``traefik``, ``auth-sidecar``), so a manifest or document regression is a template
bug the base suite cannot catch. The service set is the substantive difference: base has
``oauth`` where this has ``auth-sidecar``, and only this template can observe an authorization
decision in a service log.

Omitted: covered by the base template suite (`test_server.py`)
  The pure CLI-mechanics cases: piped log arguments (`-- --tail 5` returning exactly 5 entries),
  default-service resolution for `exec`, and non-zero exit propagation from `server exec`. All
  three are argument-plumbing in the CLI layer, identical for every template.
"""

import pexpect
import pytest
from pytest_jupyter_deploy.cli import JDCliError
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.local_proxy import LocalProxyApplication
from pytest_jupyter_deploy.local_proxy.jupyterlab import AUTH_PROBE_PATH
from pytest_jupyter_deploy.local_proxy.requests import pinned_request

# The services this template's manifest declares. `jd server logs`/`exec` must work for each.
_DECLARED_SERVICES = ["jupyter", "traefik", "auth-sidecar"]


def test_server_running(e2e_deployment: EndToEndDeployment) -> None:
    """The `server.status` manifest command reports the app in service."""
    e2e_deployment.ensure_server_running()

    server_status = e2e_deployment.cli.get_server_status()
    assert server_status == "IN_SERVICE", f"Expected server status 'IN_SERVICE', got '{server_status}'"


@pytest.mark.cli
def test_server_show(e2e_deployment: EndToEndDeployment) -> None:
    """`jd server show` prints the `docker inspect` of the jupyter container by default."""
    e2e_deployment.ensure_server_running()

    details = e2e_deployment.cli.run_show_json(["jupyter-deploy", "server", "show"])
    assert details["name"] == "jupyter", f"Expected server name 'jupyter', got: {details}"
    assert details["resource"]["Name"] == "/jupyter", f"Expected the jupyter container, got: {details['resource']}"
    assert details["resource"]["State"]["Running"] is True, f"Expected a running container: {details['resource']}"


@pytest.mark.cli
@pytest.mark.parametrize("service", ["auth-sidecar", "traefik"])
def test_server_show_service(e2e_deployment: EndToEndDeployment, service: str) -> None:
    """`jd server show --service` inspects that service's container instead; `--name` is ignored."""
    e2e_deployment.ensure_server_running()

    details = e2e_deployment.cli.run_show_json(
        ["jupyter-deploy", "server", "show", "--service", service, "--name", "anything"]
    )
    assert details["name"] == service, f"Expected server name '{service}', got: {details}"
    assert details["resource"]["Name"] == f"/{service}", f"Expected the {service} container, got: {details['resource']}"
    assert details["resource"]["State"]["Running"] is True, f"Expected a running container: {details['resource']}"


def test_stop_server(e2e_deployment: EndToEndDeployment) -> None:
    """`jd server stop` takes the app out of service while the host stays up."""
    e2e_deployment.ensure_server_running()

    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "stop"])
    server_status = e2e_deployment.cli.get_server_status()
    assert server_status == "STOPPED", f"Expected server status 'STOPPED', got '{server_status}'"


def test_start_server(e2e_deployment: EndToEndDeployment, client_proxy_app: LocalProxyApplication) -> None:
    """`jd server start` brings the app back into service, and JupyterLab renders again.

    Paired with the stop above so the two share one container cycle (cheap, unlike an EC2
    stop/start). The browser check is the part that matters: a service that reports IN_SERVICE but
    does not render is the failure mode users actually hit, and `IN_SERVICE` is a host-side health
    check with no view of the app the user came for.
    """
    e2e_deployment.ensure_server_stopped_and_host_is_running()

    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "start"])
    server_status = e2e_deployment.cli.get_server_status()
    assert server_status == "IN_SERVICE", f"Expected server status 'IN_SERVICE', got '{server_status}'"

    e2e_deployment.cli.start_proxy(replace=True)
    try:
        # attach(), not the fixture's setup-time URL: `replace=True` rebinds a fresh port, so the
        # URL captured at setup points at a dead proxy and would read as an app failure.
        client_proxy_app.attach()
        client_proxy_app.verify_jupyterlab_accessible()
    finally:
        e2e_deployment.cli.stop_proxy_if_running()


@pytest.mark.parametrize("service", _DECLARED_SERVICES)
def test_all_service_logs(
    e2e_deployment: EndToEndDeployment, client_proxy_app: LocalProxyApplication, service: str
) -> None:
    """`jd server logs -s <service>` returns output for each declared service.

    Parametrized over the manifest's service list rather than hard-coded per service, so adding
    a service to the manifest without wiring its logs fails here.

    The app is visited first, whcih guarantees there are logs for `traefik`: it is configured with
    `accessLog` but no `log` section, so it inherits traefik's default ERROR level and writes
    NOTHING to stdout until it either serves a request or fails. `ensure_server_running()` does not
    produce one -- the readiness probe is `docker exec jupyter curl localhost:8888/...`, inside the
    container, never through traefik's :8443. So after any test that recreates the containers
    (`jd server stop` immediately precedes this one), a freshly started traefik has an empty log and
    `jd server logs -s traefik` answers "no logs were retrieved". The base template's
    `test_all_service_logs` visits the app first for exactly this reason.
    """
    e2e_deployment.ensure_server_running()
    client_proxy_app.verify_jupyterlab_accessible()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "logs", "-s", service])
    assert result.stdout, f"Expected non-empty logs output for {service}"
    assert "stdout" in result.stdout or "stderr" in result.stdout, f"Expected log output markers for {service}"


def test_auth_sidecar_logs_show_the_authorization_decision(e2e_deployment: EndToEndDeployment) -> None:
    """A rejected request appears in the sidecar's log, with its status and reason.

    The auth plane has to be *observable* — it is the one component that can make the app
    unreachable while every other status reads healthy, so "why am I getting 401" must be
    answerable from `jd server logs -s auth-sidecar`. Note the sidecar logs only failures by
    design: a success is the hot path (once per request, and a websocket replays it constantly),
    so logging it would spam the log and re-emit the caller's identity and full browsing path.
    """
    e2e_deployment.ensure_server_running()
    bundle = e2e_deployment.cli.get_connect_bundle()

    status, _ = pinned_request(bundle["host"], bundle["port"], bundle["ca_cert"], path=AUTH_PROBE_PATH, headers={})
    assert status == 401, f"Expected the probe request to be rejected, got {status}"

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "logs", "-s", "auth-sidecar"])
    assert "auth 401" in result.stdout, (
        f"The sidecar did not log its 401 decision; the auth plane is not observable:\n{result.stdout[-2000:]}"
    )


def test_server_exec_shell_services(e2e_deployment: EndToEndDeployment) -> None:
    """`jd server exec` reaches into each service the exec document supports.

    Two of the three declared services, and each needs a different probe, which is the point:
    ``jupyter`` runs as ``jovyan`` under the package manager, ``traefik`` has a shell but no user
    tooling. ``auth-sidecar`` is excluded by design — see the rejection test below.
    """
    e2e_deployment.ensure_server_running()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "-s", "jupyter", "--", "whoami"])
    assert "jovyan" in result.stdout, f"Expected 'jovyan' user in jupyter, got: {result.stdout}"

    result = e2e_deployment.cli.run_command(
        ["jupyter-deploy", "server", "exec", "-s", "traefik", "--", "ps", "|", "grep", "traefik"]
    )
    assert "traefik" in result.stdout, f"Expected 'traefik' process in output, got: {result.stdout}"


def test_server_exec_rejects_auth_sidecar(e2e_deployment: EndToEndDeployment) -> None:
    """`jd server exec -s auth-sidecar` is refused, with a handled error rather than a traceback.

    The refusal is intentional and enforced two layers deep: the sidecar image is
    distroless/nonroot with no shell to exec into, and the SSM exec document encodes that by
    restricting its ``service`` parameter to ``allowedValues: [jupyter, traefik]``. So AWS
    rejects the request before it reaches the instance.

    What this pins is the *shape* of that refusal. AWS answers ``InvalidParameters`` with a
    message that names no parameter ("Parameters provided in document are invalid or not
    supported"), and an unhandled ``ClientError`` rendered that as a botocore traceback —
    nothing a user could act on for a perfectly reasonable thing to try.
    """
    e2e_deployment.ensure_server_running()

    with pytest.raises(JDCliError) as exc_info:
        e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "-s", "auth-sidecar", "--", "whoami"])
    assert "Traceback" not in str(exc_info.value), (
        f"Expected a handled error for an unsupported exec service, got a traceback: {exc_info.value}"
    )


def test_server_connect_jupyter(e2e_deployment: EndToEndDeployment) -> None:
    """`jd server connect` opens an interactive shell in the jupyter container."""
    e2e_deployment.ensure_server_running()
    e2e_deployment.wait_for_connection_agent()

    with e2e_deployment.cli.spawn_interactive_session("jupyter-deploy server connect -s jupyter") as session:
        session.expect("Starting session with SessionId:", timeout=10)
        session.sendline("whoami")
        session.expect("jovyan", timeout=10)
        session.sendline("exit")
        session.expect(pexpect.EOF, timeout=10)


def test_server_connect_traefik(e2e_deployment: EndToEndDeployment) -> None:
    """`jd server connect -s traefik` opens an interactive shell in the traefik container."""
    e2e_deployment.ensure_server_running()
    e2e_deployment.wait_for_connection_agent()

    with e2e_deployment.cli.spawn_interactive_session("jupyter-deploy server connect -s traefik") as session:
        session.expect("Starting session with SessionId:", timeout=10)
        session.sendline("ps")
        session.expect("traefik", timeout=10)
        session.sendline("exit")
        session.expect(pexpect.EOF, timeout=10)


def test_server_connect_rejects_auth_sidecar(e2e_deployment: EndToEndDeployment) -> None:
    """`jd server connect -s auth-sidecar` cannot open a shell — and says so, rather than hanging.

    The sidecar image is distroless and nonroot: there is no ``/bin/sh`` to attach to, which is
    a security property worth keeping, not a gap to close. The connect document encodes it the
    same way exec does, with ``allowedValues: [jupyter, traefik]``.

    What this pins is the *failure mode*: a user who tries must get a prompt error and a non-zero
    exit, not a session that opens and dies silently, and not one that hangs until the SSM
    timeout. The non-zero exit matters as much as the message — a failure that exits 0 is worse
    than a traceback for anything scripted.
    """
    e2e_deployment.ensure_server_running()
    e2e_deployment.wait_for_connection_agent()

    with pytest.raises(JDCliError) as exc_info:
        e2e_deployment.cli.run_command(
            ["jupyter-deploy", "server", "connect", "-s", "auth-sidecar"], timeout_seconds=120
        )
    assert "Traceback" not in str(exc_info.value), (
        f"Expected a handled failure for a shell-less container, got a traceback: {exc_info.value}"
    )
