"""CI credential fetching from mounted CI project directory."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable


def _run(args: list[str]) -> str:
    """Run a command and return stripped stdout."""
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _cmd(tool: str) -> list[str]:
    """Return command prefix: use tool directly if on PATH, else via `uv run`."""
    if shutil.which(tool):
        return [tool]
    return ["uv", "run", tool]


def fetch_ci_credentials(ci_dir: str) -> tuple[str, str, Callable[[], str]]:
    """Fetch bot credentials from the CI project directory.

    Calls the underlying CLI commands directly (no `just` dependency).
    The TOTP function is a closure called just-in-time (30s TOTP window).

    Args:
        ci_dir: Path to the CI infrastructure project directory

    Returns:
        Tuple of (email, password, totp_fn) where totp_fn generates fresh TOTP codes
    """
    jd = _cmd("jd")
    python = _cmd("python")
    email = _run([*jd, "show", "-v", "github_bot_account_email", "--text", "--path", ci_dir])
    password = _run([*python, "scripts/auth_bot_secret.py", ci_dir, "password"])

    def totp_fn() -> str:
        return _run([*_cmd("python"), "scripts/auth_bot_secret.py", ci_dir, "totp"])

    return email, password, totp_fn
