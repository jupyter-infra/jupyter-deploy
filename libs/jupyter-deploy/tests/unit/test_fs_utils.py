import unittest
from pathlib import Path
from unittest.mock import ANY, MagicMock, Mock, patch

from jupyter_deploy.fs_utils import (
    DEFAULT_IGNORE_PATTERNS,
    USER_POSIX_755,
    _copy_and_make_executable,
    get_default_project_path,
    is_empty_dir,
    safe_clean_directory,
    safe_copy_tree,
)


class TestGetDefaultProjectPath(unittest.TestCase):
    """Test cases for the get_default_project_path function."""

    @patch("pathlib.Path.cwd")
    def test_get_default_project_path(self, mock_cwd: Mock) -> None:
        """Test that get_default_project_path returns the expected path."""
        # Setup
        mock_path = Path("/some/usr/home/path")
        mock_cwd.return_value = mock_path
        expected_path = Path(mock_path) / "sandbox"

        # Execute
        result = get_default_project_path()

        # Assert
        self.assertEqual(result, expected_path)
        mock_cwd.assert_called_once()

    @patch("pathlib.Path.cwd")
    def test_get_default_project_path_error(self, mock_cwd: Mock) -> None:
        """Test that get_default_project_path raises OSError when Path.cwd raises OSError."""
        # Setup
        mock_cwd.side_effect = OSError("Test error")

        # Execute and Assert
        with self.assertRaisesRegex(OSError, "Unable to determine the current directory"):
            get_default_project_path()
        mock_cwd.assert_called_once()


class TestIsEmptyDir(unittest.TestCase):
    """Test cases for the is_empty_dir function."""

    def test_non_existent_path_return_false(self) -> None:
        """Test that is_empty_dir returns False for a non-existent path."""
        # Setup
        mock_path = MagicMock()
        mock_exists = MagicMock()
        mock_is_dir = MagicMock()
        mock_exists.return_value = False

        mock_path.exists = mock_exists
        mock_path.is_dir = mock_is_dir

        # Execute
        result = is_empty_dir(mock_path)

        # Assert
        self.assertFalse(result)
        mock_exists.assert_called_once()
        mock_is_dir.assert_not_called()

    def test_not_a_directory_return_false(self) -> None:
        """Test that is_empty_dir returns False for a path that is not a directory."""
        # Setup
        mock_path = MagicMock()
        mock_exists = MagicMock()
        mock_is_dir = MagicMock()
        mock_exists.return_value = True
        mock_is_dir.return_value = False

        mock_path.exists = mock_exists
        mock_path.is_dir = mock_is_dir

        # Execute
        result = is_empty_dir(mock_path)

        # Assert
        self.assertFalse(result)
        mock_exists.assert_called_once()
        mock_is_dir.assert_called_once()

    def test_empty_directory_return_true(self) -> None:
        """Test that is_empty_dir returns True for an empty directory."""
        # Setup
        mock_path = MagicMock()
        mock_exists = MagicMock()
        mock_is_dir = MagicMock()
        mock_iterdir = MagicMock()
        mock_exists.return_value = True
        mock_is_dir.return_value = True

        mock_iterdir.return_value = iter([])  # Empty iterator

        mock_path.exists = mock_exists
        mock_path.is_dir = mock_is_dir
        mock_path.iterdir = mock_iterdir

        # Execute
        result = is_empty_dir(mock_path)

        # Assert
        self.assertTrue(result)
        mock_exists.assert_called_once()
        mock_is_dir.assert_called_once()
        mock_iterdir.assert_called_once()

    def test_non_empty_directory_return_false(self) -> None:
        """Test that is_empty_dir returns False for a non-empty directory."""
        # Setup
        mock_path = MagicMock()
        mock_exists = MagicMock()
        mock_is_dir = MagicMock()
        mock_iterdir = MagicMock()
        mock_exists.return_value = True
        mock_is_dir.return_value = True

        mock_item = MagicMock()
        mock_iterdir.return_value = iter([mock_item])  # Non-empty iterator

        mock_path.exists = mock_exists
        mock_path.is_dir = mock_is_dir
        mock_path.iterdir = mock_iterdir

        # Execute
        result = is_empty_dir(mock_path)

        # Assert
        self.assertFalse(result)
        mock_exists.assert_called_once()
        mock_is_dir.assert_called_once()
        mock_iterdir.assert_called_once()


