import unittest

from pydantic import ValidationError

from jupyter_deploy.enum import StoreType
from jupyter_deploy.exceptions import InvalidStoreTypeError, InvalidTemplateNameError
from jupyter_deploy.preferences import JupyterDeployPreferencesV1, validate_template_name


class TestJupyterDeployPreferencesV1(unittest.TestCase):
    def test_defaults_to_no_preference(self) -> None:
        prefs = JupyterDeployPreferencesV1()

        self.assertIsNone(prefs.default_template)
        self.assertIsNone(prefs.default_store_type)

    def test_parses_hyphenated_keys(self) -> None:
        prefs = JupyterDeployPreferencesV1(
            **{"default-template": "aws:ec2:base", "default-store-type": "s3-ddb"},
        )

        self.assertEqual(prefs.default_template, "aws:ec2:base")
        self.assertEqual(prefs.default_store_type, "s3-ddb")

    def test_parses_partial_content(self) -> None:
        prefs = JupyterDeployPreferencesV1(**{"default-store-type": "s3-only"})

        self.assertIsNone(prefs.default_template)
        self.assertEqual(prefs.default_store_type, "s3-only")

    def test_preserves_unknown_keys(self) -> None:
        prefs = JupyterDeployPreferencesV1(**{"default-template": "aws:ec2:base", "from-the-future": "keep-me"})

        content = prefs.model_dump(by_alias=True, exclude_none=True)
        self.assertEqual(content["from-the-future"], "keep-me")

    def test_dumps_with_hyphenated_keys(self) -> None:
        prefs = JupyterDeployPreferencesV1(default_template="aws:ec2:base")

        content = prefs.model_dump(by_alias=True, exclude_none=True)
        self.assertEqual(content, {"schema_version": 1, "default-template": "aws:ec2:base"})

    def test_defaults_the_schema_version(self) -> None:
        """A file with no version is a V1 file: this one is hand-editable, unlike the generated ones."""
        self.assertEqual(JupyterDeployPreferencesV1().schema_version, 1)

    def test_accepts_the_declared_schema_version(self) -> None:
        prefs = JupyterDeployPreferencesV1(**{"schema_version": 1, "default-template": "aws:ec2:base"})

        self.assertEqual(prefs.schema_version, 1)
        self.assertEqual(prefs.default_template, "aws:ec2:base")

    def test_rejects_a_later_schema_version(self) -> None:
        """Only a breaking change bumps the version, so a later one must not be read as a V1 file."""
        with self.assertRaises(ValidationError):
            JupyterDeployPreferencesV1(**{"schema_version": 2, "default-template": "aws:ec2:base"})

    def test_get_store_type_returns_enum(self) -> None:
        prefs = JupyterDeployPreferencesV1(default_store_type="s3-ddb")

        self.assertEqual(prefs.get_store_type(), StoreType.S3_DDB)

    def test_get_store_type_is_case_insensitive(self) -> None:
        prefs = JupyterDeployPreferencesV1(default_store_type="S3-Only")

        self.assertEqual(prefs.get_store_type(), StoreType.S3_ONLY)

    def test_get_store_type_returns_none_when_unset(self) -> None:
        self.assertIsNone(JupyterDeployPreferencesV1().get_store_type())

    def test_get_store_type_raises_on_unknown_value(self) -> None:
        prefs = JupyterDeployPreferencesV1(default_store_type="dynamodb")

        with self.assertRaises(InvalidStoreTypeError) as ctx:
            prefs.get_store_type()

        self.assertEqual(ctx.exception.store_type, "dynamodb")
        self.assertEqual(ctx.exception.valid_store_types, ["s3-only", "s3-ddb"])


class TestValidateTemplateName(unittest.TestCase):
    def test_accepts_three_segments(self) -> None:
        validate_template_name("aws:ec2:jupyterlab")

    def test_rejects_base_name(self) -> None:
        with self.assertRaises(InvalidTemplateNameError):
            validate_template_name("jupyterlab")

    def test_rejects_two_segments(self) -> None:
        with self.assertRaises(InvalidTemplateNameError):
            validate_template_name("ec2:jupyterlab")

    def test_rejects_four_segments(self) -> None:
        with self.assertRaises(InvalidTemplateNameError):
            validate_template_name("aws:ec2:jupyterlab:v2")

    def test_rejects_empty_segment(self) -> None:
        with self.assertRaises(InvalidTemplateNameError) as ctx:
            validate_template_name("aws::jupyterlab")

        self.assertEqual(ctx.exception.template_name, "aws::jupyterlab")
