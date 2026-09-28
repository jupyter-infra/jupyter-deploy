"""E2E tests for `jd host` — and the owner of this suite's single EC2 stop/start cycle.

`jd host` is not CLI-generic: every verb here is declared in THIS template's `manifest.yaml`
(its own SSM document set, its own instance output), so a broken manifest is a template bug the
base suite cannot catch.

Omitted: covered by the base template suite (`test_host.py`)
  Nothing is dropped outright — the base file's cases all apply. What differs is the *shape*
  below.

**Why one fixture instead of four tests that each stop the host.** The base template pays an
EC2 stop/start (~2-4 minutes of pure waiting) four separate times: `test_host_stop`,
`test_host_start`, `test_home_volume_persists_across_host_restart`, and
`test_cert_pin_stable_across_host_restart`. Every property those assert is observable from ONE
cycle, so ``host_cycle`` performs a single stop and a single start, records everything, and each
test asserts one recorded fact. That is ~6 minutes saved — more than any parallelism option
considered for this suite — with no concurrency risk.

The trade-off, accepted knowingly: the assertions are coupled to one shared act, so a failure
in the cycle itself fails the whole group rather than pinpointing one command. Per-test
attribution is preserved for everything *after* the cycle runs.

Five assertions live here rather than in the file their subject suggests, for exactly that reason:
`connect-info` failing cleanly against a stopped host *and* reporting that failure as retryable,
`jd open` failing cleanly (all of which would otherwise sit in ``test_proxy.py`` / ``test_open.py``),
and the data-volume and cert-pin survival (which would otherwise sit in ``test_home_volume.py`` /
``test_auth.py``). Each would have bought a second full cycle for a single status check.

The relocated failure cases are named ``test_host_stopped_*`` rather than ``test_proxy_*`` /
``test_open_*`` deliberately: with the old names, `just test-e2e-jupyterlab <dir> test_proxy` matched
one of them and silently dragged the whole ~4-minute EC2 cycle into what should be a fast, scoped
proxy run. A test's name is part of its selection contract when `-k` is the only filter available.
"""

import contextlib
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass

import pexpect
import pytest
from jupyter_deploy.constants import RETRYABLE_EXIT_CODE
from pytest_jupyter_deploy.cli import NOOP_BROWSER, JDCliError
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.local_proxy.jupyterlab import AUTH_PROBE_PATH
from pytest_jupyter_deploy.local_proxy.requests import cert_fingerprint, pinned_request, served_cert_pem

# Written to the home volume before the cycle; its survival is the data-volume remount proof.
_PERSISTENCE_FLAG = "e2e_flag_host_cycle.txt"


@dataclass
class _CommandFailure:
    """How a command failed: with a handled error, and with which exit code.

    Attributes:
        graceful: the CLI reported a handled error rather than letting a traceback escape.
        exit_code: the process exit code (0 if it unexpectedly succeeded, None if unreadable).
    """

    graceful: bool
    exit_code: int | None


@dataclass
class HostCycleObservations:
    """Everything one stop/start cycle reveals, captured as it happens."""

    instance_id_before: str
    instance_id_after: str
    cert_fingerprint_before: str
    stopped_host_status: str
    stopped_connection_status: str
    stopped_connect_info: _CommandFailure
    stopped_open_failed: bool
    stopped_host_status_after_open: str
    running_host_status: str
    running_connection_status: str
    flag_survived: bool
    cert_fingerprint_after: str
    pinned_status_after: int


# --------------------------------------------------------------------------- running-host tests
# Defined before the cycle so they run against the as-deployed instance (pytest executes in
# definition order within a module, and the cycle fixture only materializes on first use).


def test_host_running(e2e_deployment: EndToEndDeployment) -> None:
    """The `host.status` manifest command reports the instance running."""
    e2e_deployment.ensure_host_running()

    host_status = e2e_deployment.cli.get_host_status()
    assert host_status == "running", f"Expected host status 'running', got '{host_status}'"


