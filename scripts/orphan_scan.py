#!/usr/bin/env python3
"""Scan for AWS resources still tagged with a DeploymentId after a jd down.

The templates tag every terraform-managed resource with DeploymentId, so
anything still carrying the tag after a destroy is an orphan; the scan prints
the ARNs and exits non-zero. The Resource Groups Tagging API is regional and
eventually consistent after deletions, so the scan runs in the caller's
configured AWS region and retries before failing.

Known blind spot: resources created at runtime by Kubernetes controllers (the
NLB and its ENIs from the traefik Service, security groups from the load
balancer controller) do not inherit terraform tags, so this scan cannot see
them; cluster teardown deletes them via the Service/controller path instead.

Usage: scripts/orphan_scan.py <deployment-id>
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import boto3
from ci_helpers import run_jd
from mypy_boto3_resourcegroupstaggingapi import ResourceGroupsTaggingAPIClient

SCAN_ATTEMPTS = 5
SCAN_INTERVAL_SECONDS = 60


def read_deployment_id(project_dir: Path) -> str | None:
    """Read the deployment_id output of a project; None when outputs are unavailable.

    Must run BEFORE jd down: the destroy removes the outputs along with the state.
    """
    result = run_jd(["show", "-o", "deployment_id", "--text"], cwd=str(project_dir), capture=True, check=False)
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def find_tagged_resources(deployment_id: str) -> list[str]:
    """Return the ARNs of resources currently tagged DeploymentId=<deployment_id>."""
    client: ResourceGroupsTaggingAPIClient = boto3.client("resourcegroupstaggingapi")
    paginator = client.get_paginator("get_resources")
    arns: list[str] = []
    for page in paginator.paginate(TagFilters=[{"Key": "DeploymentId", "Values": [deployment_id]}]):
        arns.extend(mapping["ResourceARN"] for mapping in page["ResourceTagMappingList"])
    return arns


def scan_or_fail(deployment_id: str) -> None:
    """Exit 1 listing any resources still tagged with the DeploymentId."""
    print(f"Scanning for resources still tagged DeploymentId={deployment_id}...")
    orphans: list[str] = []
    for attempt in range(1, SCAN_ATTEMPTS + 1):
        orphans = find_tagged_resources(deployment_id)
        if not orphans:
            print("  No tagged resources remain.")
            return
        print(f"  Attempt {attempt}/{SCAN_ATTEMPTS}: {len(orphans)} resource(s) still tagged.")
        if attempt < SCAN_ATTEMPTS:
            print(f"  Retrying in {SCAN_INTERVAL_SECONDS}s (the tag index lags deletions)...")
            time.sleep(SCAN_INTERVAL_SECONDS)

    print(
        f"Error: {len(orphans)} resource(s) still tagged DeploymentId={deployment_id} after the destroy:",
        file=sys.stderr,
    )
    for arn in orphans:
        print(f"  {arn}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1]:
        print("Usage: scripts/orphan_scan.py <deployment-id>")
        sys.exit(2)
    scan_or_fail(sys.argv[1])


if __name__ == "__main__":
    main()
