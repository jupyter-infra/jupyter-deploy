import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from jupyter_deploy.fs_utils import (
    read_yaml_reference_file,
    write_yaml_file_with_comments,
    write_yaml_reference_file,
)
from jupyter_deploy.variables_config import (
    VARIABLES_CONFIG_V2_COMMENTS,
    VARIABLES_CONFIG_V2_KEYS_ORDER,
)


class TestWriteYamlFileWithCommentedEntries(unittest.TestCase):
    def _write_v2(
        self,
        path: Path,
        required: dict,
        required_sensitive: dict,
        overrides: dict,
        defaults_for_comments: dict,
    ) -> None:
        content = {
            "schema_version": 2,
            "required": required,
            "required_sensitive": required_sensitive,
            "overrides": overrides,
        }
        write_yaml_file_with_comments(
            file_path=path,
            content=content,
            key_order=VARIABLES_CONFIG_V2_KEYS_ORDER,
            comments=VARIABLES_CONFIG_V2_COMMENTS,
            commented_entries={"overrides": defaults_for_comments},
        )

    def test_write_basic_v2(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "variables.yaml"
            self._write_v2(
                path=path,
                required={"domain": "example.com", "email": None},
                required_sensitive={"secret": "****"},
                overrides={"region": "eu-west-1"},
                defaults_for_comments={"region": "us-west-2", "instance_type": "t3.medium"},
            )

            content = path.read_text()
            # Verify schema_version
            self.assertIn("schema_version: 2", content)
            # Verify required section
            self.assertIn("domain: example.com", content)
            self.assertIn("email: null", content)
            # Verify sensitive section
            self.assertIn("secret: '****'", content)
            # Verify active override
            self.assertIn("  region: eu-west-1", content)
            # Verify inactive default as comment (region is active, so only instance_type)
            self.assertIn("  # instance_type: t3.medium", content)
            # region should NOT appear as a comment (it's an active override)
            commented_lines = [line for line in content.splitlines() if line.strip().startswith("# region:")]
            self.assertEqual(len(commented_lines), 0)

    def test_write_empty_overrides_all_commented(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "variables.yaml"
            self._write_v2(
                path=path,
                required={"domain": None},
                required_sensitive={},
                overrides={},
                defaults_for_comments={"region": "us-west-2", "size": 30},
            )

            content = path.read_text()
            self.assertIn("  # region: us-west-2", content)
            self.assertIn("  # size: 30", content)

    def test_write_complex_defaults_as_multiline_comments(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "variables.yaml"
            defaults = {
                "node_groups": [
                    {"name": "workers", "instance_type": "t3.medium", "size": 2},
                    {"name": "gpu", "instance_type": "p3.2xlarge", "size": 1},
                ],
                "tags": {"env": "prod", "team": "ml"},
            }
            self._write_v2(
                path=path,
                required={},
                required_sensitive={},
                overrides={},
                defaults_for_comments=defaults,
            )

            content = path.read_text()
            # Should have multi-line comments for complex types
            self.assertIn("  # node_groups:", content)
            self.assertIn("  # - name: workers", content)
            self.assertIn("  #   instance_type: t3.medium", content)
            self.assertIn("  # tags:", content)
            self.assertIn("  #   env: prod", content)

    def test_write_parseable_as_v2(self) -> None:
        """Verify the output is valid YAML and parses as schema_version 2."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "variables.yaml"
            self._write_v2(
                path=path,
                required={"domain": "example.com"},
                required_sensitive={"secret": None},
                overrides={"region": "us-west-2"},
                defaults_for_comments={"region": "us-east-1", "size": 10},
            )

            with open(path) as f:
                parsed = yaml.safe_load(f)

            self.assertEqual(parsed["schema_version"], 2)
            self.assertEqual(parsed["required"]["domain"], "example.com")
            self.assertEqual(parsed["overrides"]["region"], "us-west-2")
            # Comments are ignored by YAML parser, so size should not be in overrides
            self.assertNotIn("size", parsed.get("overrides", {}))

    def test_write_no_defaults_section(self) -> None:
        """Ensure no 'defaults:' section appears in v2 output."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "variables.yaml"
            self._write_v2(
                path=path,
                required={"domain": None},
                required_sensitive={},
                overrides={},
                defaults_for_comments={"region": "us-west-2"},
            )

            content = path.read_text()
            # Should not have a top-level 'defaults:' key
            lines = content.splitlines()
            top_level_defaults = [line for line in lines if line.startswith("defaults:")]
            self.assertEqual(len(top_level_defaults), 0)

    def test_header_comments_present(self) -> None:
        """Verify section header comments appear."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "variables.yaml"
            self._write_v2(
                path=path,
                required={"domain": None},
                required_sensitive={"secret": None},
                overrides={},
                defaults_for_comments={"region": "us-west-2"},
            )

            content = path.read_text()
            self.assertIn("# fill in values below", content)
            self.assertIn("# uncomment and change a value to override the default", content)
            self.assertIn("# values entered here will be masked", content)


class TestYamlReferenceFile(unittest.TestCase):
    def test_write_and_read(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".jd" / "variables-defaults.yaml"
            defaults = {
                "region": "us-west-2",
                "instance_type": "t3.medium",
                "node_groups": [{"name": "workers", "size": 2}],
            }
            write_yaml_reference_file(path, defaults, header="auto-generated")
            result = read_yaml_reference_file(path)

            self.assertEqual(result["region"], "us-west-2")
            self.assertEqual(result["instance_type"], "t3.medium")
            self.assertEqual(result["node_groups"], [{"name": "workers", "size": 2}])

    def test_read_nonexistent_returns_empty(self) -> None:
        path = Path("/nonexistent/path/variables-defaults.yaml")
        result = read_yaml_reference_file(path)
        self.assertEqual(result, {})

    def test_write_creates_parent_dirs(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "deep" / "nested" / "variables-defaults.yaml"
            write_yaml_reference_file(path, {"region": "us-west-2"})
            self.assertTrue(path.exists())

    def test_write_empty_defaults(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "variables-defaults.yaml"
            write_yaml_reference_file(path, {})
            result = read_yaml_reference_file(path)
            self.assertEqual(result, {})

    def test_read_invalid_content_returns_empty(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "variables-defaults.yaml"
            path.write_text("not a dict\n")
            result = read_yaml_reference_file(path)
            self.assertEqual(result, {})

    def test_header_written(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "defaults.yaml"
            write_yaml_reference_file(path, {"x": 1}, header="do not edit")
            content = path.read_text()
            self.assertTrue(content.startswith("# do not edit\n"))