def test_host_connect_whoami(e2e_deployment: EndToEndDeployment) -> None:
    """`jd host connect` opens an SSM shell on the instance as ``ssm-user``.

    The break-glass path: it is how a user reaches the box when the app itself is broken, so it
    must not depend on anything the app needs (docker, traefik, the sidecar).
    """
    e2e_deployment.ensure_host_running()
    e2e_deployment.wait_for_connection_agent()

    with e2e_deployment.cli.spawn_interactive_session("jupyter-deploy host connect") as session:
        session.expect("Starting session with SessionId:", timeout=10)
        session.sendline("whoami")
        session.expect("ssm-user", timeout=5)
        session.sendline("exit")
        session.expect(pexpect.EOF, timeout=5)


def test_host_exec_simple_command(e2e_deployment: EndToEndDeployment) -> None:
    """`jd host exec` runs a command on the instance (as root, outside the containers)."""
    e2e_deployment.ensure_host_running()
    e2e_deployment.wait_for_host_agent()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "host", "exec", "--", "whoami"])
    assert "root" in result.stdout, f"Expected 'root' in output, got: {result.stdout}"


def test_host_exec_disk_usage(e2e_deployment: EndToEndDeployment) -> None:
    """`jd host exec -- df -h` shows the Jupyter data volume mounted at /mnt/jupyter-data.

    The data volume is what makes the instance disposable: it is mounted over ``/home/jovyan``
    in the container, so if it were missing the app would come up with an empty home and the
    user's work would appear to have vanished.
    """
    e2e_deployment.ensure_host_running()
    e2e_deployment.wait_for_host_agent()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "host", "exec", "--", "df", "-h"])
    assert "/mnt/jupyter-data" in result.stdout, f"Jupyter data volume is not mounted: {result.stdout}"


def test_host_exec_failed_command(e2e_deployment: EndToEndDeployment) -> None:
    """A failing `jd host exec` surfaces the command's own exit code, not a generic error.

    The manifest wires ``host.exec.returncode`` from the SSM response, so this is really a test
    of that wiring: without it every failure would look like success (or like an SSM error) and
    a script run over `jd host exec` could not be trusted.
    """
    e2e_deployment.ensure_host_running()
    e2e_deployment.wait_for_host_agent()

    with pytest.raises(JDCliError) as exc_info:
        e2e_deployment.cli.run_command(["jupyter-deploy", "host", "exec", "--", "command_that_does_not_exist"])

    assert exc_info.value.__cause__ is not None
    assert isinstance(exc_info.value.__cause__, subprocess.CalledProcessError)
    assert exc_info.value.__cause__.returncode == 127


# --------------------------------------------------------------------------- the one cycle


