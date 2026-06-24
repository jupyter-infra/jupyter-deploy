"""Namespace lifecycle helpers for E2E tests."""

import json
import subprocess
from collections.abc import Generator
from contextlib import contextmanager


def create_namespace(name: str, labels: dict[str, str] | None = None) -> None:
    """Create a namespace, optionally applying labels."""
    subprocess.run(["kubectl", "create", "namespace", name], check=True, capture_output=True, text=True)
    for key, value in (labels or {}).items():
        subprocess.run(
            ["kubectl", "label", "namespace", name, f"{key}={value}", "--overwrite"],
            check=True,
            capture_output=True,
            text=True,
        )


def delete_namespace(name: str) -> None:
    """Delete a namespace (best-effort, non-blocking)."""
    subprocess.run(
        ["kubectl", "delete", "namespace", name, "--ignore-not-found", "--wait=false"],
        capture_output=True,
        text=True,
    )


def get_namespace_labels(name: str) -> dict[str, str]:
    """Return the namespace's labels as a dict."""
    result = subprocess.run(
        ["kubectl", "get", "namespace", name, "-o", "jsonpath={.metadata.labels}"],
        check=True,
        capture_output=True,
        text=True,
    )
    raw = result.stdout.strip()
    if not raw:
        return {}
    labels: dict[str, str] = json.loads(raw)
    return labels


@contextmanager
def temporary_namespace(name: str, labels: dict[str, str] | None = None) -> Generator[str, None, None]:
    """Create a namespace for the duration of the block, deleting it on exit.

    Yields the namespace name. Deletion is best-effort and runs even if the body
    raises.
    """
    create_namespace(name, labels=labels)
    try:
        yield name
    finally:
        delete_namespace(name)
