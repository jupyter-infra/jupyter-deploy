"""Guard the repo-level lists that enumerate the workspace packages.

Six places name every package: the uv workspace members, mypy's `files` and `mypy_path`, pytest's
`pythonpath`, the CI change detector's `LIB_PATHS`, and the README package list. Adding a package
means editing all six, and nothing fails when one is missed -- it just silently stops being covered.
`LIB_PATHS` is the costly one: a package it omits never gets linted or tested on its own, so a
dependency the package uses but never declares keeps resolving from the workspace root install and
only surfaces in that package's release workflow.

The source of truth here is the filesystem: `libs/*/pyproject.toml`.

Also guards the constants two packages must agree on by value because neither imports the other.
"""

import importlib.util
import re
import tomllib
import unittest
from pathlib import Path

from jupyter_deploy import constants as jd_constants
from jupyter_deploy.proxy import proxy_manager
from jupyter_deploy_client_proxy import constants as proxy_constants

REPO_ROOT = Path(__file__).parent.parent.parent
ROOT_PYPROJECT = REPO_ROOT / "pyproject.toml"
MODIFIED_DIRS_SCRIPT = REPO_ROOT / ".github" / "utils" / "get_modified_dirs.py"


def declared_packages() -> set[str]:
    """Return every workspace package as a repo-relative path, discovered from disk."""
    return {f"libs/{path.parent.name}" for path in REPO_ROOT.glob("libs/*/pyproject.toml")}


def root_config() -> dict:
    with open(ROOT_PYPROJECT, "rb") as f:
        return tomllib.load(f)


def declared_dependency_names(package: str) -> set[str]:
    """Return every distribution a package declares, runtime plus dependency groups.

    Runtime counts: the plugin depends on `pytest` as a real dependency, not a dev tool.
    """
    with open(REPO_ROOT / package / "pyproject.toml", "rb") as f:
        config = tomllib.load(f)

    specs = list(config.get("project", {}).get("dependencies", []))
    for group in config.get("dependency-groups", {}).values():
        specs.extend(group)

    # Strip everything after the distribution name: version specifier, extras, marker.
    return {re.split(r"[<>=!~\[;\s]", str(spec))[0].strip().lower() for spec in specs}


def lib_paths() -> list[str]:
    """Import LIB_PATHS from the CI change detector, which is not an importable package."""
    spec = importlib.util.spec_from_file_location("get_modified_dirs", MODIFIED_DIRS_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.LIB_PATHS)


class TestDeclaredPackages(unittest.TestCase):
    def test_every_package_dir_has_a_readme(self) -> None:
        for package in sorted(declared_packages()):
            self.assertTrue((REPO_ROOT / package / "README.md").is_file(), f"{package} has no README.md")

    def test_every_package_declares_its_own_lint_and_test_tooling(self) -> None:
        """`lint.yml` and `test.yml` run these from inside the package directory, where only that
        package's own dependencies are installed. A package that leans on the root dev group for one
        of them passes locally and then fails in CI with `Failed to spawn`.
        """
        required = {"mypy", "pytest", "pytest-cov", "ruff", "yamllint"}
        for package in sorted(declared_packages()):
            missing = required - declared_dependency_names(package)
            self.assertEqual(set(), missing, f"{package} does not declare {sorted(missing)}")

    def test_packages_are_discovered(self) -> None:
        # A sanity floor: if the glob silently matched nothing, every assertion below would pass.
        self.assertGreaterEqual(len(declared_packages()), 5)


class TestCiChangeDetectorLibPaths(unittest.TestCase):
    """`.github/utils/get_modified_dirs.py` decides which dirs CI lints and tests per package."""

    def test_lib_paths_match_declared_packages(self) -> None:
        self.assertEqual(sorted(declared_packages()), sorted(lib_paths()))

    def test_lib_paths_has_no_duplicates(self) -> None:
        paths = lib_paths()
        self.assertEqual(len(paths), len(set(paths)))


