import tempfile
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.enum import PreferenceName, PreferenceSource, StoreType, TemplateSource
from jupyter_deploy.exceptions import InvalidTemplateNameError, ReadPreferencesError
from jupyter_deploy.handlers import preferences_handler
from jupyter_deploy.handlers.preferences_handler import (
    PreferencesHandler,
    get_preferences_dir,
    get_preferences_path,
    retrieve_preferences,
    write_preferences,
)
from jupyter_deploy.preferences import JupyterDeployPreferencesV1

_RETRIEVE = "jupyter_deploy.handlers.preferences_handler.retrieve_preferences"
_WRITE = "jupyter_deploy.handlers.preferences_handler.write_preferences"


@contextmanager
def _preferences_home(tmp_dir: str, create: bool = True) -> Iterator[Path]:
    """Point the preferences file at a temporary home, and yield the directory it lands in.

    The preferences file lives under the real home directory, which no test may touch, and the
    CLI reads no environment variable that would redirect it -- so relocate `Path.home` itself.
    Pass create=False to start from a machine that never saved a preference.
    """
    jd_home = Path(tmp_dir) / ".jupyter-deploy"
    if create:
        jd_home.mkdir(parents=True)
    with patch("pathlib.Path.home", return_value=Path(tmp_dir)):
        yield jd_home


class TestGetPreferencesDir(unittest.TestCase):
    @patch("pathlib.Path.home")
    def test_is_a_dot_dir_under_home(self, mock_home: Mock) -> None:
        mock_home.return_value = Path("/home/someone")

        self.assertEqual(get_preferences_dir(), Path("/home/someone/.jupyter-deploy"))

    @patch("pathlib.Path.home")
    def test_path_is_inside_the_dir(self, mock_home: Mock) -> None:
        mock_home.return_value = Path("/home/someone")

        self.assertEqual(get_preferences_path(), Path("/home/someone/.jupyter-deploy/preferences.yaml"))


