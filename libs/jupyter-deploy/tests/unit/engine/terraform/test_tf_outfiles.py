import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from jupyter_deploy.engine.terraform import tf_outdefs, tf_outfiles
from jupyter_deploy.engine.terraform.tf_types import TerraformType


class TestExtractDescriptionFromDotTfFile(unittest.TestCase):
    outputs_tf_content: str

    @classmethod
    def setUpClass(cls) -> None:
        mock_outputs_path = Path(__file__).parent / "mock_outputs.tf"
        with open(mock_outputs_path) as f:
            cls.outputs_tf_content = f.read()

    def test_return_empty_dict_on_empty_content(self) -> None:
        result = tf_outfiles.extract_description_from_dot_tf_content("")
        self.assertEqual({}, result)

    def test_parsing_actual_outputs_dot_tf(self) -> None:
        content = self.outputs_tf_content
        result = tf_outfiles.extract_description_from_dot_tf_content(content)

        expected = {"instance_id": "ID of the jupyter notebook.", "aws_region": "Name of the AWS region."}
        self.assertEqual(expected, result)


class TestCombineCmdAndOutputsDotTfResults(unittest.TestCase):
    def test_combine_add_description_to_matched(self) -> None:
        # Setup
        output_def = tf_outdefs.TerraformStrOutputDefinition(
            output_name="instance_id", value="i-12345abcdef", tf_type=TerraformType.STRING
        )
        output_defs_from_cmd: dict[str, tf_outdefs.TerraformOutputDefinition] = {
            "instance_id": cast(tf_outdefs.TerraformOutputDefinition, output_def)
        }
        descriptions_from_file = {"instance_id": "ID of the jupyter notebook."}

        # Execute
        result = tf_outfiles.combine_cmd_and_outputs_dot_tf_results(output_defs_from_cmd, descriptions_from_file)

        # Verify
        self.assertEqual(1, len(result))
        self.assertEqual("ID of the jupyter notebook.", result["instance_id"].description)

    def test_combine_add_empty_description_if_not_found_in_outputs_dot_tf(self) -> None:
        # Setup
        output_def = tf_outdefs.TerraformStrOutputDefinition(
            output_name="missing_output", value="some-value", tf_type=TerraformType.STRING
        )
        output_defs_from_cmd: dict[str, tf_outdefs.TerraformOutputDefinition] = {
            "missing_output": cast(tf_outdefs.TerraformOutputDefinition, output_def)
        }
        descriptions_from_file = {"instance_id": "ID of the jupyter notebook."}

        # Execute
        with patch("builtins.print") as mock_print:
            result = tf_outfiles.combine_cmd_and_outputs_dot_tf_results(output_defs_from_cmd, descriptions_from_file)

        # Verify
        self.assertEqual(1, len(result))
        self.assertEqual("", result["missing_output"].description)
        mock_print.assert_called_once_with("Warning: output 'missing_output' not found in outputs.tf file.")

    def test_combine_ignore_output_dot_tf_entries_not_matching(self) -> None:
        # Setup
        output_def = tf_outdefs.TerraformStrOutputDefinition(
            output_name="instance_id", value="i-12345abcdef", tf_type=TerraformType.STRING
        )
        output_defs_from_cmd: dict[str, tf_outdefs.TerraformOutputDefinition] = {
            "instance_id": cast(tf_outdefs.TerraformOutputDefinition, output_def)
        }
        descriptions_from_file = {
            "instance_id": "ID of the jupyter notebook.",
            "extra_output": "This output is not in cmd results.",
        }

        # Execute
        result = tf_outfiles.combine_cmd_and_outputs_dot_tf_results(output_defs_from_cmd, descriptions_from_file)

        # Verify
        self.assertEqual(1, len(result))
        self.assertEqual("ID of the jupyter notebook.", result["instance_id"].description)
        self.assertNotIn("extra_output", result)

    def test_combine_returns_empty_dict_on_empty_cmd_defs(self) -> None:
        # Setup
        output_defs_from_cmd: dict[str, tf_outdefs.TerraformOutputDefinition] = {}
        descriptions_from_file: dict[str, str] = {}

        # Execute
        result = tf_outfiles.combine_cmd_and_outputs_dot_tf_results(output_defs_from_cmd, descriptions_from_file)

        # Verify
        self.assertEqual({}, result)
