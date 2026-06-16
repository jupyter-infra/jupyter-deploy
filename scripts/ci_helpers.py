"""Shared helpers for CI scripts.

Provides boto3-based AWS secret/parameter fetching and jd CLI output reading.
"""

from __future__ import annotations

import subprocess
import sys

import boto3
from mypy_boto3_secretsmanager import SecretsManagerClient
from mypy_boto3_ssm import SSMClient

# Backstop timeout for any single `jd` invocation. The canary job cap is 30
# minutes; a stuck `jd` should fail well before that with a diagnostic rather
# than silently eating the whole job budget.
JD_TIMEOUT_SECONDS = 600


def run_jd(
    jd_args: list[str],
    cwd: str | None = None,
    capture: bool = False,
    timeout: int = JD_TIMEOUT_SECONDS,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a `jd` CLI command with CI-safe defaults.

    Closes stdin so a no-TTY interactive prompt fails fast instead of hanging,
    enforces a timeout backstop, and surfaces stderr on failure or timeout.

    With check=False a non-zero exit is returned to the caller instead of
    terminating the process, so optional steps can fail without aborting.
    """
    cmd = ["uv", "run", "jd", *jd_args]
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            capture_output=capture,
            text=True,
            check=check,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        print(f"Error: `jd {' '.join(jd_args)}` timed out after {timeout}s", file=sys.stderr)
        if e.stderr:
            print(e.stderr if isinstance(e.stderr, str) else e.stderr.decode(), file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error: `jd {' '.join(jd_args)}` failed with exit code {e.returncode}", file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        sys.exit(1)


def arn_region(arn: str) -> str:
    """Extract the AWS region (field 4) from an ARN."""
    parts = arn.split(":")
    if len(parts) < 4:
        print(f"Error: Cannot extract region from ARN: {arn}", file=sys.stderr)
        sys.exit(1)
    return parts[3]


def jd_output(output_name: str, ci_dir: str) -> str:
    """Read a jd output value as plain text."""
    result = run_jd(["show", "-o", output_name, "--text", "-p", ci_dir], capture=True)
    return result.stdout.strip().replace("\n", "")


def fetch_secret_value(arn: str) -> str:
    """Fetch a secret string from AWS Secrets Manager."""
    region = arn_region(arn)
    client: SecretsManagerClient = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=arn)
    return response["SecretString"]


def fetch_ssm_value(arn: str) -> str:
    """Fetch a parameter value from AWS SSM Parameter Store."""
    region = arn_region(arn)
    client: SSMClient = boto3.client("ssm", region_name=region)
    response = client.get_parameter(Name=arn, WithDecryption=True)
    return response["Parameter"]["Value"]


def fetch_value(arn: str) -> str:
    """Fetch a value from AWS, auto-detecting Secrets Manager vs SSM from the ARN."""
    if ":secretsmanager:" in arn:
        return fetch_secret_value(arn)
    if ":ssm:" in arn:
        return fetch_ssm_value(arn)
    print(f"Error: Unrecognized ARN format: {arn}", file=sys.stderr)
    sys.exit(1)


def put_secret_value(arn: str, value: str) -> None:
    """Store a secret string in AWS Secrets Manager."""
    region = arn_region(arn)
    client: SecretsManagerClient = boto3.client("secretsmanager", region_name=region)
    client.put_secret_value(SecretId=arn, SecretString=value)


def is_project_deployed(project_dir: str) -> bool:
    """Check if a project has live infrastructure (non-empty terraform state).

    Runs `jd show --outputs --list` and returns True if any outputs are present.
    A project with empty state (e.g. destroyed but still in S3) returns False.
    """
    result = subprocess.run(
        ["uv", "run", "jd", "show", "--outputs", "--list", "--text", "-p", project_dir],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=JD_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        return False
    return bool(result.stdout.strip())


def run_jd_config(config_args: list[str], project_dir: str, check: bool = True) -> bool:
    """Run jd config with the given arguments in a project directory.

    Returns True on success. With check=False a non-zero exit returns False
    instead of aborting, so optional config steps can be skipped on failure.
    """
    result = run_jd(["config", *config_args], cwd=project_dir, check=check)
    return result.returncode == 0
