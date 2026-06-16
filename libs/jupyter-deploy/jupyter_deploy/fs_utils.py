import glob
import heapq
import os
import shutil
import stat
from pathlib import Path
from typing import Any

import pathspec
import yaml

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


def list_files_sorted(
    dir_path: Path,
    pattern: str,
    max_files: int | None = None,
    reverse: bool = True,
) -> list[Path]:
    """Return a list of file paths matching pattern in directory, sorted lexicographically.

    Uses efficient os.scandir() and heapq.nlargest() for performance with large directories.
    When max_files is specified, uses O(n log k) heap selection instead of O(n log n) full sort.

    Args:
        dir_path: Directory to scan
        pattern: Glob-style pattern (e.g., "*.log", "*.txt")
        max_files: Maximum number of files to return (None = unlimited)
        reverse: If True, return newest first (highest lexicographic value first)

    Raises:
        FileNotFoundError: If dir_path does not exist
        NotADirectoryError: If dir_path is not a directory
        ValueError: If pattern is invalid
        OSError: If directory scanning fails (e.g., permission issues)

    Example:
        # Get 100 most recent log files (assuming YYYYMMDD-HHMMSS.log naming)
        logs = list_files_sorted(Path("/logs"), "*.log", max_files=100, reverse=True)
    """
    # Validate preconditions
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory does not exist: {dir_path}")
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {dir_path}")

    # Convert glob pattern to simple suffix check (only supports "*.ext" patterns)
    if not pattern.startswith("*"):
        raise ValueError(f"Pattern must start with '*': {pattern}")
    suffix = pattern[1:]  # Remove the '*'

    # Use os.scandir() for efficient directory listing (let OSError propagate)
    entries = [entry for entry in os.scandir(dir_path) if entry.is_file() and entry.name.endswith(suffix)]

    if not entries:
        return []

    # Sort by filename lexicographically
    if max_files is not None and max_files < len(entries):
        # O(n log k) complexity - more efficient when k << n
        if reverse:
            selected_entries = heapq.nlargest(max_files, entries, key=lambda e: e.name)
        else:
            selected_entries = heapq.nsmallest(max_files, entries, key=lambda e: e.name)
    else:
        # O(n log n) complexity - sort all entries
        selected_entries = sorted(entries, key=lambda e: e.name, reverse=reverse)

    return [Path(entry.path) for entry in selected_entries]


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


def write_yaml_file_with_comments(
    file_path: Path,
    content: dict,
    key_order: list[str] | None = None,
    comments: dict[str, list[str]] | None = None,
    commented_entries: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Write dict content to disk with optional header comments and commented-out entries.

    Args:
        file_path: Target file path.
        content: Dict to serialize as YAML.
        key_order: Optional ordering for top-level keys.
        comments: Header comment lines to insert after a top-level key line.
        commented_entries: Dict of {section_key: {var: value}} rendered as
            commented-out YAML lines at the end of the section. Entries whose
            key already appears in the section's active content are skipped.
    """
    ordered_dict: dict = {}

    # First add keys in specified order
    if key_order:
        for key in key_order:
            if key in content:
                ordered_dict[key] = content[key]

    # Add any remaining keys not specified in order
    for key in content:
        if key not in ordered_dict:
            ordered_dict[key] = content[key]

    # Dump to string, then inject comments in a single pass before writing to disk
    raw_yaml = yaml.dump(ordered_dict, indent=2, sort_keys=False, default_flow_style=False)

    if not comments and not commented_entries:
        with open(file_path, "w") as f:
            f.write(raw_yaml)
        return

    # Walk the YAML lines and inject comments in a single pass.
    # Commented entries (inactive defaults) are appended AFTER the section's
    # active content so that user-set values stay at the top of each section.
    modified_lines: list[str] = []
    top_level_keys: set[str] = set(ordered_dict.keys())
    pending_commented_section: str | None = None

    def _match_top_level_key(stripped_line: str) -> str | None:
        """Return the matching top-level key if this line starts a new YAML section."""
        for key in top_level_keys:
            if stripped_line == f"{key}:" or stripped_line.startswith(f"{key}: "):
                return key
        return None

    def _flush_pending_comments() -> None:
        # `nonlocal` allows this nested function to reassign the enclosing
        # scope's variable (without it, assignment would create a new local).
        nonlocal pending_commented_section
        if pending_commented_section and commented_entries:
            entries = commented_entries.get(pending_commented_section, {})
            # Skip entries that are already active (uncommented) in the section
            active_keys = set((content.get(pending_commented_section) or {}).keys())
            inactive = {k: v for k, v in entries.items() if k not in active_keys}
            if inactive:
                modified_lines.extend(_render_commented_yaml_entries(inactive))
        pending_commented_section = None

    for line in raw_yaml.splitlines(keepends=True):
        stripped = line.strip()
        matched_key = _match_top_level_key(stripped)

        if matched_key:
            # We're entering a new section — flush any pending commented entries
            # from the previous section (they trail after the active content).
            _flush_pending_comments()

            # Blank line between top-level sections for readability
            if modified_lines:
                modified_lines.append("\n")

            modified_lines.append(line)

            # Header comments (e.g. "# fill in values below...")
            if comments and matched_key in comments:
                for comment in comments[matched_key]:
                    modified_lines.append(f"{comment}\n")

            # Remember this section so we can append commented entries at its end
            if commented_entries and matched_key in commented_entries:
                pending_commented_section = matched_key
        else:
            modified_lines.append(line)

    # Flush commented entries for the final section (no next section triggers the flush)
    _flush_pending_comments()

    with open(file_path, "w") as f:
        f.writelines(modified_lines)


def _render_commented_yaml_entries(entries: dict[str, Any]) -> list[str]:
    """Render dict entries as commented-out multi-line YAML with 2-space indent."""
    lines: list[str] = []
    for var_name, var_value in entries.items():
        single_entry = {var_name: var_value}
        raw = yaml.dump(single_entry, indent=2, sort_keys=False, default_flow_style=False)
        for raw_line in raw.splitlines():
            lines.append(f"  # {raw_line}\n")
    return lines


def write_yaml_reference_file(file_path: Path, content: dict[str, Any], header: str | None = None) -> None:
    """Write a simple YAML reference file with an optional header comment."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w") as f:
        if header:
            f.write(f"# {header}\n")
        if content:
            yaml.dump(content, f, indent=2, sort_keys=False, default_flow_style=False)


def read_yaml_reference_file(file_path: Path) -> dict[str, Any]:
    """Read a YAML reference file. Returns empty dict if file doesn't exist or is invalid."""
    if not file_path.exists():
        return {}
    with open(file_path) as f:
        result = yaml.safe_load(f)
    if not isinstance(result, dict):
        return {}
    return result


def walk_local_files_with_gitignore_rules(local_path: Path, gitignore_path: Path | None = None) -> list[Path]:
    """Walk local directory and return files, respecting .gitignore patterns."""
    spec: pathspec.PathSpec | None = None
    if gitignore_path and gitignore_path.exists():
        with open(gitignore_path) as f:
            spec = pathspec.PathSpec.from_lines("gitignore", f)

    files: list[Path] = []
    for file_path in sorted(local_path.rglob("*")):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(local_path)
        if spec and spec.match_file(str(relative)):
            continue
        files.append(file_path)

    return files
