"""Retrieve GitHub bot account secrets from the CI project.

Supports two modes:
- password: prints the bot account password
- totp: generates a 2FA code via oathtool

Usage: uv run python scripts/auth_bot_secret.py <ci-dir> <password|totp>
"""

from __future__ import annotations

import subprocess
import sys

from ci_helpers import fetch_secret_value, jd_output

MODES = {
    "password": "github_bot_account_password_secret_arn",
    "totp": "github_bot_account_totp_secret_secret_arn",
}


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[2] not in MODES:
        print(f"Usage: uv run python scripts/auth_bot_secret.py <ci-dir> <{'|'.join(MODES)}>", file=sys.stderr)
        sys.exit(1)

    ci_dir = sys.argv[1]
    mode = sys.argv[2]

    arn = jd_output(MODES[mode], ci_dir)
    secret = fetch_secret_value(arn)

    if mode == "totp":
        result = subprocess.run(
            ["oathtool", "-b", "--totp", secret],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Error: oathtool failed: {result.stderr.strip()}", file=sys.stderr)
            print(
                "Install oathtool: brew install oath-toolkit (macOS) or apt install oathtool (Linux)", file=sys.stderr
            )
            sys.exit(1)
        print(result.stdout.strip())
    else:
        print(secret)


if __name__ == "__main__":
    main()
