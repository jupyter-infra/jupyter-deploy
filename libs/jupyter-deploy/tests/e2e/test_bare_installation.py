"""Bare install track tests — validate the CLI works without AWS deps.

These tests MUST be run with ``pytest -m bare`` in an environment where
``jupyter-deploy`` was installed WITHOUT the ``[aws]`` extra. They will
fail (not skip) if boto3 is present — that's intentional: a bare track
that accidentally includes cloud deps is a real bug.
"""

import unittest

import pytest


@pytest.mark.bare
class TestBareInstallation(unittest.TestCase):
    def test_no_boto3(self) -> None:
        with self.assertRaises(ImportError):
            import boto3  # noqa: F401

    def test_no_botocore(self) -> None:
        with self.assertRaises(ImportError):
            import botocore  # noqa: F401

    def test_no_kubernetes(self) -> None:
        with self.assertRaises(ImportError):
            import kubernetes  # noqa: F401

    def test_no_client_proxy(self) -> None:
        # `jd` shells out to the `jupyter-deploy-client-proxy` console script and must NEVER import
        # it. The proxy is a separate package shipped only via the `[proxy]` extra. This assertion
        # turns the bare track red if a handler ever imports it directly.
        with self.assertRaises(ImportError):
            import jupyter_deploy_client_proxy  # noqa: F401

    def test_aws_provider_import_fails(self) -> None:
        with self.assertRaises(ImportError):
            from jupyter_deploy.provider.aws import aws_runner  # noqa: F401

    def test_k8s_provider_import_fails(self) -> None:
        with self.assertRaises(ImportError):
            from jupyter_deploy.provider.k8s import k8s_runner  # noqa: F401
