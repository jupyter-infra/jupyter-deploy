import glob
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


def file_exists(file_path: Path) -> bool:
    """Return True if the provided path exists and corresponds to a file."""
    return file_path.exists() and file_path.is_file()


def delete_file_if_exists(file_path: Path) -> bool:
    """If path exists, unlinks and return True, else return False."""
    if not file_path.exists():
        return False

    file_path.unlink(missing_ok=True)
    return True


def write_inline_file_content(file_path: Path, lines: list[str]) -> None:
    """Write file as separate lines."""
    with open(file_path, "w+") as f:
        f.writelines(lines)


def find_matching_filenames(dir_path: Path, file_pattern: str) -> list[str]:
    """Return a list of file names which match the pattern in the target dir."""

    path_pattern = dir_path / file_pattern
    matching_filepaths = glob.glob(f"{path_pattern.absolute()}")

    valid_filenames = []
    for file_path_str in matching_filepaths:
        filename = Path(file_path_str).name
        valid_filenames.append(filename)

    return valid_filenames


def read_short_file(file_path: Path, max_size_mb: float = 1.0) -> str:
    """Return the content of the file.

    Raises:
        FileNotFoundError if the path does not exist.
        IsADirectoryError if the path does not correspond to a file.
        RuntimeError if the file size exceeds the limit.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Invalid file path: {file_path.absolute()} does not exist.")
    if not file_path.is_file():
        raise IsADirectoryError(f"Invalid file path: {file_path.absolute()} is not file.")

    file_stats = file_path.stat()
    file_size_bytes = file_stats.st_size

    if file_size_bytes > int(max_size_mb * 1024 * 1024):
        raise RuntimeError(f"File size at path '{file_path.absolute()}' is too large.")

    with file_path.open("r") as f:
        return f.read()
