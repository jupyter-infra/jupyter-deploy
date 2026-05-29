#!/usr/bin/env python3
"""Generate CLI reference docs from Typer app.

Generates raw markdown via typer's built-in docs utility, then splits it
into per-command pages organized by group for the docs site Reference section.

Usage: python hack/docs/generate-cli-ref.py docs/source/reference
"""

import re
import sys
from pathlib import Path
from typing import Any

import typer
import typer.main
from jupyter_deploy.cli.app import runner
from typer.cli import get_docs_for_click

COMMAND_GROUPS = {
    "project": {
        "title": "Project Commands",
        "description": (
            "Project commands manage the full lifecycle of a deployment project:"
            " initialization, configuration, provisioning, teardown, and inspection."
        ),
        "commands": ["init", "config", "up", "down", "open", "show", "health", "history"],
    },
    "resource": {
        "title": "Resource Commands",
        "description": (
            "Resource commands interact with the infrastructure resources backing your"
            " deployment: application servers, compute hosts, Kubernetes clusters,"
            " and platform components."
        ),
        "commands": ["server", "host", "cluster", "component"],
    },
    "access": {
        "title": "Access Control Commands",
        "description": (
            "Access control commands manage who can reach your deployed applications."
            " Grant or revoke permissions at the user, team, or organization level."
        ),
        "commands": ["users", "teams", "organization"],
    },
    "store": {
        "title": "Store Commands",
        "description": (
            "Store commands manage projects persisted in a remote store."
            " List, inspect, or restore projects that have been saved."
        ),
        "commands": ["projects"],
    },
    "general": {
        "title": "General",
        "description": "",
        "commands": [],
    },
}


def generate_raw_docs() -> str:
    click_obj = typer.main.get_command(runner.app)
    ctx = typer.Context(click_obj, info_name="jd")
    return get_docs_for_click(obj=click_obj, ctx=ctx, name="jd", title=None)


def split_into_sections(raw: str) -> dict[str, str]:
    """Split raw docs into sections keyed by command name.

    The preamble (top-level jd usage/options) is stored under key "__general__".
    """
    sections: dict[str, str] = {}
    current_cmd: str | None = None
    current_lines: list[str] = []
    preamble_lines: list[str] = []

    for line in raw.split("\n"):
        match = re.match(r"^## `jd (\w+)`", line)
        if match:
            if current_cmd is not None:
                sections[current_cmd] = "\n".join(current_lines)
            current_cmd = match.group(1)
            current_lines = [line]
        elif current_cmd is not None:
            current_lines.append(line)
        else:
            if not line.startswith("# "):
                preamble_lines.append(line)

    if current_cmd is not None:
        sections[current_cmd] = "\n".join(current_lines)

    sections["__general__"] = "\n".join(preamble_lines).strip()

    return sections


def strip_jd_prefix(line: str) -> str:
    """Remove 'jd ' from command headings: `jd foo` -> `foo`."""
    return re.sub(r"`jd ", "`", line)


def reformat_section(section: str) -> str:
    """Promote headings and strip jd prefix from command names."""
    lines = section.split("\n")
    result = []
    for line in lines:
        if line.startswith("### "):
            result.append(strip_jd_prefix("##" + line[3:]))
        elif line.startswith("## "):
            result.append(strip_jd_prefix("#" + line[2:]))
        else:
            result.append(line)
    return "\n".join(result)


def build_command_page(cmd: str, sections: dict[str, str]) -> str:
    """Build a single command page."""
    if cmd not in sections:
        return ""
    return reformat_section(sections[cmd]).strip() + "\n"


def get_command_help_map() -> dict[str, str]:
    """Get short help strings for all top-level commands."""
    click_obj: Any = typer.main.get_command(runner.app)
    help_map: dict[str, str] = {}
    for name in click_obj.list_commands(None):
        cmd = click_obj.get_command(None, name)
        if cmd:
            help_map[name] = cmd.get_short_help_str(limit=120)
    return help_map


def build_group_index(group_key: str, group_info: dict, help_map: dict[str, str]) -> str:
    """Build a group index page with description, table, and toctree."""
    lines = [f"# {group_info['title']}\n"]
    lines.append(f"{group_info['description']}\n")
    lines.append("| Command | Description |")
    lines.append("|---------|-------------|")
    for cmd in group_info["commands"]:
        desc = help_map.get(cmd, "")
        lines.append(f"| [{cmd}]({group_key}/{cmd}) | {desc} |")
    lines.append("")
    lines.append("```{toctree}")
    lines.append(":hidden:")
    lines.append("")
    for cmd in group_info["commands"]:
        lines.append(f"{group_key}/{cmd}")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def build_general_page(sections: dict[str, str]) -> str:
    """Build the General page with top-level jd usage/options."""
    lines = ["# General\n"]
    lines.append(sections.get("__general__", ""))
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_cli_ref.py <output-dir>", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(sys.argv[1])
    output_dir.mkdir(parents=True, exist_ok=True)

    raw = generate_raw_docs()
    sections = split_into_sections(raw)
    help_map = get_command_help_map()

    for group_key, group_info in COMMAND_GROUPS.items():
        if group_key == "general":
            out_path = output_dir / "overview.md"
            out_path.write_text(build_general_page(sections))
            print(f"  {out_path}")
            continue

        group_dir = output_dir / group_key
        group_dir.mkdir(exist_ok=True)

        for cmd in group_info["commands"]:
            page = build_command_page(cmd, sections)
            if page:
                cmd_path = group_dir / f"{cmd}.md"
                cmd_path.write_text(page)
                print(f"  {cmd_path}")

        index_path = output_dir / f"{group_key}-commands.md"
        index_path.write_text(build_group_index(group_key, group_info, help_map))
        print(f"  {index_path}")


if __name__ == "__main__":
    main()