class TestSafeCleanDirectory(unittest.TestCase):
    """Test cases for the safe_clean_directory function."""

    def get_mocked_path(self) -> MagicMock:
        """Return the mock path."""
        mock_path = MagicMock()
        self.mock_exists = MagicMock()
        self.mock_absolute = MagicMock()
        self.mock_is_dir = MagicMock()

        self.mock_exists.return_value = True
        self.mock_absolute.return_value = Path("/from/root/some/path")
        self.mock_is_dir.return_value = True

        mock_path.exists = self.mock_exists
        mock_path.absolute = self.mock_absolute
        mock_path.is_dir = self.mock_is_dir

        return mock_path

    def test_non_existent_path_deleted_ok_false_raises_exception(self) -> None:
        """
        Test that safe_clean_directory raises FileNotFoundError
        for a non-existent path when deleted_ok is False.
        """
        # Setup
        mock_path = self.get_mocked_path()
        self.mock_exists.return_value = False

        # Execute and Assert
        with self.assertRaisesRegex(FileNotFoundError, "Directory /from/root/some/path does not exist."):
            safe_clean_directory(mock_path, deleted_ok=False)
        self.mock_exists.assert_called_once()
        self.mock_absolute.assert_called_once()
        self.mock_is_dir.assert_not_called()

    def test_non_existent_path_deleted_ok_is_no_op(self) -> None:
        """Test that safe_clean_directory does not raise for a non-existent path when deleted_ok is True."""
        # Setup
        mock_path = self.get_mocked_path()
        self.mock_exists.return_value = False

        # Execute
        safe_clean_directory(mock_path, deleted_ok=True)

        # Assert
        self.mock_exists.assert_called_once()
        self.mock_absolute.assert_called_once()
        self.mock_is_dir.assert_not_called()

    def test_not_a_directory_raises_exception(self) -> None:
        """Test that safe_clean_directory raises NotADirectoryError for a path that is not a directory."""
        # Setup
        mock_path = self.get_mocked_path()
        self.mock_is_dir.return_value = False

        # Execute and Assert
        with self.assertRaisesRegex(NotADirectoryError, "/from/root/some/path is not a directory."):
            safe_clean_directory(mock_path)

    @patch("shutil.rmtree")
    def test_valid_directory(self, mock_rmtree: Mock) -> None:
        """Test that safe_clean_directory calls shutil.rmtree for a valid directory."""
        # Setup
        mock_path = self.get_mocked_path()

        # Execute
        safe_clean_directory(mock_path)

        # Assert
        mock_rmtree.assert_called_once_with(mock_path, ignore_errors=True)


class TestCopyAndMakeExecutable(unittest.TestCase):
    """Test cases for the copy_and_make_executable function."""

    @patch("shutil.copy2")
    @patch("os.chmod")
    def test_copy_and_make_executable(self, mock_chmod: Mock, mock_copy2: Mock) -> None:
        """Test that copy_and_make_executable calls shutil.copy2 and os.chmod with the correct arguments."""
        # Setup
        source_path = "/test/source"
        dest_path = "/test/dest"

        # Execute
        _copy_and_make_executable(source_path, dest_path)

        # Assert
        mock_copy2.assert_called_once_with(source_path, dest_path)
        mock_chmod.assert_called_once_with(dest_path, mode=USER_POSIX_755)


