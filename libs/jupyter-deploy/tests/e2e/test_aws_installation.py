"""AWS install track tests — validate the CLI works with the [aws] extra.

These tests run in the ``aws`` install track where ``jupyter-deploy[aws]``
is installed alongside the base template.
"""

import unittest


class TestAwsInstallation(unittest.TestCase):
    def test_boto3_importable(self) -> None:
        import boto3  # noqa: F401

    def test_botocore_importable(self) -> None:
        import botocore  # noqa: F401

    def test_provider_factory_resolves(self) -> None:
        from jupyter_deploy.provider.aws import aws_runner  # noqa: F401