class TestRetrievePreferences(unittest.TestCase):
    def test_returns_empty_when_file_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, _preferences_home(tmp_dir):
            prefs = retrieve_preferences()

        self.assertIsNone(prefs.default_template)
        self.assertIsNone(prefs.default_store_type)

    def test_returns_empty_when_file_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, _preferences_home(tmp_dir) as jd_home:
            (jd_home / "preferences.yaml").write_text("")
            prefs = retrieve_preferences()

        self.assertIsNone(prefs.default_template)

    def test_parses_recorded_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, _preferences_home(tmp_dir) as jd_home:
            (jd_home / "preferences.yaml").write_text("default-template: aws:ec2:base\ndefault-store-type: s3-ddb\n")
            prefs = retrieve_preferences()

        self.assertEqual(prefs.default_template, "aws:ec2:base")
        self.assertEqual(prefs.default_store_type, "s3-ddb")

    def test_raises_on_malformed_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, _preferences_home(tmp_dir) as jd_home:
            (jd_home / "preferences.yaml").write_text("not: a: mapping:\n")

            with self.assertRaises(ReadPreferencesError):
                retrieve_preferences()

    def test_raises_when_content_is_not_a_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, _preferences_home(tmp_dir) as jd_home:
            (jd_home / "preferences.yaml").write_text("- default-template\n")

            with self.assertRaises(ReadPreferencesError) as ctx:
                retrieve_preferences()

        self.assertIn("mapping", ctx.exception.error_msg)

    def test_raises_on_a_wrongly_typed_preference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, _preferences_home(tmp_dir) as jd_home:
            (jd_home / "preferences.yaml").write_text("default-template:\n  - aws:ec2:base\n")

            with self.assertRaises(ReadPreferencesError) as ctx:
                retrieve_preferences()

        self.assertIn("default-template", ctx.exception.error_msg)

    def test_raises_when_a_preference_cannot_be_read_from_disk(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp_dir,
            _preferences_home(tmp_dir) as jd_home,
            patch.object(preferences_handler.fs_utils, "read_short_file", side_effect=OSError("Permission denied")),
        ):
            (jd_home / "preferences.yaml").write_text("default-template: aws:ec2:base\n")

            with self.assertRaises(ReadPreferencesError) as ctx:
                retrieve_preferences()

        self.assertIn("Permission denied", ctx.exception.error_msg)

    def test_reads_a_file_with_no_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, _preferences_home(tmp_dir) as jd_home:
            (jd_home / "preferences.yaml").write_text("default-template: aws:ec2:base\n")

            prefs = retrieve_preferences()

        self.assertEqual(prefs.schema_version, 1)

    def test_refuses_a_file_from_a_later_schema_version(self) -> None:
        """A later version means a breaking change, so reading it as V1 would misread it."""
        with tempfile.TemporaryDirectory() as tmp_dir, _preferences_home(tmp_dir) as jd_home:
            (jd_home / "preferences.yaml").write_text("schema_version: 2\ndefault-template: aws:ec2:base\n")

            with self.assertRaises(ReadPreferencesError) as ctx:
                retrieve_preferences()

        self.assertIn("schema_version", ctx.exception.error_msg)

    def test_tolerates_a_file_written_by_an_older_version(self) -> None:
        """A file missing a preference this version knows about reads as that preference being unset."""
        with tempfile.TemporaryDirectory() as tmp_dir, _preferences_home(tmp_dir) as jd_home:
            (jd_home / "preferences.yaml").write_text("default-template: aws:ec2:base\n")

            prefs = retrieve_preferences()

        self.assertEqual(prefs.default_template, "aws:ec2:base")
        self.assertIsNone(prefs.default_store_type)

    def test_tolerates_a_file_written_by_a_newer_version(self) -> None:
        """A preference this version does not know about is kept, so that writing back cannot drop it."""
        with tempfile.TemporaryDirectory() as tmp_dir, _preferences_home(tmp_dir) as jd_home:
            (jd_home / "preferences.yaml").write_text("default-template: aws:ec2:base\ndefault-region: us-west-2\n")

            prefs = retrieve_preferences()
            write_preferences(prefs)
            rewritten = (jd_home / "preferences.yaml").read_text()

        self.assertEqual(prefs.default_template, "aws:ec2:base")
        self.assertIn("default-region: us-west-2", rewritten)


class TestWritePreferences(unittest.TestCase):
    def test_creates_the_directory_and_round_trips(self) -> None:
        """The dot directory does not exist on a machine that never saved a preference."""
        with tempfile.TemporaryDirectory() as tmp_dir, _preferences_home(tmp_dir, create=False) as jd_home:
            self.assertFalse(jd_home.exists())

            written_path = write_preferences(
                JupyterDeployPreferencesV1(default_template="aws:ec2:base", default_store_type="s3-only")
            )
            reread = retrieve_preferences()

            self.assertEqual(written_path, jd_home / "preferences.yaml")
            self.assertEqual(reread.default_template, "aws:ec2:base")
            self.assertEqual(reread.default_store_type, "s3-only")

    def test_omits_unset_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, _preferences_home(tmp_dir):
            written_path = write_preferences(JupyterDeployPreferencesV1(default_store_type="s3-only"))
            content = yaml.safe_load(written_path.read_text())

        self.assertEqual(content, {"schema_version": 1, "default-store-type": "s3-only"})

    def test_writes_keys_in_declared_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, _preferences_home(tmp_dir):
            written_path = write_preferences(
                JupyterDeployPreferencesV1(default_store_type="s3-only", default_template="aws:ec2:base")
            )
            keys = [line.split(":")[0] for line in written_path.read_text().splitlines() if line.strip()]

        self.assertEqual(keys, ["schema_version", "default-template", "default-store-type"])


