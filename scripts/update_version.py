#!/usr/bin/env python3
"""Bump the version of a jupyter-deploy release target.

Usage:
    python scripts/update_version.py <target> <bump-or-version>

    <target>           cli | plugin | base-template | eks-oidc-template
    <bump-or-version>  patch | minor | major | an explicit version (e.g. 0.1.4, 0.1.0rc1)

Dispatch:
    - cli               bumps BOTH the root and CLI pyproject.toml (they move in lockstep)
    - plugin            bumps the plugin pyproject.toml
    - base-template     delegates to scripts/upgrade_base_template_version.py
    - eks-oidc-template delegates to scripts/upgrade_eks_oidc_template_version.py

For a `patch|minor|major` bump the new version is computed from the target's current
`pyproject.toml` version, using only its X.Y.Z core (any pre-release suffix is dropped).
Pass an explicit version to cut a pre-release (e.g. `0.1.0rc1`).

This script does NOT run `uv lock` — the `just update-version` recipe does that.
"""

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# canonical pyproject.toml whose version is the source of truth for each target
TARGET_PYPROJECT: dict[str, Path] = {
    "cli": REPO_ROOT / "libs" / "jupyter-deploy" / "pyproject.toml",
    "plugin": REPO_ROOT / "libs" / "pytest-jupyter-deploy" / "pyproject.toml",
    "base-template": REPO_ROOT / "libs" / "jupyter-deploy-tf-aws-ec2-base" / "pyproject.toml",
    "eks-oidc-template": REPO_ROOT / "libs" / "jupyter-deploy-tf-aws-eks-oidc" / "pyproject.toml",
}

# template targets delegate their multi-file bump to a dedicated script
TEMPLATE_SCRIPTS: dict[str, Path] = {
    "base-template": REPO_ROOT / "scripts" / "upgrade_base_template_version.py",
    "eks-oidc-template": REPO_ROOT / "scripts" / "upgrade_eks_oidc_template_version.py",
}

BUMP_KEYWORDS = ("patch", "minor", "major")


def read_pyproject_version(file_path: Path) -> str:
    with open(file_path, "rb") as f:
        data = tomllib.load(f)
    return str(data["project"]["version"])


def compute_bumped_version(current: str, bump: str) -> str:
    """Bump the X.Y.Z core of `current` (dropping any pre-release suffix)."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", current)
    if not match:
        print(f"Error: cannot parse a X.Y.Z core from current version '{current}'")
        sys.exit(1)
    major, minor, patch = (int(part) for part in match.groups())

    if bump == "major":
        major, minor, patch = major + 1, 0, 0
    elif bump == "minor":
        minor, patch = minor + 1, 0
    else:  # patch
        patch += 1
    return f"{major}.{minor}.{patch}"


def set_pyproject_version(file_path: Path, new_version: str) -> None:
    """Update only the project version line, preserving formatting."""
    content = file_path.read_text()
    updated = re.sub(
        r'^(version\s*=\s*)["\'][^"\']+["\']',
        rf'\g<1>"{new_version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if content == updated:
        print(f"! Warning: no version line updated in {file_path}")
    else:
        file_path.write_text(updated)
        print(f"✓ Updated version in {file_path.relative_to(REPO_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bump the version of a release target.")
    parser.add_argument("target", choices=sorted(TARGET_PYPROJECT))
    parser.add_argument(
        "bump_or_version",
        help="patch | minor | major, or an explicit version (e.g. 0.1.4, 0.1.0rc1)",
    )
    args = parser.parse_args()

    current = read_pyproject_version(TARGET_PYPROJECT[args.target])

    if args.bump_or_version in BUMP_KEYWORDS:
        new_version = compute_bumped_version(current, args.bump_or_version)
    else:
        new_version = args.bump_or_version

    print(f"{args.target}: {current} -> {new_version}\n")

    if args.target in TEMPLATE_SCRIPTS:
        # delegate to the template's dedicated multi-file bump script
        subprocess.run(
            [sys.executable, str(TEMPLATE_SCRIPTS[args.target]), new_version],
            check=True,
        )
    elif args.target == "cli":
        # root and CLI versions move in lockstep
        set_pyproject_version(REPO_ROOT / "pyproject.toml", new_version)
        set_pyproject_version(TARGET_PYPROJECT["cli"], new_version)
    else:  # plugin
        set_pyproject_version(TARGET_PYPROJECT["plugin"], new_version)

    print("\nRun `uv lock` to update the lockfile (the just recipe does this).")


if __name__ == "__main__":
    main()
