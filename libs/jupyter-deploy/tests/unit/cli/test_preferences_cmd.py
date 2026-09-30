import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.app import runner as app_runner
from jupyter_deploy.enum import PreferenceName, PreferenceSource, StoreType
from jupyter_deploy.exceptions import ReadPreferencesError
from jupyter_deploy.preferences import PreferenceEntry

_HANDLER = "jupyter_deploy.cli.preferences_app.PreferencesHandler"

_BUILT_IN_ENTRIES = [
    PreferenceEntry(
        name=PreferenceName.DEFAULT_TEMPLATE,
        value="aws:ec2:jupyterlab",
        source=PreferenceSource.BUILT_IN,
    ),
    PreferenceEntry(name=PreferenceName.DEFAULT_STORE_TYPE, value=None, source=PreferenceSource.UNSET),
]

_RECORDED_ENTRIES = [
    PreferenceEntry(name=PreferenceName.DEFAULT_TEMPLATE, value="aws:ec2:base", source=PreferenceSource.PREFERENCES),
    PreferenceEntry(name=PreferenceName.DEFAULT_STORE_TYPE, value="s3-ddb", source=PreferenceSource.PREFERENCES),
]


def get_mock_handler(entries: list[PreferenceEntry] | None = None) -> Mock:
    mock_handler = Mock()
    mock_handler.preferences_path = Path("/home/someone/.jupyter-deploy/preferences.yaml")
    mock_handler.list_preferences.return_value = entries if entries is not None else _BUILT_IN_ENTRIES
    mock_handler.set_preferences.return_value = mock_handler.preferences_path
    mock_handler.unset_preferences.return_value = mock_handler.preferences_path
    mock_handler.unset_all_preferences.return_value = True
    return mock_handler