class TestRootPyprojectPackageLists(unittest.TestCase):
    def test_workspace_members_match_declared_packages(self) -> None:
        members = root_config()["tool"]["uv"]["workspace"]["members"]
        self.assertEqual(sorted(declared_packages()), sorted(members))

    def test_pytest_pythonpath_matches_declared_packages(self) -> None:
        pythonpath = root_config()["tool"]["pytest"]["ini_options"]["pythonpath"]
        self.assertEqual(sorted(declared_packages()), sorted(pythonpath))

    def test_mypy_files_covers_every_package(self) -> None:
        # `files` also lists non-package dirs (scripts, tests), so this is a containment check.
        files = set(root_config()["tool"]["mypy"]["files"])
        self.assertEqual(set(), declared_packages() - files)

    def test_mypy_path_covers_every_package(self) -> None:
        mypy_path = set(root_config()["tool"]["mypy"]["mypy_path"])
        self.assertEqual(set(), declared_packages() - mypy_path)

    def test_mypy_lists_name_only_real_packages(self) -> None:
        mypy = root_config()["tool"]["mypy"]
        # Entries naming a `libs/<package>` directly, as opposed to a path inside one.
        for key in ("files", "mypy_path"):
            for entry in mypy[key]:
                if re.fullmatch(r"libs/[^/]+", entry):
                    self.assertIn(entry, declared_packages(), f"mypy {key} names unknown package {entry}")


class TestReleaseInstallExtras(unittest.TestCase):
    """The post-publish check installs `<pkg><INSTALL_EXTRAS>==<version>`, so that literal has to
    name every extra the package declares -- an unlisted extra is published untested.
    """

    # release workflow -> the package it publishes
    WORKFLOWS = {
        "release-cli.yml": "libs/jupyter-deploy",
        "release-plugin.yml": "libs/pytest-jupyter-deploy",
        "release-proxy.yml": "libs/jupyter-deploy-client-proxy",
        "release-base.yml": "libs/jupyter-deploy-tf-aws-ec2-base",
        "release-jupyterlab.yml": "libs/jupyter-deploy-tf-aws-ec2-jupyterlab",
        "release-eks-oidc.yml": "libs/jupyter-deploy-tf-aws-eks-oidc",
    }

    def test_install_extras_matches_declared_extras(self) -> None:
        for workflow, package in self.WORKFLOWS.items():
            with open(REPO_ROOT / package / "pyproject.toml", "rb") as f:
                declared = set(tomllib.load(f).get("project", {}).get("optional-dependencies", {}))

            content = (REPO_ROOT / ".github" / "workflows" / workflow).read_text()
            match = re.search(r'^\s*INSTALL_EXTRAS:\s*"\[([^\]]*)\]"', content, re.MULTILINE)
            declared_in_workflow = {e.strip() for e in match.group(1).split(",") if e.strip()} if match else set()

            self.assertEqual(declared, declared_in_workflow, f"{workflow} INSTALL_EXTRAS is stale")

    def test_workflows_cover_every_publishable_package(self) -> None:
        workflows = {path.name for path in (REPO_ROOT / ".github" / "workflows").glob("release-*.yml")}
        self.assertEqual(workflows, set(self.WORKFLOWS))


class TestReadmePackageList(unittest.TestCase):
    def test_readme_links_every_package(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text()
        for package in sorted(declared_packages()):
            self.assertIn(f"(./{package}/README.md)", readme, f"README.md does not link {package}")


class TestProxyExitCodeContract(unittest.TestCase):
    """`jd` and the client proxy agree on the exit codes they exchange.

    Two numbers cross the process boundary between them: `75`, which `jd proxy connect-info` exits
    to tell a running proxy its failure was transient, and `78`, which the proxy exits to tell `jd`
    it stopped because refreshing the credential became impossible. Each side names them itself,
    because `jd` never imports the proxy package — it shells out to the console script.

    Nothing else fails if one side is changed alone, and both failures are quiet: a renumbered `75`
    turns every transient AWS error into a proxy shutdown, and a renumbered `78` turns an expired
    credential into a bare non-zero exit with no explanation for the user.
    """

    def test_retryable_exit_code_agrees(self) -> None:
        self.assertEqual(jd_constants.RETRYABLE_EXIT_CODE, proxy_constants.RETRYABLE_EXIT_CODE)

    def test_refresh_failed_exit_code_agrees(self) -> None:
        self.assertEqual(proxy_manager.PROXY_REFRESH_FAILED_EXIT_CODE, proxy_constants.REFRESH_FAILED_EXIT_CODE)

    def test_the_two_codes_are_distinct(self) -> None:
        # `jd` reads the proxy's exit code to tell a failed refresh from other exits; sharing a
        # number with the retryable signal would make those indistinguishable.
        self.assertNotEqual(proxy_constants.RETRYABLE_EXIT_CODE, proxy_constants.REFRESH_FAILED_EXIT_CODE)
