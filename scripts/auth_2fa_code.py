"""Generate a TOTP code for the GitHub bot account.

Reads the TOTP secret ARN from the CI project outputs,
fetches the seed from Secrets Manager, and prints a 6-digit
TOTP code via oathtool.

Usage: uv run python scripts/auth_2fa_code.py <ci-dir>
"""

from __future__ import annotations

import subprocess
import sys

from ci_helpers import fetch_secret_value, jd_output


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: uv run python scripts/auth_2fa_code.py <ci-dir>", file=sys.stderr)
        sys.exit(1)

    ci_dir = sys.argv[1]

    arn = jd_output("github_bot_account_totp_secret_secret_arn", ci_dir)
    secret = fetch_secret_value(arn)

    result = subprocess.run(
        ["oathtool", "-b", "--totp", secret],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Error: oathtool failed: {result.stderr.strip()}", file=sys.stderr)
        print("Install oathtool: brew install oath-toolkit (macOS) or apt install oathtool (Linux)", file=sys.stderr)
        sys.exit(1)

    print(result.stdout.strip())


if __name__ == "__main__":
    main()