@pytest.fixture(scope="module")
def host_cycle(e2e_deployment: EndToEndDeployment) -> Iterator[HostCycleObservations]:
    """Stop the host once, start it once, and record every property the transition reveals.

    Ordered deliberately: everything observable while stopped is captured before the start, so
    the stopped-state assertions do not need a second stop.
    """
    e2e_deployment.ensure_server_running()
    instance_id_before = e2e_deployment.cli.get_str_output("instance_id")
    bundle_before = e2e_deployment.cli.get_connect_bundle()
    fingerprint_before = cert_fingerprint(served_cert_pem(bundle_before["host"], bundle_before["port"]))
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--", "touch", _PERSISTENCE_FLAG])

    # --- stop once
    e2e_deployment.cli.run_command(["jupyter-deploy", "host", "stop"])
    stopped_host_status = e2e_deployment.cli.get_host_status()
    stopped_connection_status = e2e_deployment.cli.get_connection_status()
    stopped_connect_info = _observe_failure(e2e_deployment, ["jupyter-deploy", "proxy", "connect-info"])
    stopped_open_failed = _observe_failure(e2e_deployment, ["jupyter-deploy", "open", "--detached"]).graceful
    # Read the status straight after the failed `jd open`, while the host is still stopped: this is
    # the only point where "jd open did not start the instance" is observable. Read after the
    # `jd host start` below it would be "running" no matter what `jd open` did.
    stopped_host_status_after_open = e2e_deployment.cli.get_host_status()

    # --- start once
    e2e_deployment.cli.run_command(["jupyter-deploy", "host", "start"])
    running_host_status = e2e_deployment.cli.get_host_status()
    e2e_deployment.wait_for_connection_agent()
    running_connection_status = e2e_deployment.cli.get_connection_status()

    e2e_deployment.ensure_server_running(wait_after_restart=True)
    flag_survived = _flag_present(e2e_deployment, _PERSISTENCE_FLAG)

    instance_id_after = e2e_deployment.cli.get_str_output("instance_id")
    bundle_after = e2e_deployment.cli.get_connect_bundle()
    fingerprint_after = cert_fingerprint(served_cert_pem(bundle_after["host"], bundle_after["port"]))
    pinned_status_after, _ = pinned_request(
        bundle_after["host"],
        bundle_after["port"],
        bundle_after["ca_cert"],
        path=AUTH_PROBE_PATH,
        headers=bundle_after["headers"],
    )

    try:
        yield HostCycleObservations(
            instance_id_before=instance_id_before,
            instance_id_after=instance_id_after,
            cert_fingerprint_before=fingerprint_before,
            stopped_host_status=stopped_host_status,
            stopped_connection_status=stopped_connection_status,
            stopped_connect_info=stopped_connect_info,
            stopped_open_failed=stopped_open_failed,
            stopped_host_status_after_open=stopped_host_status_after_open,
            running_host_status=running_host_status,
            running_connection_status=running_connection_status,
            flag_survived=flag_survived,
            cert_fingerprint_after=fingerprint_after,
            pinned_status_after=pinned_status_after,
        )
    finally:
        # Cleanup must never mask a recorded result.
        with contextlib.suppress(Exception):
            e2e_deployment.cli.run_command(["jupyter-deploy", "server", "exec", "--", "rm", "-f", _PERSISTENCE_FLAG])


def _observe_failure(e2e_deployment: EndToEndDeployment, cmd: list[str]) -> _CommandFailure:
    """Run ``cmd`` once and record how it failed: gracefully or not, and with which exit code.

    One invocation, two observations — running the command twice to ask two questions about the
    same moment would let the answers disagree.
    """
    try:
        e2e_deployment.cli.run_command(cmd, env={"BROWSER": NOOP_BROWSER}, timeout_seconds=180)
    except JDCliError as e:
        # JDCliError wraps the CalledProcessError that carries the real exit code.
        cause = e.__cause__
        exit_code = cause.returncode if isinstance(cause, subprocess.CalledProcessError) else None
        return _CommandFailure(graceful="Traceback" not in str(e), exit_code=exit_code)
    return _CommandFailure(graceful=False, exit_code=0)


def _flag_present(e2e_deployment: EndToEndDeployment, path: str) -> bool:
    """Return True if ``path`` exists in the Jupyter home volume."""
    try:
        e2e_deployment.cli.run_exec_with_retry(["jupyter-deploy", "server", "exec", "--", "stat", path])
    except JDCliError:
        return False
    return True


def test_host_stop(host_cycle: HostCycleObservations) -> None:
    """`jd host stop` leaves the instance stopped and the SSM agent not connected."""
    assert host_cycle.stopped_host_status == "stopped", (
        f"Expected host status 'stopped', got '{host_cycle.stopped_host_status}'"
    )
    assert host_cycle.stopped_connection_status == "notconnected", (
        f"Expected 'notconnected', got '{host_cycle.stopped_connection_status}'"
    )


def test_host_start(host_cycle: HostCycleObservations) -> None:
    """`jd host start` brings the instance back to running with the SSM agent connected."""
    assert host_cycle.running_host_status == "running", (
        f"Expected host status 'running', got '{host_cycle.running_host_status}'"
    )
    assert host_cycle.running_connection_status == "connected", (
        f"Expected 'connected', got '{host_cycle.running_connection_status}'"
    )
    # A stop/start is not a replacement: the same instance must come back, or the data volume
    # and cert assertions below would be testing a different machine entirely.
    assert host_cycle.instance_id_after == host_cycle.instance_id_before, (
        f"The instance was replaced by a stop/start: {host_cycle.instance_id_before} -> {host_cycle.instance_id_after}"
    )


