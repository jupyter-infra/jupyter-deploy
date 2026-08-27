"""Parsing utilities for the proxy status file.

``status.json`` is a versioned wire contract published by ``jupyter-deploy-client-proxy``
under each proxy instance's log dir. Because instance directories persist across proxy
upgrades, a project's history can hold files written by older proxy versions — so reads go
through a per-version converter keyed on the file's ``schema_version``.

These are pure functions (no I/O beyond reading the given file); the manager owns discovery
of instance directories and process orchestration.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from jupyter_deploy import cmd_utils, fs_utils
from jupyter_deploy.handlers.payloads import ProxyStatus

# Status file the running proxy publishes under its --log-dir (name owned by the proxy).
PROXY_STATUS_FILE_NAME = "status.json"

# Published states the proxy uses for a torn-down / crashed instance; these are "not running"
# even if the recorded PID happens to still be alive.
_TERMINAL_STATES = ("stopped", "failed")


def _status_from_v1(payload: dict, instance_dir: Path) -> ProxyStatus:
    """Convert a v1 status.json payload ({state, pid, port, expires_at}) to a ProxyStatus."""
    state = str(payload.get("state", "unknown"))
    pid = int(payload["pid"]) if payload.get("pid") else 0
    alive = cmd_utils.is_pid_alive(pid)
    return ProxyStatus(
        state=state,
        pid=pid,
        alive=alive,
        port=payload.get("port"),
        expires_at=payload.get("expires_at"),
        running=alive and state not in _TERMINAL_STATES,
        started_at=instance_dir.name,
        log_dir=str(instance_dir),
        process_created_at=payload.get("process_created_at"),
    )


# status.json schema versions this CLI can read. Add an entry when the proxy's payload shape
# changes incompatibly; the newest is the fallback for unknown (future) versions.
_STATUS_CONVERTERS: dict[int, Callable[[dict, Path], ProxyStatus]] = {1: _status_from_v1}
_LATEST_STATUS_CONVERTER = _status_from_v1


def read_instance_status(instance_dir: Path) -> ProxyStatus | None:
    """Read + parse one proxy instance's status file, or None if unreadable.

    Missing/corrupt/non-object status files yield None so a single bad directory never breaks
    a scan (rather than raising). The ``schema_version`` selects the converter; files
    predating the field are treated as v1, and an unknown (future) version falls back to the
    latest known converter since the core liveness fields have been stable.
    """
    status_path = instance_dir / PROXY_STATUS_FILE_NAME
    try:
        # read_short_file caps the size (RuntimeError) — a status file is tiny by contract, so
        # an oversize one is corrupt. A missing file is the routine "stopped" signal.
        payload = json.loads(fs_utils.read_short_file(status_path))
    except (FileNotFoundError, RuntimeError, json.JSONDecodeError):
        # Absent (routine "stopped"), oversize, or corrupt JSON → skip this dir.
        # Other OSErrors (PermissionError, IO) propagate on purpose: a present-but-unreadable
        # status file is a real fault, not "no proxy" — masking it risks a duplicate spawn.
        return None
    if not isinstance(payload, dict):
        return None

    version = payload.get("schema_version", 1)
    convert = _STATUS_CONVERTERS.get(version, _LATEST_STATUS_CONVERTER)
    return convert(payload, instance_dir)