class TestSafeCopyTree(unittest.TestCase):
    """Test cases for the safe_copy_tree function."""

    def get_mocked_src_path(self) -> MagicMock:
        """Return the mock path."""
        mock_src_path = MagicMock()
        self.mock_exists = MagicMock()
        self.mock_absolute = MagicMock()
        self.mock_is_dir = MagicMock()

        self.mock_exists.return_value = True
        self.mock_is_dir.return_value = True
        self.mock_absolute.return_value = "/from/root/some/path"

        mock_src_path.exists = self.mock_exists
        mock_src_path.is_dir = self.mock_is_dir
        mock_src_path.absolute = self.mock_absolute

        return mock_src_path

    def test_non_existent_source_path(self) -> None:
        """Test that safe_copy_tree raises FileNotFoundError for a non-existent source path."""
        # Setup
        mock_source_path = self.get_mocked_src_path()
        mock_dest_path = MagicMock()
        self.mock_exists.return_value = False

        # Execute and Assert
        with self.assertRaisesRegex(FileNotFoundError, "Source directory /from/root/some/path does not exist."):
            safe_copy_tree(mock_source_path, mock_dest_path)

        self.mock_exists.assert_called_once()
        self.mock_is_dir.assert_not_called()

    def test_source_path_not_a_directory(self) -> None:
        """Test that safe_copy_tree raises NotADirectoryError for a source path that is not a directory."""
        # Setup
        mock_source_path = self.get_mocked_src_path()
        mock_dest_path = MagicMock()
        self.mock_is_dir.return_value = False

        # Execute and Assert
        with self.assertRaisesRegex(NotADirectoryError, "Source path /from/root/some/path is not a directory."):
            safe_copy_tree(mock_source_path, mock_dest_path)

        self.mock_exists.assert_called_once()
        self.mock_is_dir.assert_called_once()

    @patch("os.makedirs")
    @patch("shutil.copytree")
    @patch("shutil.ignore_patterns")
    def test_valid_paths_calls_copytree(
        self, mock_ignore_patterns: Mock, mock_copytree: Mock, mock_makedirs: Mock
    ) -> None:
        """Test that safe_copy_tree calls os.makedirs and shutil.copytree for valid paths."""
        # Setup
        mock_source_path = self.get_mocked_src_path()
        mock_dest_path = MagicMock()

        # Execute
        safe_copy_tree(mock_source_path, mock_dest_path)

        # Assert
        mock_makedirs.assert_called_once_with(mock_dest_path, mode=USER_POSIX_755, exist_ok=True)
        mock_ignore_patterns.assert_called_with(*DEFAULT_IGNORE_PATTERNS)
        mock_copytree.assert_called_once_with(
            src=mock_source_path,
            dst=mock_dest_path,
            copy_function=_copy_and_make_executable,
            dirs_exist_ok=True,
            ignore=ANY,
        )

    @patch("os.makedirs")
    @patch("shutil.copytree")
    @patch("shutil.ignore_patterns")
    def test_valid_path_with_ignore_patterns_passes_arg(
        self, mock_ignore_patterns: Mock, mock_copytree: Mock, mock_makedirs: Mock
    ) -> None:
        """Test that safe_copy_tree passes ignore_patterns to shutil.copytree."""
        # Setup
        mock_source_path = MagicMock()
        mock_dest_path = MagicMock()
        ignore_patterns = ["*.pyc", "__pycache__"]

        # Execute
        safe_copy_tree(mock_source_path, mock_dest_path, ignore=ignore_patterns)

        # Assert
        mock_makedirs.assert_called_once()
        mock_ignore_patterns.assert_called_with(*ignore_patterns)
        mock_copytree.assert_called_once_with(
            src=mock_source_path,
            dst=mock_dest_path,
            copy_function=_copy_and_make_executable,
            dirs_exist_ok=True,
            ignore=ANY,
        )

    @patch("os.makedirs")
    @patch("shutil.copytree")
    def test_valid_path_raises_exception_when_copytree_fails(self, mock_copytree: Mock, mock_makedirs: Mock) -> None:
        """Test that safe_copy_tree passes ignore_patterns to shutil.copytree."""
        # Setup
        mock_source_path = MagicMock()
        mock_dest_path = MagicMock()

        mock_copytree.side_effect = RuntimeError("Something went wrong")

        # Execute
        with self.assertRaises(RuntimeError):
            safe_copy_tree(mock_source_path, mock_dest_path)

        # Assert
        mock_makedirs.assert_called_once()
