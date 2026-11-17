"""Helpers for the mutating modules that rewrite template variables for a window of cases."""

from typing import Any

from pytest_jupyter_deploy.deployment import EndToEndDeployment


def pools_offering(pools: list[dict[str, str]], config_name: str) -> list[dict[str, str]]:
    """The pool entries with the first CPU pool also offering config_name.

    A config renders a card only where a pool lists it in its templates key.
    """
    offering = [dict(pool) for pool in pools]
    cpu_pool = next(pool for pool in offering if not pool.get("accelerator"))
    offered = [name for name in cpu_pool.get("templates", "").split(",") if name]
    cpu_pool["templates"] = ",".join(dict.fromkeys([*offered, config_name]))
    return offering


def snapshot_overrides(e2e_deployment: EndToEndDeployment, keys: list[str]) -> dict[str, Any]:
    """The current override of each key, None for an unset one."""
    return {key: e2e_deployment.read_override_value(key) for key in keys}


def restore_overrides(e2e_deployment: EndToEndDeployment, snapshot: dict[str, Any]) -> None:
    """Write the snapshotted overrides back, resetting the keys that were unset, then jd config + jd up."""
    reset_args: list[str] = []
    for key, value in snapshot.items():
        if value is None:
            reset_args += ["--reset-variable", key]
        else:
            e2e_deployment.update_override_value(key, value)
    e2e_deployment.ensure_deployed_with(reset_args)
