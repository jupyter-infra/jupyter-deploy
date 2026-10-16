"""Guard the `cli` E2E marker against the same test landing in several template suites.

The CLI release gate (`e2e-cli.yml`) runs every template's `cli`-marked tests to catch regressions
in the CLI itself. A generic CLI path (`jd init` rendering AGENT.md, `jd volume list`, ...) behaves
the same for every template, so it needs gating once; a copy in a second suite only re-tests it
against another deployment. Template suites copy test files from each other, so a test keeps its
name when it is duplicated -- which is what this checks. A template's own copy can stay, unmarked:
its release gate and canary run every non-mutating test anyway.

Matching on names is a proxy for "same CLI path": a renamed copy slips through, and two genuinely
different tests that happen to share a name must be renamed to pass.
"""

import ast
import unittest
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
CLI_MARKER = "pytest.mark.cli"


def _marks(node: ast.expr) -> list[str]:
    """Return the marker expressions in a decorator or a `pytestmark` value (single or list)."""
    elements = node.elts if isinstance(node, ast.List | ast.Tuple) else [node]
    return [ast.unparse(element) for element in elements]


def cli_marked_tests(e2e_dir: Path) -> set[str]:
    """Return the names of the module-level test functions in `e2e_dir` that carry the `cli` marker."""
    names = set()
    for path in sorted(e2e_dir.glob("test_*.py")):
        module = ast.parse(path.read_text())
        module_marked = any(
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets)
            and CLI_MARKER in _marks(node.value)
            for node in module.body
        )
        for node in module.body:
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
                continue
            decorators = [mark for decorator in node.decorator_list for mark in _marks(decorator)]
            if module_marked or CLI_MARKER in decorators:
                names.add(node.name)
    return names


class TestCliMarkerUniqueness(unittest.TestCase):
    def test_suites_are_discovered(self) -> None:
        suites = list(REPO_ROOT.glob("libs/*/tests/e2e"))
        self.assertGreater(len(suites), 1, "Expected several E2E suites under libs/*/tests/e2e")

    def test_no_cli_test_name_is_shared_across_suites(self) -> None:
        owners: dict[str, list[str]] = defaultdict(list)
        for e2e_dir in sorted(REPO_ROOT.glob("libs/*/tests/e2e")):
            for name in cli_marked_tests(e2e_dir):
                owners[name].append(e2e_dir.parent.parent.name)

        shared = {name: suites for name, suites in owners.items() if len(suites) > 1}
        self.assertEqual(
            shared,
            {},
            "These cli-marked tests exist in several suites; keep the `cli` marker on one copy only "
            "(generic CLI paths belong to the base template suite):\n"
            + "\n".join(f"  {name}: {', '.join(suites)}" for name, suites in sorted(shared.items())),
        )
