import json
import subprocess
import sys

# Update this for any new packages/libs we want checked.
# Kept in sync with the declared workspace packages by tests/unit/test_package_declarations.py.
LIB_PATHS = [
    "libs/jupyter-deploy",
    "libs/jupyter-deploy-client-proxy",
    "libs/jupyter-deploy-tf-aws-ec2-base",
    "libs/jupyter-deploy-tf-aws-ec2-jupyterlab",
    "libs/jupyter-deploy-tf-aws-eks-oidc",
    "libs/jupyter-infra-tf-aws-iam-ci",
    "libs/pytest-jupyter-deploy",
]


def get_file_diff(base_ref: str) -> list:
    """Return list of files changed in the current branch compared to base_ref."""
    cmd = ["git", "diff", "--name-only", base_ref]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error getting changed files: {result.stderr}")
        sys.exit(1)

    return result.stdout.strip().split("\n")


def get_updated_pkgs(file_diff: list) -> list:
    """Return the directories to lint and test: every touched package, plus the root when needed.

    A package directory and the workspace root are NOT interchangeable targets. Syncing at the root
    installs every member and every extra, so an import that a package uses but never declares still
    resolves; syncing inside the package installs only what that package declares, which is what the
    release workflows do. Linting the root alone therefore cannot catch a missing dependency
    declaration -- the package has to be checked on its own.
    """
    lib_dirs = set()
    root_changed = False

    for file in file_diff:
        if not file:
            continue

        for lib_path in LIB_PATHS:
            if file.startswith(f"{lib_path}/"):
                lib_dirs.add(lib_path)
                # The root suite guards cross-package rules over the E2E suites
                # (tests/unit/test_cli_marker_uniqueness.py), so an E2E edit has to run it too.
                if file.startswith(f"{lib_path}/tests/e2e/"):
                    root_changed = True
                break
        else:
            root_changed = True

    if root_changed or not lib_dirs:
        return ["."] + sorted(lib_dirs)

    return sorted(lib_dirs)


def main():
    base_ref = sys.argv[1] if len(sys.argv) > 1 else None

    if not base_ref:
        # Push to main. The merge commit's tree is the one the PR already ran the full per-package
        # matrix against, so re-deriving it from `git ls-files` would fan out over every package to
        # re-check what was just checked. Root only.
        print(json.dumps(["."]))
        return

    file_diff = get_file_diff(base_ref)

    updated_dirs = get_updated_pkgs(file_diff)

    print(json.dumps(updated_dirs))


if __name__ == "__main__":
    main()