class TestPreferencesHandlerList(unittest.TestCase):
    @patch(_RETRIEVE)
    def test_reports_built_in_template_when_unset(self, mock_retrieve: Mock) -> None:
        mock_retrieve.return_value = JupyterDeployPreferencesV1()
        handler = PreferencesHandler(display_manager=NullDisplay())

        entries = handler.list_preferences()

        self.assertEqual(entries[0].name, PreferenceName.DEFAULT_TEMPLATE)
        self.assertEqual(entries[0].value, "aws:ec2:jupyterlab")
        self.assertEqual(entries[0].source, PreferenceSource.BUILT_IN)

    @patch(_RETRIEVE)
    def test_reports_store_type_as_unset_with_no_value(self, mock_retrieve: Mock) -> None:
        mock_retrieve.return_value = JupyterDeployPreferencesV1()
        handler = PreferencesHandler(display_manager=NullDisplay())

        entries = handler.list_preferences()

        self.assertEqual(entries[1].name, PreferenceName.DEFAULT_STORE_TYPE)
        self.assertIsNone(entries[1].value)
        self.assertEqual(entries[1].source, PreferenceSource.UNSET)

    @patch(_RETRIEVE)
    def test_reports_recorded_values(self, mock_retrieve: Mock) -> None:
        mock_retrieve.return_value = JupyterDeployPreferencesV1(
            default_template="aws:ec2:base", default_store_type="s3-ddb"
        )
        handler = PreferencesHandler(display_manager=NullDisplay())

        entries = handler.list_preferences()

        self.assertEqual([e.value for e in entries], ["aws:ec2:base", "s3-ddb"])
        self.assertEqual([e.source for e in entries], [PreferenceSource.PREFERENCES] * 2)


class TestPreferencesHandlerSet(unittest.TestCase):
    @patch(_WRITE)
    @patch(_RETRIEVE)
    @patch("jupyter_deploy.template_utils.TEMPLATES", {"terraform": {"aws:ec2:base": Path("/mock/path")}})
    def test_records_template_and_store_type(self, mock_retrieve: Mock, mock_write: Mock) -> None:
        mock_retrieve.return_value = JupyterDeployPreferencesV1()
        handler = PreferencesHandler(display_manager=NullDisplay())

        handler.set_preferences(default_template="aws:ec2:base", default_store_type=StoreType.S3_DDB)

        written = mock_write.call_args.args[0]
        self.assertEqual(written.default_template, "aws:ec2:base")
        self.assertEqual(written.default_store_type, "s3-ddb")

    @patch(_WRITE)
    @patch(_RETRIEVE)
    @patch("jupyter_deploy.template_utils.TEMPLATES", {"terraform": {"aws:ec2:base": Path("/mock/path")}})
    def test_leaves_other_preferences_untouched(self, mock_retrieve: Mock, mock_write: Mock) -> None:
        mock_retrieve.return_value = JupyterDeployPreferencesV1(default_store_type="s3-only")
        handler = PreferencesHandler(display_manager=NullDisplay())

        handler.set_preferences(default_template="aws:ec2:base")

        written = mock_write.call_args.args[0]
        self.assertEqual(written.default_store_type, "s3-only")

    @patch(_WRITE)
    @patch(_RETRIEVE)
    def test_refuses_a_malformed_template_name(self, mock_retrieve: Mock, mock_write: Mock) -> None:
        mock_retrieve.return_value = JupyterDeployPreferencesV1()
        handler = PreferencesHandler(display_manager=NullDisplay())

        with self.assertRaises(InvalidTemplateNameError):
            handler.set_preferences(default_template="base")

        mock_write.assert_not_called()

    @patch(_WRITE)
    @patch(_RETRIEVE)
    @patch("jupyter_deploy.template_utils.TEMPLATES", {"terraform": {"aws:ec2:base": Path("/mock/path")}})
    def test_records_a_template_that_is_not_installed_but_warns(self, mock_retrieve: Mock, mock_write: Mock) -> None:
        mock_retrieve.return_value = JupyterDeployPreferencesV1()
        display_manager = Mock()
        handler = PreferencesHandler(display_manager=display_manager)

        handler.set_preferences(default_template="gcp:gce:lab")

        mock_write.assert_called_once()
        self.assertEqual(mock_write.call_args.args[0].default_template, "gcp:gce:lab")
        display_manager.warning.assert_called_once()
        self.assertIn("gcp:gce:lab", display_manager.warning.call_args.args[0])

    @patch(_WRITE)
    @patch(_RETRIEVE)
    @patch("jupyter_deploy.template_utils.TEMPLATES", {"terraform": {"aws:ec2:base": Path("/mock/path")}})
    def test_does_not_warn_for_an_installed_template(self, mock_retrieve: Mock, mock_write: Mock) -> None:
        mock_retrieve.return_value = JupyterDeployPreferencesV1()
        display_manager = Mock()
        handler = PreferencesHandler(display_manager=display_manager)

        handler.set_preferences(default_template="aws:ec2:base")

        display_manager.warning.assert_not_called()


