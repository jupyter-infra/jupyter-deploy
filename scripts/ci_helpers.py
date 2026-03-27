"""Shared helpers for CI scripts.

Provides boto3-based AWS secret/parameter fetching and jd CLI output reading.
"""

from __future__ import annotations

import subprocess
import sys

import boto3
from mypy_boto3_secretsmanager import SecretsManagerClient
from mypy_boto3_ssm import SSMClient


def arn_region(arn: str) -> str:
    """Extract the AWS region (field 4) from an ARN."""
    parts = arn.split(":")
    if len(parts) < 4:
        print(f"Error: Cannot extract region from ARN: {arn}", file=sys.stderr)
        sys.exit(1)
    return parts[3]


def jd_output(output_name: str, ci_dir: str) -> str:
    """Read a jd output value as plain text."""
    result = subprocess.run(
        ["uv", "run", "jd", "show", "-o", output_name, "--text", "-p", ci_dir],
        capture_output=True,
        text=True,
        check=True,
    )
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


def run_jd_config(config_args: list[str], project_dir: str) -> None:
    """Run jd config with the given arguments in a project directory."""
    subprocess.run(
        ["uv", "run", "jd", "config", *config_args],
        cwd=project_dir,
        check=True,
    )
