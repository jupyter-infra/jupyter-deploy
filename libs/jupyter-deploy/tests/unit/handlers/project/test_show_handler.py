import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.handlers.project.show_handler import ShowHandler
from jupyter_deploy.manifest import JupyterDeployManifestV1


class TestShowHandler(unittest.TestCase):
    def get_mock_manifest(self) -> JupyterDeployManifestV1:
        """Create a mock manifest."""
        return JupyterDeployManifestV1(
            **{  # type: ignore
                "schema_version": 1,
                "template": {
                    "name": "tf-aws-ec2-base",
                    "engine": "terraform",
                    "version": "1.0.0",
                },
            }
        )

    def get_mock_console_and_fns(self) -> tuple[Mock, dict[str, Mock]]:
        """Return a mocked rich console instance."""
        mock_console = Mock()
        mock_print = Mock()
        mock_line = Mock()
        mock_console.print = mock_print
        mock_console.line = mock_line
        return mock_console, {"print": mock_print, "line": mock_line}

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    def test_init_terraform(self, mock_retrieve_manifest: Mock) -> None:
        mock_manifest = self.get_mock_manifest()
        mock_retrieve_manifest.return_value = mock_manifest
        handler = ShowHandler()

        self.assertIsNotNone(handler._outputs_handler)
        self.assertIsNotNone(handler._variables_handler)
        self.assertEqual(handler.engine, EngineType.TERRAFORM)
        self.assertEqual(handler.project_manifest, mock_manifest)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("rich.console.Console")
    def test_show_project_basic_info(self, mock_console_cls: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.get_mock_manifest()
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console
        handler = ShowHandler()

        handler._show_project_basic_info()

        # Verify console.print was called (header + table)
        self.assertEqual(mock_console_fns["print"].call_count, 2)
        self.assertEqual(mock_console_fns["line"].call_count, 2)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("rich.console.Console")
    def test_show_project_outputs_no_outputs(self, mock_console_cls: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.get_mock_manifest()
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console
        handler = ShowHandler()

        with patch.object(handler._outputs_handler, "get_full_project_outputs", return_value={}) as _:
            handler._show_project_outputs()

        # Check that both lines are printed with correct styles
        mock_console_fns["print"].assert_any_call(":warning: No outputs available.", style="yellow")
        mock_console_fns["print"].assert_any_call(
            "This is normal if the project has not been deployed yet.", style="yellow"
        )
        self.assertEqual(mock_console_fns["print"].call_count, 2)
        mock_console_fns["line"].assert_called_once()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("rich.console.Console")
    def test_show_project_outputs_with_outputs(self, mock_console_cls: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.get_mock_manifest()
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console
        handler = ShowHandler()

        mock_output = Mock()
        mock_output.value = "https://example.com"
        mock_output.description = "Jupyter URL"
        mock_outputs = {"jupyter_url": mock_output}

        with patch.object(handler._outputs_handler, "get_full_project_outputs", return_value=mock_outputs) as _:
            handler._show_project_outputs()

        # Verify console.print was called (header + table)
        self.assertEqual(mock_console_fns["print"].call_count, 2)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("rich.console.Console")
    def test_show_project_outputs_exception(self, mock_console_cls: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.get_mock_manifest()
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console
        handler = ShowHandler()

        with patch.object(handler._outputs_handler, "get_full_project_outputs", side_effect=Exception("Test error")):
            handler._show_project_outputs()

        # Verify error handling
        mock_console_fns["print"].assert_any_call(":x: Could not retrieve outputs: Test error", style="red")
        mock_console_fns["line"].assert_called_once()

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("rich.console.Console")
    def test_show_project_variables_no_variables(self, mock_console_cls: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.get_mock_manifest()
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console
        handler = ShowHandler()

        with (
            patch.object(handler._variables_handler, "get_template_variables", return_value={}),
            patch.object(handler._variables_handler, "sync_engine_varfiles_with_project_variables_config"),
        ):
            handler._show_project_variables()

        mock_console_fns["print"].assert_called_once_with(":x: No variables available.", style="red")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("rich.console.Console")
    def test_show_project_variables_with_variables(self, mock_console_cls: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.get_mock_manifest()
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console
        handler = ShowHandler()

        # Create mock variables
        mock_normal_var = Mock()
        mock_normal_var.get_cli_description = Mock(return_value="Normal variable")
        mock_normal_var.sensitive = False
        mock_normal_var.assigned_value = "value1"

        mock_sensitive_var = Mock()
        mock_sensitive_var.get_cli_description = Mock(return_value="Sensitive variable")
        mock_sensitive_var.sensitive = True
        mock_sensitive_var.assigned_value = "secret"

        mock_vars = {"normal_var": mock_normal_var, "sensitive_var": mock_sensitive_var}

        with (
            patch.object(handler._variables_handler, "get_template_variables", return_value=mock_vars),
            patch.object(handler._variables_handler, "sync_engine_varfiles_with_project_variables_config"),
        ):
            handler._show_project_variables()

        # Verify console.print was called (header + table)
        self.assertEqual(mock_console_fns["print"].call_count, 2)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    def test_sensitive_variables_are_masked(self, mock_retrieve_manifest: Mock) -> None:
        """Test that sensitive variables are properly masked in the output."""
        mock_retrieve_manifest.return_value = self.get_mock_manifest()
        handler = ShowHandler()

        # Create mock variables with one sensitive and one normal variable
        mock_normal_var = Mock()
        mock_normal_var.get_cli_description = Mock(return_value="Normal variable")
        mock_normal_var.sensitive = False
        mock_normal_var.assigned_value = "visible_value"

        mock_sensitive_var = Mock()
        mock_sensitive_var.get_cli_description = Mock(return_value="Sensitive variable")
        mock_sensitive_var.sensitive = True
        mock_sensitive_var.assigned_value = "secret_value_should_not_be_visible"

        mock_vars = {"normal_var": mock_normal_var, "sensitive_var": mock_sensitive_var}

        # Mock the actual Table.add_row method to capture the values being added
        rows_added: list[tuple[str, ...]] = []

        def capture_add_row(*args: str, **kwargs: object) -> None:
            rows_added.append(args)
            return None

        with (
            patch.object(handler._variables_handler, "get_template_variables", return_value=mock_vars),
            patch.object(handler._variables_handler, "sync_engine_varfiles_with_project_variables_config"),
            patch("rich.table.Table.add_row", side_effect=capture_add_row),
        ):
            handler._show_project_variables()

        # Find rows for our variables
        normal_var_row: tuple[str, ...] | None = None
        sensitive_var_row: tuple[str, ...] | None = None

        for row in rows_added:
            if len(row) >= 3:  # Ensure row has enough elements
                if row[0] == "normal_var":
                    normal_var_row = row
                elif row[0] == "sensitive_var":
                    sensitive_var_row = row

        # Verify both variables were added to the table
        self.assertIsNotNone(normal_var_row, "Normal variable row not found in table")
        self.assertIsNotNone(sensitive_var_row, "Sensitive variable row not found in table")

        # Verify normal variable shows its actual value
        assert normal_var_row is not None  # For mypy
        self.assertEqual(normal_var_row[1], "visible_value", "Normal variable value should be visible")

        # Verify sensitive variable value is masked
        assert sensitive_var_row is not None  # For mypy
        self.assertEqual(sensitive_var_row[1], "****", "Sensitive variable should be masked with asterisks")
        self.assertNotEqual(
            sensitive_var_row[1],
            "secret_value_should_not_be_visible",
            "Sensitive variable value should not be displayed",
        )

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("rich.console.Console")
    def test_show_project_variables_exception(self, mock_console_cls: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.get_mock_manifest()
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console
        handler = ShowHandler()

        with patch.object(
            handler._variables_handler,
            "sync_engine_varfiles_with_project_variables_config",
            side_effect=Exception("Test error"),
        ):
            handler._show_project_variables()

        # Verify error handling
        mock_console_fns["print"].assert_called_once_with(":x: Could not retrieve variables: Test error", style="red")

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("rich.console.Console")
    def test_show_project_info_default(self, mock_console_cls: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.get_mock_manifest()
        mock_console, mock_console_fns = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console
        handler = ShowHandler()

        with (
            patch.object(handler, "_show_project_basic_info") as mock_basic,
            patch.object(handler, "_show_project_outputs") as mock_outputs,
            patch.object(handler, "_show_project_variables") as mock_variables,
        ):
            handler.show_project_info()
            mock_basic.assert_called_once()
            mock_outputs.assert_called_once()
            mock_variables.assert_called_once()

        self.assertEqual(mock_console_fns["line"].call_count, 3)

    @patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
    @patch("rich.console.Console")
    def test_show_project_info_with_flags(self, mock_console_cls: Mock, mock_retrieve_manifest: Mock) -> None:
        mock_retrieve_manifest.return_value = self.get_mock_manifest()
        mock_console, _ = self.get_mock_console_and_fns()
        mock_console_cls.return_value = mock_console
        handler = ShowHandler()

        with (
            patch.object(handler, "_show_project_basic_info") as mock_basic,
            patch.object(handler, "_show_project_outputs") as mock_outputs,
            patch.object(handler, "_show_project_variables") as mock_variables,
        ):
            # Test with only info flag
            handler.show_project_info(show_info=True, show_outputs=False, show_variables=False)
            mock_basic.assert_called_once()
            mock_outputs.assert_not_called()
            mock_variables.assert_not_called()
            mock_basic.reset_mock()

            # Test with only outputs flag
            handler.show_project_info(show_info=False, show_outputs=True, show_variables=False)
            mock_basic.assert_not_called()
            mock_outputs.assert_called_once()
            mock_variables.assert_not_called()
            mock_outputs.reset_mock()

            # Test with only variables flag
            handler.show_project_info(show_info=False, show_outputs=False, show_variables=True)
            mock_basic.assert_not_called()
            mock_outputs.assert_not_called()
            mock_variables.assert_called_once()
            mock_variables.reset_mock()

            # Test with multiple flags
            handler.show_project_info(show_info=True, show_outputs=True, show_variables=False)
            mock_basic.assert_called_once()
            mock_outputs.assert_called_once()
            mock_variables.assert_not_called()
