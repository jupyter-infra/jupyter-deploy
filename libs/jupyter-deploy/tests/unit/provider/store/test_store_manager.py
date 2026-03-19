import unittest

from jupyter_deploy.provider.store.store_manager import StoreManager


class TestSafeParseVariables(unittest.TestCase):
    def test_parses_all_sections(self) -> None:
        content = (
            "schema_version: 1\n"
            "required:\n  project_name: my-project\n"
            "required_sensitive:\n  gh_token: secret123\n"
            "overrides:\n  instance_type: t3.large\n"
            "defaults:\n  instance_type: t3.medium\n  region: us-east-1\n"
        )
        result = StoreManager._safe_parse_variables(content)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["project_name"], "my-project")
        self.assertEqual(result["gh_token"], "****")
        # Override takes precedence over default
        self.assertEqual(result["instance_type"], "t3.large")
        self.assertEqual(result["region"], "us-east-1")

    def test_defaults_without_overrides(self) -> None:
        content = (
            "schema_version: 1\n"
            "required:\n  project_name: test\n"
            "defaults:\n  region: us-west-2\n  instance_type: t3.micro\n"
        )
        result = StoreManager._safe_parse_variables(content)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["region"], "us-west-2")
        self.assertEqual(result["instance_type"], "t3.micro")

    def test_returns_none_for_invalid_yaml(self) -> None:
        result = StoreManager._safe_parse_variables("{{invalid yaml")
        self.assertIsNone(result)

    def test_returns_none_for_non_dict(self) -> None:
        result = StoreManager._safe_parse_variables("just a string")
        self.assertIsNone(result)

    def test_returns_none_for_invalid_schema(self) -> None:
        result = StoreManager._safe_parse_variables("schema_version: 99\nrequired: {}\n")
        self.assertIsNone(result)

    def test_empty_sections(self) -> None:
        content = "schema_version: 1\nrequired:\nrequired_sensitive:\noverrides:\ndefaults:\n"
        result = StoreManager._safe_parse_variables(content)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result, {})