class TestPreferencesHandlerUnset(unittest.TestCase):
    @patch(_WRITE)
    @patch(_RETRIEVE)
    def test_clears_only_the_named_preference(self, mock_retrieve: Mock, mock_write: Mock) -> None:
        mock_retrieve.return_value = JupyterDeployPreferencesV1(
            default_template="aws:ec2:base", default_store_type="s3-ddb"
        )
        handler = PreferencesHandler(display_manager=NullDisplay())

        handler.unset_preferences([PreferenceName.DEFAULT_TEMPLATE])

        written = mock_write.call_args.args[0]
        self.assertIsNone(written.default_template)
        self.assertEqual(written.default_store_type, "s3-ddb")

    @patch(_WRITE)
    @patch(_RETRIEVE)
    def test_clears_several_preferences(self, mock_retrieve: Mock, mock_write: Mock) -> None:
        mock_retrieve.return_value = JupyterDeployPreferencesV1(
            default_template="aws:ec2:base", default_store_type="s3-ddb"
        )
        handler = PreferencesHandler(display_manager=NullDisplay())

        handler.unset_preferences([PreferenceName.DEFAULT_TEMPLATE, PreferenceName.DEFAULT_STORE_TYPE])

        written = mock_write.call_args.args[0]
        self.assertIsNone(written.default_template)
        self.assertIsNone(written.default_store_type)

    def test_unset_all_deletes_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, _preferences_home(tmp_dir) as jd_home:
            (jd_home / "preferences.yaml").write_text("default-template: aws:ec2:base\n")
            handler = PreferencesHandler(display_manager=NullDisplay())

            deleted = handler.unset_all_preferences()

            self.assertTrue(deleted)
            self.assertFalse((jd_home / "preferences.yaml").exists())

    def test_unset_all_reports_when_there_was_no_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, _preferences_home(tmp_dir):
            handler = PreferencesHandler(display_manager=NullDisplay())

            self.assertFalse(handler.unset_all_preferences())


