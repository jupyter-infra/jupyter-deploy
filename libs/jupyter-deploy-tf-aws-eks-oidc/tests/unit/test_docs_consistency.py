"""Tests that README.md and docs pages stay in sync.

The README is an abbreviated version of the docs. This test enforces that
sections duplicated verbatim between the two stay consistent. Sections that
are intentionally more detailed in the docs (inputs/outputs tables, helm
charts, architecture) are NOT tested here.

Key normalizations:
- README uses ### where docs use ## (heading promotion)
- README uses absolute GitHub raw URLs for images; docs use relative paths
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
README = REPO_ROOT / "libs" / "jupyter-deploy-tf-aws-eks-oidc" / "README.md"
DOCS_DIR = REPO_ROOT / "docs" / "source" / "templates" / "aws-eks-oidc-template"

RAW_GITHUB_PREFIX = (
    "https://raw.githubusercontent.com/jupyter-infra/jupyter-deploy/main/docs/source/templates/aws-eks-oidc-template/"
)


_HEADING_RE = re.compile(r"^(#{3,6}) ")


def _promote_headings(line: str) -> str:
    """Promote headings h3-h6 by one level (### -> ##, #### -> ###, etc.)."""
    m = _HEADING_RE.match(line)
    if m:
        return line[1:]
    return line


def _normalize(text: str) -> str:
    """Normalize markdown for comparison."""
    lines = text.strip().splitlines()
    normalized: list[str] = []
    for line in lines:
        line = line.rstrip()
        if "jupyter-deploy.readthedocs.io" in line:
            continue
        line = _promote_headings(line)
        line = line.replace(RAW_GITHUB_PREFIX, "")
        normalized.append(line)
    result = "\n".join(normalized).strip()
    return re.sub(r"\n{3,}", "\n\n", result)


_MD_HEADING_RE = re.compile(r"^(#{1,6}) ")


def _is_heading(line: str, in_fence: bool) -> re.Match[str] | None:
    if in_fence:
        return None
    return _MD_HEADING_RE.match(line)


def _extract_section(text: str, heading: str) -> str:
    """Extract a markdown section by heading (including its subsections)."""
    lines = text.splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    start = None
    in_fence = False
    for i, line in enumerate(lines):
        if line.startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.strip() == heading and start is None:
            start = i + 1
            continue
        if start is not None:
            m = _is_heading(line, in_fence)
            if m and len(m.group(1)) <= level:
                return "\n".join(lines[start:i])
    if start is not None:
        return "\n".join(lines[start:])
    raise ValueError(f"Heading {heading!r} not found")


class TestReadmeDocsConsistency(unittest.TestCase):
    """Verify that duplicated content between README.md and docs pages stays in sync."""

    readme: str
    prerequisites_md: str
    user_guide_md: str
    details_md: str
    index_md: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.readme = README.read_text()
        cls.index_md = (DOCS_DIR / "index.md").read_text()
        cls.prerequisites_md = (DOCS_DIR / "prerequisites.md").read_text()
        cls.user_guide_md = (DOCS_DIR / "user-guide.md").read_text()
        cls.details_md = (DOCS_DIR / "details.md").read_text()

    def test_prerequisites_aws_account(self) -> None:
        """AWS account subsection must match."""
        readme_sub = _extract_section(self.readme, "### AWS account")
        doc_sub = _extract_section(self.prerequisites_md, "## AWS account")
        self.assertEqual(
            _normalize(readme_sub),
            _normalize(doc_sub),
            "Prerequisites 'AWS account' drifted",
        )

    def test_prerequisites_domain(self) -> None:
        """Domain subsection must match."""
        readme_sub = _extract_section(self.readme, "### Get and register a domain")
        doc_sub = _extract_section(self.prerequisites_md, "## Get and register a domain")
        self.assertEqual(
            _normalize(readme_sub),
            _normalize(doc_sub),
            "Prerequisites 'Get and register a domain' drifted",
        )

    def test_usage_installation(self) -> None:
        """Installation subsection must match."""
        readme_sub = _extract_section(self.readme, "### Installation")
        doc_sub = _extract_section(self.user_guide_md, "## Installation")
        self.assertEqual(
            _normalize(readme_sub),
            _normalize(doc_sub),
            "Usage 'Installation' drifted between README.md and user-guide.md",
        )

    def test_usage_project_setup(self) -> None:
        """Project setup subsection must match."""
        readme_sub = _extract_section(self.readme, "### Project setup")
        doc_sub = _extract_section(self.user_guide_md, "## Project setup")
        self.assertEqual(
            _normalize(readme_sub),
            _normalize(doc_sub),
            "Usage 'Project setup' drifted between README.md and user-guide.md",
        )

    def test_details_networking(self) -> None:
        """Networking section must match."""
        readme_sub = _extract_section(self.readme, "### Networking")
        doc_sub = _extract_section(self.details_md, "## Networking")
        self.assertEqual(
            _normalize(readme_sub),
            _normalize(doc_sub),
            "Networking section drifted between README.md and details.md",
        )

    def test_inputs_table(self) -> None:
        """Inputs table must match."""
        readme_section = _extract_section(self.readme, "## Inputs")
        doc_section = _extract_section(self.details_md, "## Inputs")
        self.assertEqual(
            _normalize(readme_section),
            _normalize(doc_section),
            "Inputs table drifted between README.md and details.md",
        )

    def test_outputs_table(self) -> None:
        """Outputs table must match."""
        readme_lines = self.readme.splitlines()
        start = None
        for i, line in enumerate(readme_lines):
            if line.strip() == "## Outputs":
                start = i + 1
            elif start is not None and line.strip() == "## License":
                readme_section = "\n".join(readme_lines[start:i])
                break
        else:
            readme_section = "\n".join(readme_lines[start:]) if start else ""
        doc_section = _extract_section(self.details_md, "## Outputs")
        self.assertEqual(
            _normalize(readme_section),
            _normalize(doc_section),
            "Outputs table drifted between README.md and details.md",
        )

    def test_license_link(self) -> None:
        """Both README and index.md must reference the MIT License."""
        mit_pattern = re.compile(r"\bMIT License\b", re.IGNORECASE)
        self.assertTrue(
            mit_pattern.search(self.readme),
            "README.md is missing MIT License reference",
        )
        self.assertTrue(
            mit_pattern.search(self.index_md),
            "docs index.md is missing MIT License reference",
        )
