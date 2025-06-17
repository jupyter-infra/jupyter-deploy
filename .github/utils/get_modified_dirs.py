import sys
import subprocess
import json

# Update this for any new packages/libs we want checked
LIB_PATHS = [
    "libs/jupyter-deploy",
    "libs/jupyter-deploy-tf-aws-ec2-ngrok",
    "libs/jupyter-deploy-tf-aws-ec2-base",
    "images/uvbase",
]


def get_file_diff(base_ref: str) -> list:
    """Return list of files changed in the current branch compared to base_ref."""
    if base_ref:
        cmd = ["git", "diff", "--name-only", base_ref]
    else:
        # If no base branch ref (i.e. pushing to main), return everything
        cmd = ["git", "ls-files"]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error getting changed files: {result.stderr}")
        sys.exit(1)

    return result.stdout.strip().split("\n")


def get_updated_pkgs(file_diff: list) -> list:
    """Return list of packages with updated/new files."""
    lib_dirs = set()
    root_changed = False

    for file in file_diff:
        if not file:
            continue

        lib_match = False
        for lib_path in LIB_PATHS:
            if file.startswith(f"{lib_path}/"):
                lib_dirs.add(lib_path)
                lib_match = True
                break

        if not lib_match:
            root_changed = True
            break

    if root_changed or not lib_dirs:
        return ["."]

    return list(lib_dirs)


def main():
    base_ref = sys.argv[1] if len(sys.argv) > 1 else None

    file_diff = get_file_diff(base_ref)

    updated_dirs = get_updated_pkgs(file_diff)

    print(json.dumps(updated_dirs))


if __name__ == "__main__":
    main()
