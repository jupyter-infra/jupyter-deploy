"""Guard the `full_deployment` E2E marker against tests that merely need a live deployment.

The plugin skips `full_deployment` tests against an existing project unless --with-full-deployment
is passed, which no CI test job does: only the fresh workflows' deploy job runs a template's
`test_deployment.py` with it, right after `jd up`. A test that just needs a deployment and carries
the marker therefore never runs in CI while the run stays green -- which hid the eks-oidc namespace
and placement suites.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

ALLOWED_FILES = {"test_deployment.py"}
MARKER = re.compile(r"\bpytest\.mark\.full_deployment\b")


class TestFullDeploymentMarker(unittest.TestCase):
    def test_suites_are_discovered(self) -> None:
        suites = list(REPO_ROOT.glob("libs/*/tests/e2e"))
        self.assertGreater(len(suites), 1, "Expected several E2E suites under libs/*/tests/e2e")

    def test_marker_only_in_test_deployment(self) -> None:
        offenders = [
            str(path.relative_to(REPO_ROOT))
            for path in sorted(REPO_ROOT.glob("libs/*/tests/e2e/**/*.py"))
            if path.name not in ALLOWED_FILES and MARKER.search(path.read_text())
        ]
        self.assertEqual(
            offenders,
            [],
            "These files use `full_deployment`, which every CI test job skips; drop the marker "
            "(it is reserved for test_deployment.py):\n" + "\n".join(f"  {path}" for path in offenders),
        )
