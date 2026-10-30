"""Unit tests for the network_probe helper's pod-naming and probe flow."""

import subprocess
from unittest.mock import patch

import pytest

from pytest_jupyter_deploy.workspaces import network_probe


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def test_unique_pod_name_is_prefixed_and_distinct() -> None:
    """Each generated name keeps the prefix but gets a distinct random suffix."""
    names = {network_probe._unique_pod_name("netpol-probe") for _ in range(100)}
    assert len(names) == 100
    for name in names:
        assert name.startswith("netpol-probe-")
        assert name != "netpol-probe"


def test_probe_service_runs_pod_under_unique_name() -> None:
    """probe_service creates and deletes a pod whose name is prefix + random suffix."""
    create = _completed(returncode=0)
    with (
        patch.object(network_probe, "_run", return_value=create) as run_mock,
        patch.object(network_probe, "_wait_for_terminated_exit_code", return_value=0) as wait_mock,
        patch.object(network_probe, "delete_probe_pod") as delete_mock,
    ):
        allowed = network_probe.probe_service("svc.host", 8888, from_namespace="ns")

    assert allowed is True
    run_cmd = run_mock.call_args.args[0]
    pod_name = run_cmd[run_cmd.index("run") + 1]
    assert pod_name.startswith("netpol-probe-")
    assert pod_name != "netpol-probe"
    # The same unique name is waited on and cleaned up.
    wait_mock.assert_called_once()
    assert wait_mock.call_args.args[0] == pod_name
    delete_mock.assert_called_once_with(pod_name, "ns")


def test_probe_service_uses_custom_prefix() -> None:
    """A caller-supplied prefix is honored, with a unique suffix still appended."""
    with (
        patch.object(network_probe, "_run", return_value=_completed(returncode=0)) as run_mock,
        patch.object(network_probe, "_wait_for_terminated_exit_code", return_value=0),
        patch.object(network_probe, "delete_probe_pod"),
    ):
        network_probe.probe_service("svc.host", 8888, from_namespace="ns", pod_name_prefix="custom")

    run_cmd = run_mock.call_args.args[0]
    pod_name = run_cmd[run_cmd.index("run") + 1]
    assert pod_name.startswith("custom-")


def test_probe_service_generates_fresh_name_each_call() -> None:
    """Two sequential probes never reuse a pod name, even with the same prefix."""
    seen: list[str] = []

    def capture(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        if "run" in cmd:
            seen.append(cmd[cmd.index("run") + 1])
        return _completed(returncode=0)

    with (
        patch.object(network_probe, "_run", side_effect=capture),
        patch.object(network_probe, "_wait_for_terminated_exit_code", return_value=0),
        patch.object(network_probe, "delete_probe_pod"),
    ):
        network_probe.probe_service("svc.host", 8888, from_namespace="ns")
        network_probe.probe_service("svc.host", 8888, from_namespace="ns")

    assert len(seen) == 2
    assert seen[0] != seen[1]


def test_probe_service_allowed_retries_with_distinct_names() -> None:
    """Each retry attempt probes under a fresh, distinct pod name."""
    seen: list[str] = []

    def capture(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        if "run" in cmd:
            seen.append(cmd[cmd.index("run") + 1])
        return _completed(returncode=0)

    # Force every probe to read as denied (curl timeout exit 28) so all attempts run.
    with (
        patch.object(network_probe, "_run", side_effect=capture),
        patch.object(network_probe, "_wait_for_terminated_exit_code", return_value=network_probe._CURL_TIMEOUT_EXIT),
        patch.object(network_probe, "delete_probe_pod"),
    ):
        allowed = network_probe.probe_service_allowed("svc.host", 8888, from_namespace="ns", attempts=3)

    assert allowed is False
    assert len(seen) == 3
    assert len(set(seen)) == 3


def test_probe_service_maps_curl_exit_codes() -> None:
    """0 is an allow, 28 a deny; anything else, e.g. an empty reply (52) or a DNS failure (6), raises."""
    for exit_code, expected in [(0, True), (28, False)]:
        with (
            patch.object(network_probe, "_run", return_value=_completed(returncode=0)),
            patch.object(network_probe, "_wait_for_terminated_exit_code", return_value=exit_code),
            patch.object(network_probe, "delete_probe_pod"),
        ):
            assert network_probe.probe_service("svc.host", 8443, from_namespace="ns") is expected, exit_code

    for exit_code in (6, 52):
        with (
            patch.object(network_probe, "_run", return_value=_completed(returncode=0)),
            patch.object(network_probe, "_wait_for_terminated_exit_code", return_value=exit_code),
            patch.object(network_probe, "delete_probe_pod"),
            pytest.raises(RuntimeError, match="ambiguously"),
        ):
            network_probe.probe_service("svc.host", 8443, from_namespace="ns")


def test_probe_service_https_skips_verification() -> None:
    """scheme="https" requests an https:// URL with --insecure; the http default sends neither."""
    for scheme, url, insecure in [("https", "https://svc.host:8443/", True), ("http", "http://svc.host:8443/", False)]:
        with (
            patch.object(network_probe, "_run", return_value=_completed(returncode=0)) as run_mock,
            patch.object(network_probe, "_wait_for_terminated_exit_code", return_value=0),
            patch.object(network_probe, "delete_probe_pod"),
        ):
            network_probe.probe_service("svc.host", 8443, from_namespace="ns", scheme=scheme)

        run_cmd = run_mock.call_args_list[0].args[0]
        assert run_cmd[-1] == url
        assert ("--insecure" in run_cmd) is insecure


def test_probe_service_rejects_unknown_scheme() -> None:
    """A scheme other than http/https raises before any pod is created."""
    with patch.object(network_probe, "_run") as run_mock, pytest.raises(ValueError, match="unsupported probe scheme"):
        network_probe.probe_service("svc.host", 8443, from_namespace="ns", scheme="grpc")
    run_mock.assert_not_called()
