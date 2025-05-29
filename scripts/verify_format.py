# /// script
# dependencies = [
#   "rich",
# ]
# ///

import argparse
import os
import subprocess
import sys

from rich.console import Console


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify code formatting with ruff")
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to check (default: current directory)",
    )
    args = parser.parse_args()

    console = Console()
    directory = args.directory

    if not os.path.isdir(directory):
        console.print(
            f"Error: Directory '{directory}' does not exist", style="bold red"
        )
        return 1

    format_result = subprocess.run(
        ["uv", "run", "ruff", "format", "--diff", directory], capture_output=True
    )

    if format_result.stdout:
        console.print(
            f"Ruff found formatting issues in '{directory}'. Please run `uv run ruff format {directory}` to fix them.",
            style="bold red",
        )
        raise RuntimeError()

    console.print(
        f"All good, confirmed that `uv run ruff format` would not make any change in '{directory}'.",
        style="bold green",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
