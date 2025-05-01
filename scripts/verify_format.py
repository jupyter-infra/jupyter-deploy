# /// script
# dependencies = [
#   "rich",
# ]
# ///

import subprocess

from rich.console import Console


def main() -> int:
    console = Console()

    # Run format and capture output
    format_result = subprocess.run(["uv", "run", "ruff", "format", "--diff"], capture_output=True)

    if format_result.stdout:
        console.print("Ruff format would make changes, run `uv run ruff format` first.", style="bold red")
        raise RuntimeError()

    console.print("All good, confirmed that `uv run ruff format` would not make any change.", style="bold green")
    return 0


if __name__ == "__main__":
    main()