def test_host_stopped_fails_connect_info_gracefully(host_cycle: HostCycleObservations) -> None:
    """`jd proxy connect-info` against a stopped host fails cleanly — no public IP to resolve.

    A stopped instance has no public IP, so the bundle cannot be assembled. The error has to
    point at the host rather than surface as a traceback: this is the state a user lands in
    after any overnight stop, and "start the host" is the whole fix.
    """
    assert host_cycle.stopped_connect_info.graceful, (
        "`jd proxy connect-info` did not fail gracefully against a stopped host"
    )


def test_host_stopped_connect_info_reports_a_retryable_failure(host_cycle: HostCycleObservations) -> None:
    """A stopped host is reported to the proxy as *retryable* (exit 75), not permanent.

    `connect-info`'s exit code is a verdict the running proxy acts on: 75 (EX_TEMPFAIL) means
    "keep serving on the last-good credential and try again", anything else non-zero means "give
    up and shut down". A stopped host is recoverable — `jd host start` fixes it and the proxy
    self-heals on its next refresh, with the idle timeout bounding it if nobody ever does — so it
    must not be the code that kills a proxy.

    This pins a classification that is otherwise implicit: a stopped host raises
    ``IncompatibleHostStateError``, which is simply absent from the CLI's permanent list, and the
    fail-safe default sends everything unlisted to 75. Without this test, adding that class to the
    permanent list (or reclassifying by accident) would silently start killing proxies whenever a
    host stops, and no unit test would notice — they all use synthetic exceptions.
    """
    assert host_cycle.stopped_connect_info.exit_code == RETRYABLE_EXIT_CODE, (
        f"Expected exit {RETRYABLE_EXIT_CODE} (retryable) from `jd proxy connect-info` against a "
        f"stopped host, got {host_cycle.stopped_connect_info.exit_code}"
    )


def test_host_stopped_fails_open_gracefully(host_cycle: HostCycleObservations) -> None:
    """`jd open` against a stopped host fails with an actionable error and never auto-starts it.

    Starting an instance is a billable side effect, so `jd open` must not do it implicitly —
    the user asked to open the app, not to provision. It reports the problem and stops.
    """
    assert host_cycle.stopped_open_failed, "`jd open` did not fail gracefully against a stopped host"
    assert host_cycle.stopped_host_status_after_open == "stopped", (
        "`jd open` started the host implicitly: expected it to still be 'stopped' after the failed "
        f"open, got '{host_cycle.stopped_host_status_after_open}'"
    )


def test_home_volume_persists_across_host_restart(host_cycle: HostCycleObservations) -> None:
    """A file written to the home volume survives a full host stop/start.

    The data volume is a separate EBS volume that reattaches and remounts over
    ``/home/jovyan`` at boot. If that ever regressed, every stop/start would silently reset the
    user's home directory — the single most destructive failure this template can have.
    """
    assert host_cycle.flag_survived, (
        f"{_PERSISTENCE_FLAG} did not survive the host restart; the data volume did not remount"
    )


def test_cert_pin_stable_across_host_restart(host_cycle: HostCycleObservations) -> None:
    """The instance serves the same cert after a restart, and the pin still validates.

    The key and cert live on the persisted data volume, so a restart must not regenerate them.
    If it did, every client's pinned PEM (and the copy published to SSM) would go stale and the
    app would become unreachable through the proxy until the next `jd up` — while the instance
    itself looked perfectly healthy.
    """
    assert host_cycle.cert_fingerprint_after == host_cycle.cert_fingerprint_before, (
        "The instance regenerated its cert across a restart; every pinned client would now fail"
    )
    assert host_cycle.pinned_status_after == 200, (
        f"The pinned connection did not succeed after the restart (status {host_cycle.pinned_status_after})"
    )