class TestPreferencesShowCommand(unittest.TestCase):
    @patch(_HANDLER)
    def test_shows_a_table_of_effective_values(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = get_mock_handler(_RECORDED_ENTRIES)

        result = CliRunner().invoke(app_runner.app, ["preferences", "show"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("default-template", result.output)
        self.assertIn("aws:ec2:base", result.output)
        self.assertIn("s3-ddb", result.output)

    @patch(_HANDLER)
    def test_shows_the_file_path(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = get_mock_handler()

        result = CliRunner().invoke(app_runner.app, ["preferences", "show"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("preferences.yaml", result.output)

    @patch(_HANDLER)
    def test_hints_at_set_when_a_value_is_built_in(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = get_mock_handler(_BUILT_IN_ENTRIES)

        result = CliRunner().invoke(app_runner.app, ["preferences", "show"])

        self.assertIn("jd preferences set", result.output)

    @patch(_HANDLER)
    def test_does_not_hint_when_every_value_is_recorded(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = get_mock_handler(_RECORDED_ENTRIES)

        result = CliRunner().invoke(app_runner.app, ["preferences", "show"])

        self.assertNotIn("To pin a value", result.output)

    @patch(_HANDLER)
    def test_outputs_json(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = get_mock_handler(_RECORDED_ENTRIES)

        result = CliRunner().invoke(app_runner.app, ["preferences", "show", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["path"], "/home/someone/.jupyter-deploy/preferences.yaml")
        self.assertEqual(
            payload["preferences"],
            [
                {"name": "default-template", "value": "aws:ec2:base", "source": "preferences"},
                {"name": "default-store-type", "value": "s3-ddb", "source": "preferences"},
            ],
        )

    @patch(_HANDLER)
    def test_reports_an_unreadable_file(self, mock_handler_cls: Mock) -> None:
        mock_handler = get_mock_handler()
        mock_handler.list_preferences.side_effect = ReadPreferencesError("/some/preferences.yaml", "bad yaml")
        mock_handler_cls.return_value = mock_handler

        result = CliRunner().invoke(app_runner.app, ["preferences", "show"])

        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Cannot read the preferences file", result.output)
        self.assertIn("jd preferences unset --all", result.output)


class TestPreferencesSetCommand(unittest.TestCase):
    @patch(_HANDLER)
    def test_sets_the_template(self, mock_handler_cls: Mock) -> None:
        mock_handler = get_mock_handler()
        mock_handler_cls.return_value = mock_handler

        result = CliRunner().invoke(app_runner.app, ["preferences", "set", "--default-template", "aws:ec2:base"])

        self.assertEqual(result.exit_code, 0, result.output)
        mock_handler.set_preferences.assert_called_once_with(
            default_template="aws:ec2:base",
            default_store_type=None,
        )

    @patch(_HANDLER)
    def test_sets_the_store_type(self, mock_handler_cls: Mock) -> None:
        mock_handler = get_mock_handler()
        mock_handler_cls.return_value = mock_handler

        result = CliRunner().invoke(app_runner.app, ["preferences", "set", "--default-store-type", "s3-ddb"])

        self.assertEqual(result.exit_code, 0, result.output)
        mock_handler.set_preferences.assert_called_once_with(
            default_template=None,
            default_store_type=StoreType.S3_DDB,
        )

    @patch(_HANDLER)
    def test_sets_both_in_one_call(self, mock_handler_cls: Mock) -> None:
        mock_handler = get_mock_handler()
        mock_handler_cls.return_value = mock_handler

        result = CliRunner().invoke(
            app_runner.app,
            ["preferences", "set", "--default-template", "aws:ec2:base", "--default-store-type", "s3-only"],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        mock_handler.set_preferences.assert_called_once_with(
            default_template="aws:ec2:base",
            default_store_type=StoreType.S3_ONLY,
        )

    @patch(_HANDLER)
    def test_rejects_an_unknown_store_type(self, mock_handler_cls: Mock) -> None:
        mock_handler_cls.return_value = get_mock_handler()

        result = CliRunner().invoke(app_runner.app, ["preferences", "set", "--default-store-type", "dynamodb"])

        self.assertNotEqual(result.exit_code, 0)

    @patch(_HANDLER)
    def test_requires_at_least_one_preference(self, mock_handler_cls: Mock) -> None:
        mock_handler = get_mock_handler()
        mock_handler_cls.return_value = mock_handler

        result = CliRunner().invoke(app_runner.app, ["preferences", "set"])

        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("at least one preference", result.output)
        mock_handler.set_preferences.assert_not_called()


class TestPreferencesUnsetCommand(unittest.TestCase):
    @patch(_HANDLER)
    def test_clears_the_template(self, mock_handler_cls: Mock) -> None:
        mock_handler = get_mock_handler()
        mock_handler_cls.return_value = mock_handler

        result = CliRunner().invoke(app_runner.app, ["preferences", "unset", "--default-template"])

        self.assertEqual(result.exit_code, 0, result.output)
        mock_handler.unset_preferences.assert_called_once_with([PreferenceName.DEFAULT_TEMPLATE])

    @patch(_HANDLER)
    def test_clears_both(self, mock_handler_cls: Mock) -> None:
        mock_handler = get_mock_handler()
        mock_handler_cls.return_value = mock_handler

        result = CliRunner().invoke(
            app_runner.app, ["preferences", "unset", "--default-template", "--default-store-type"]
        )

        self.assertEqual(result.exit_code, 0, result.output)
        mock_handler.unset_preferences.assert_called_once_with(
            [PreferenceName.DEFAULT_TEMPLATE, PreferenceName.DEFAULT_STORE_TYPE]
        )

    @patch(_HANDLER)
    def test_all_deletes_the_file(self, mock_handler_cls: Mock) -> None:
        mock_handler = get_mock_handler()
        mock_handler_cls.return_value = mock_handler

        result = CliRunner().invoke(app_runner.app, ["preferences", "unset", "--all"])

        self.assertEqual(result.exit_code, 0, result.output)
        mock_handler.unset_all_preferences.assert_called_once()
        mock_handler.unset_preferences.assert_not_called()
        self.assertIn("Deleted", result.output)

    @patch(_HANDLER)
    def test_all_reports_when_there_was_nothing_to_clear(self, mock_handler_cls: Mock) -> None:
        mock_handler = get_mock_handler()
        mock_handler.unset_all_preferences.return_value = False
        mock_handler_cls.return_value = mock_handler

        result = CliRunner().invoke(app_runner.app, ["preferences", "unset", "--all"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("nothing to clear", result.output)

    @patch(_HANDLER)
    def test_refuses_all_combined_with_a_specific_preference(self, mock_handler_cls: Mock) -> None:
        mock_handler = get_mock_handler()
        mock_handler_cls.return_value = mock_handler

        result = CliRunner().invoke(app_runner.app, ["preferences", "unset", "--all", "--default-template"])

        self.assertEqual(result.exit_code, 1, result.output)
        mock_handler.unset_all_preferences.assert_not_called()
        mock_handler.unset_preferences.assert_not_called()

    @patch(_HANDLER)
    def test_requires_at_least_one_preference(self, mock_handler_cls: Mock) -> None:
        mock_handler = get_mock_handler()
        mock_handler_cls.return_value = mock_handler

        result = CliRunner().invoke(app_runner.app, ["preferences", "unset"])

        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("at least one preference", result.output)
        mock_handler.unset_preferences.assert_not_called()


class TestPreferencesGroup(unittest.TestCase):
    def test_shows_help_when_called_with_no_subcommand(self) -> None:
        result = CliRunner().invoke(app_runner.app, ["preferences"])

        self.assertIn("show", result.output)
        self.assertIn("set", result.output)
        self.assertIn("unset", result.output)

    def test_is_listed_in_the_top_level_help(self) -> None:
        result = CliRunner().invoke(app_runner.app, ["--help"])

        self.assertIn("preferences", result.output)
