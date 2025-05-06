import os
import shutil
import stat
from pathlib import Path

DEFAULT_IGNORE_PATTERNS: list[str] = []

# Calculate permissions: 0o755 (rwxr-xr-x)
# User can read, write, and execute
# Group and others can read and execute
USER_POSIX_755 = stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH


def get_default_project_path() -> Path:
    """Return the current directory of the terminal."""
    try:
        return Path.cwd() / "sandbox"
    except OSError as e:
        raise OSError("Unable to determine the current directory") from e


def is_empty_dir(path: Path) -> bool:
    """Return True if the path is a dir and is empty."""
    if not path.exists() or not path.is_dir():
        return False

    return not any(path.iterdir())


def safe_clean_directory(directory_path: Path, deleted_ok: bool = False) -> None:
    """Verify that the directory exists, then recursively deletes or files and nested dirs.

    No-op if the directory path does not exist.

    Raise:
        FileNotFoundError if the directory does not exist.
        NotADirectoryError if the path is not a directory.
    """
    if not directory_path.exists():
        if deleted_ok:
            print(f"Directory {directory_path.absolute()} does not exist.")
            return
        else:
            raise FileNotFoundError(f"Directory {directory_path.absolute()} does not exist.")

    if not directory_path.is_dir():
        raise NotADirectoryError(f"{directory_path.absolute()} is not a directory.")

    # TODO: improve to dryrun and ensure all permission will succeed
    shutil.rmtree(directory_path, ignore_errors=True)


def _copy_and_make_executable(source_path: str, dest_path: str) -> None:
    """Copy file and ensure it is executable by the owner."""
    # Copy the file with metadata
    shutil.copy2(source_path, dest_path)

    # Make dest file executable
    os.chmod(dest_path, mode=USER_POSIX_755)


def safe_copy_tree(source_path: Path, dest_path: Path, ignore: list[str] = DEFAULT_IGNORE_PATTERNS) -> None:
    """Verify that the source directory exists, recursively copies it to the target, make executable by user.

    Creates the destination dir path if they do not exist.

    Raises:
        FileNotFoundError if the source directory does not exist.
        NotADirectoryError if the source path is not a directory.
    """

    if not source_path.exists():
        raise FileNotFoundError(f"Source directory {source_path.absolute()} does not exist.")
    if not source_path.is_dir():
        raise NotADirectoryError(f"Source path {source_path.absolute()} is not a directory.")

    os.makedirs(dest_path, mode=USER_POSIX_755, exist_ok=True)

    # TODO: improve to dryrun and ensure all permission will succeed otherwise rollback
    shutil.copytree(
        src=source_path,
        dst=dest_path,
        copy_function=_copy_and_make_executable,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(*ignore),
    )
