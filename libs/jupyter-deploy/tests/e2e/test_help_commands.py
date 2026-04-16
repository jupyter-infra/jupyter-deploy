"""CLI help smoke tests — validate every subcommand responds to --help."""

import re
import subprocess

import pytest

_HELP_COMMANDS: list[list[str]] = [
    ["jd", "--help"],
    ["jd", "init", "--help"],
    ["jd", "config", "--help"],
    ["jd", "up", "--help"],
    ["jd", "down", "--help"],
    ["jd", "open", "--help"],
    ["jd", "show", "--help"],
    ["jd", "server", "--help"],
    ["jd", "users", "--help"],
    ["jd", "teams", "--help"],
    ["jd", "organization", "--help"],
    ["jd", "host", "--help"],
    ["jd", "history", "--help"],
    ["jd", "projects", "--help"],
]


_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


@pytest.mark.parametrize("flag", ["--version", "-V"])
def test_version(flag: str) -> None:
    """jd --version / -V prints a semver string and exits 0."""
    result = subprocess.run(["jd", flag], capture_output=True, text=True)
    assert result.returncode == 0, f"jd {flag} failed: {result.stderr}"
    assert _SEMVER_PATTERN.match(result.stdout.strip()), f"Expected <major>.<minor>.<patch>, got: {result.stdout!r}"


@pytest.mark.parametrize("cmd", _HELP_COMMANDS, ids=[" ".join(c) for c in _HELP_COMMANDS])
def test_help_commands(cmd: list[str]) -> None:
    """Every subcommand responds to --help with exit code 0."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"{' '.join(cmd)} failed: {result.stderr}"
