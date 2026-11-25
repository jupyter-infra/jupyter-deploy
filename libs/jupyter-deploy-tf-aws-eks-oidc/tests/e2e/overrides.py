"""Helpers for the mutating modules that rewrite template variables for a window of cases."""


def with_names(csv: str, names: list[str]) -> str:
    """The comma-separated list csv with names appended once each, order kept."""
    return ",".join(dict.fromkeys([*[name for name in csv.split(",") if name], *names]))


def pools_offering(pools: list[dict[str, str]], config_name: str) -> list[dict[str, str]]:
    """The pool entries with the first CPU pool also offering config_name.

    A config renders a card only where a pool lists it in its templates key.
    """
    offering = [dict(pool) for pool in pools]
    cpu_pool = next(pool for pool in offering if not pool.get("accelerator"))
    cpu_pool["templates"] = with_names(cpu_pool.get("templates", ""), [config_name])
    return offering
