#!/usr/bin/env python3
"""Regex-based, in-place version edits shared by the version bump scripts.

Every helper here rewrites one line and leaves the rest of the file byte-identical.
That is the point: parsing a file and dumping it back drops comments, and the
version files carry comments that explain non-obvious pins and declarations. A
`yaml.safe_load`/`yaml.dump` round-trip of a template manifest, or a
`tomllib`/`tomli_w` round-trip of a pyproject, silently deletes all of them.
"""

import re
from pathlib import Path

# `version = "..."` at the start of a line: the project/workspace version of a
# pyproject.toml, a pixi.toml, or either rendered from a .tftpl. Dependency pins
# are quoted list items, so they never sit at column 0 and cannot match.
TOML_VERSION_PATTERN = r'^(version\s*=\s*)["\'][^"\']+["\']'

# The first INDENTED `version:` of a template manifest, i.e. the one under `template:`.
# `schema_version:` at column 0 is a different key and is left alone.
YAML_VERSION_PATTERN = r"^(\s+version:\s*).+$"

# A Helm Chart.yaml `version:`, which sits at column 0.
CHART_VERSION_PATTERN = r"^(version:\s*).+$"


def _substitute(file_path: Path, pattern: str, replacement: str) -> None:
    content = file_path.read_text()
    updated_content = re.sub(pattern, replacement, content, count=1, flags=re.MULTILINE)

    if content == updated_content:
        print(f"! Warning: No version pattern found in {file_path}")
    else:
        file_path.write_text(updated_content)
        print(f"✓ Updated version in {file_path}")


def set_toml_version(file_path: Path, new_version: str) -> None:
    """Update the version of a pyproject.toml, pixi.toml, or their .tftpl counterparts.

    Falls back to `<file_path>.tftpl` when the plain path does not exist, so callers
    can name the rendered file and stay correct whether or not it is templated.
    """
    if not file_path.exists():
        tftpl_path = Path(f"{file_path}.tftpl")
        if not tftpl_path.exists():
            print(f"! Warning: File not found: {file_path}")
            return
        file_path = tftpl_path

    _substitute(file_path, TOML_VERSION_PATTERN, rf'\g<1>"{new_version}"')


def set_manifest_version(file_path: Path, new_version: str) -> None:
    """Update `template.version` of a template manifest.yaml."""
    _substitute(file_path, YAML_VERSION_PATTERN, rf"\g<1>{new_version}")


def set_chart_version(file_path: Path, new_version: str) -> None:
    """Update `version` of a Helm Chart.yaml."""
    _substitute(file_path, CHART_VERSION_PATTERN, rf"\g<1>{new_version}")


def set_init_version(file_path: Path, new_version: str) -> None:
    """Update `__version__` of a package __init__.py."""
    _substitute(file_path, r'(__version__\s*=\s*)["\'][^"\']+["\']', rf'\g<1>"{new_version}"')


def set_tf_template_version(file_path: Path, new_version: str) -> None:
    """Update the `template_version` local of an engine main.tf."""
    _substitute(file_path, r'(template_version\s*=\s*)["\'][^"\']+["\']', rf'\g<1>"{new_version}"')


def set_app_image_name_version(file_path: Path, app_name: str, new_version: str) -> None:
    """Update the `<app_name>-v<version>` default image name in a presets tfvars or variables.yaml."""
    _substitute(file_path, rf"({re.escape(app_name)}-v)[^\"'\s]+", rf"\g<1>{new_version}")


def pep440_to_semver(version: str) -> str:
    """Convert a PEP 440 pre-release to SemVer (e.g. '0.1.0rc1' -> '0.1.0-rc.1')."""
    match = re.match(r"^(\d+\.\d+\.\d+)(rc|a|b)(\d+)$", version)
    if match:
        base, pre_type, pre_num = match.groups()
        return f"{base}-{pre_type}.{pre_num}"
    return version
