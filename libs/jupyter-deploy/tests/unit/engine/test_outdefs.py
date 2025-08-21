import unittest
from unittest.mock import Mock, patch

from parameterized import parameterized  # type: ignore

from jupyter_deploy.engine import outdefs


class TestStrTemplateOutputDefinition(unittest.TestCase):
    @patch("jupyter_deploy.str_utils.get_trimmed_header")
    def test_str_outdef_with_value_should_get_a_valid_trimmed_header(self, mock_get_trimmed_header: Mock) -> None:
        # Arrange
        mock_get_trimmed_header.return_value = "Test description"
        outdef = outdefs.StrTemplateOutputDefinition(
            output_name="test_output", description="Test description", value="test_value"
        )

        # Act
        result = outdef.get_cli_description()

        # Assert
        mock_get_trimmed_header.assert_called_once_with("Test description")
        self.assertEqual(result, "Test description value: test_value")

    @patch("jupyter_deploy.str_utils.get_trimmed_header")
    def test_str_outdef_without_value_should_get_a_valid_trimmed_header(self, mock_get_trimmed_header: Mock) -> None:
        # Arrange
        mock_get_trimmed_header.return_value = "Test description"
        outdef = outdefs.StrTemplateOutputDefinition(
            output_name="test_output", description="Test description", value=None
        )

        # Act
        result = outdef.get_cli_description()

        # Assert
        mock_get_trimmed_header.assert_called_once_with("Test description")
        self.assertEqual(result, "Test description")


class TestRequireOutputDef(unittest.TestCase):
    def test_str_outdef_should_resolve_when_prompted_for_str(self) -> None:
        # Arrange
        output_name = "test_output"
        str_outdef = outdefs.StrTemplateOutputDefinition(
            output_name=output_name, description="Test description", value="test_value"
        )
        output_defs: dict[str, outdefs.TemplateOutputDefinition] = {output_name: str_outdef}

        # Act
        result = outdefs.require_output_def(output_defs, output_name, outdefs.StrTemplateOutputDefinition)

        # Assert
        self.assertEqual(result, str_outdef)
        self.assertEqual(result.value, "test_value")

    @parameterized.expand([(int), (float), (bool), (list), (dict)])
    def test_str_outdef_should_raise_type_exception_when_prompted_invalid_type(self, type: type) -> None:
        # Arrange
        output_name = "test_output"
        str_outdef = outdefs.StrTemplateOutputDefinition(
            output_name=output_name, description="Test description", value="test_value"
        )
        output_defs: dict[str, outdefs.TemplateOutputDefinition] = {output_name: str_outdef}

        class OtherTypeClass(outdefs.TemplateOutputDefinition[type]):  # type: ignore
            pass

        # Act & Assert
        with self.assertRaises(TypeError):
            outdefs.require_output_def(output_defs, output_name, OtherTypeClass)

    def test_should_raise_key_error_when_output_not_found(self) -> None:
        # Arrange
        output_defs: dict[str, outdefs.TemplateOutputDefinition] = {
            "existing_output": outdefs.StrTemplateOutputDefinition(output_name="existing_output")
        }
        non_existent_output = "non_existent_output"

        # Act & Assert
        with self.assertRaises(KeyError) as context:
            outdefs.require_output_def(output_defs, non_existent_output, outdefs.StrTemplateOutputDefinition)

        self.assertIn(f"Required output '{non_existent_output}' not found", str(context.exception))


class TestListStrTemplateOutputDefinition(unittest.TestCase):
    @patch("jupyter_deploy.str_utils.get_trimmed_header")
    def test_list_str_outdef_with_value_should_get_a_valid_trimmed_header(self, mock_get_trimmed_header: Mock) -> None:
        # Arrange
        mock_get_trimmed_header.return_value = "Test description"
        test_value = ["item1", "item2", "item3"]
        outdef = outdefs.ListStrTemplateOutputDefinition(
            output_name="test_output", description="Test description", value=test_value
        )

        # Act
        result = outdef.get_cli_description()

        # Assert
        mock_get_trimmed_header.assert_called_once_with("Test description")
        self.assertEqual(result, f"Test description value: {test_value}")

    @patch("jupyter_deploy.str_utils.get_trimmed_header")
    def test_list_str_outdef_with_empty_list_value(self, mock_get_trimmed_header: Mock) -> None:
        # Arrange
        mock_get_trimmed_header.return_value = "Test description"
        test_value: list[str] = []
        outdef = outdefs.ListStrTemplateOutputDefinition(
            output_name="test_output", description="Test description", value=test_value
        )

        # Act
        result = outdef.get_cli_description()

        # Assert
        mock_get_trimmed_header.assert_called_once_with("Test description")
        self.assertEqual(result, "Test description value: []")

    @patch("jupyter_deploy.str_utils.get_trimmed_header")
    def test_list_str_outdef_without_value_should_get_a_valid_trimmed_header(
        self, mock_get_trimmed_header: Mock
    ) -> None:
        # Arrange
        mock_get_trimmed_header.return_value = "Test description"
        outdef = outdefs.ListStrTemplateOutputDefinition(
            output_name="test_output", description="Test description", value=None
        )

        # Act
        result = outdef.get_cli_description()

        # Assert
        mock_get_trimmed_header.assert_called_once_with("Test description")
        self.assertEqual(result, "Test description")

    def test_list_str_outdef_should_resolve_when_prompted_for_list_str(self) -> None:
        # Arrange
        output_name = "test_output"
        test_value = ["item1", "item2", "item3"]
        list_str_outdef = outdefs.ListStrTemplateOutputDefinition(
            output_name=output_name, description="Test description", value=test_value
        )
        output_defs: dict[str, outdefs.TemplateOutputDefinition] = {output_name: list_str_outdef}

        # Act
        result = outdefs.require_output_def(output_defs, output_name, outdefs.ListStrTemplateOutputDefinition)

        # Assert
        self.assertEqual(result, list_str_outdef)
        self.assertEqual(result.value, test_value)

    def test_list_str_outdef_should_raise_type_exception_when_prompted_as_str(self) -> None:
        # Arrange
        output_name = "test_output"
        test_value = ["item1", "item2", "item3"]
        list_str_outdef = outdefs.ListStrTemplateOutputDefinition(
            output_name=output_name, description="Test description", value=test_value
        )
        output_defs: dict[str, outdefs.TemplateOutputDefinition] = {output_name: list_str_outdef}

        # Act & Assert
        with self.assertRaises(TypeError):
            outdefs.require_output_def(output_defs, output_name, outdefs.StrTemplateOutputDefinition)