class TestPreferencesHandlerResolveTemplate(unittest.TestCase):
    @patch(_RETRIEVE)
    def test_composes_a_base_name_with_provider_and_infrastructure(self, mock_retrieve: Mock) -> None:
        handler = PreferencesHandler(display_manager=NullDisplay())

        resolved, source = handler.resolve_template(template="base", provider="AWS", infrastructure="ec2")

        self.assertEqual(resolved, "aws:ec2:base")
        self.assertEqual(source, TemplateSource.ARGUMENT)
        mock_retrieve.assert_not_called()

    @patch(_RETRIEVE)
    def test_takes_a_full_name_as_is(self, mock_retrieve: Mock) -> None:
        handler = PreferencesHandler(display_manager=NullDisplay())

        resolved, source = handler.resolve_template(template="AWS:EKS:oidc", provider="aws", infrastructure="ec2")

        self.assertEqual(resolved, "aws:eks:oidc")
        self.assertEqual(source, TemplateSource.ARGUMENT)
        mock_retrieve.assert_not_called()

    @patch(_RETRIEVE)
    def test_falls_back_to_the_preference(self, mock_retrieve: Mock) -> None:
        mock_retrieve.return_value = JupyterDeployPreferencesV1(default_template="aws:ec2:base")
        handler = PreferencesHandler(display_manager=NullDisplay())

        resolved, source = handler.resolve_template(template=None, provider="aws", infrastructure="ec2")

        self.assertEqual(resolved, "aws:ec2:base")
        self.assertEqual(source, TemplateSource.PREFERENCES)

    @patch(_RETRIEVE)
    def test_falls_back_to_the_built_in_default(self, mock_retrieve: Mock) -> None:
        mock_retrieve.return_value = JupyterDeployPreferencesV1()
        handler = PreferencesHandler(display_manager=NullDisplay())

        resolved, source = handler.resolve_template(template=None, provider="aws", infrastructure="ec2")

        self.assertEqual(resolved, "aws:ec2:jupyterlab")
        self.assertEqual(source, TemplateSource.BUILT_IN)

    @patch(_RETRIEVE)
    def test_raises_on_a_malformed_preference(self, mock_retrieve: Mock) -> None:
        mock_retrieve.return_value = JupyterDeployPreferencesV1(default_template="ec2:base")
        handler = PreferencesHandler(display_manager=NullDisplay())

        with self.assertRaises(InvalidTemplateNameError):
            handler.resolve_template(template=None, provider="aws", infrastructure="ec2")

    @patch(_RETRIEVE)
    def test_raises_on_a_malformed_argument(self, mock_retrieve: Mock) -> None:
        handler = PreferencesHandler(display_manager=NullDisplay())

        with self.assertRaises(InvalidTemplateNameError):
            handler.resolve_template(template="aws::base", provider="aws", infrastructure="ec2")


class TestPreferencesHandlerResolveStoreType(unittest.TestCase):
    @patch(_RETRIEVE)
    def test_prefers_the_explicit_store_type(self, mock_retrieve: Mock) -> None:
        handler = PreferencesHandler(display_manager=NullDisplay())

        self.assertEqual(handler.resolve_store_type(StoreType.S3_DDB), StoreType.S3_DDB)
        mock_retrieve.assert_not_called()

    @patch(_RETRIEVE)
    def test_falls_back_to_the_preference(self, mock_retrieve: Mock) -> None:
        mock_retrieve.return_value = JupyterDeployPreferencesV1(default_store_type="s3-ddb")
        handler = PreferencesHandler(display_manager=NullDisplay())

        self.assertEqual(handler.resolve_store_type(None), StoreType.S3_DDB)

    @patch(_RETRIEVE)
    def test_returns_none_when_nothing_is_set(self, mock_retrieve: Mock) -> None:
        mock_retrieve.return_value = JupyterDeployPreferencesV1()
        handler = PreferencesHandler(display_manager=NullDisplay())

        self.assertIsNone(handler.resolve_store_type(None))


class TestPreferencesHandlerReadsThroughFsUtils(unittest.TestCase):
    def test_reads_via_read_short_file(self) -> None:
        """The reader must go through fs_utils so its size guard applies to the preferences file too."""
        with (
            tempfile.TemporaryDirectory() as tmp_dir,
            _preferences_home(tmp_dir) as jd_home,
            patch.object(
                preferences_handler.fs_utils, "read_short_file", return_value="default-template: aws:ec2:base\n"
            ) as mock_read,
        ):
            (jd_home / "preferences.yaml").write_text("default-template: ignored\n")

            prefs = retrieve_preferences()

        mock_read.assert_called_once()
        self.assertEqual(prefs.default_template, "aws:ec2:base")
