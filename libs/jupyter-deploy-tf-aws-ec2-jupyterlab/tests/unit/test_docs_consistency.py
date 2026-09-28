"""Tests that README.md and docs pages stay in sync."""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
README = REPO_ROOT / "libs" / "jupyter-deploy-tf-aws-ec2-jupyterlab" / "README.md"
DOCS_DIR = REPO_ROOT / "docs" / "source" / "templates" / "aws-ec2-jupyterlab-template"

RAW_GITHUB_PREFIX = (
    "https://raw.githubusercontent.com/jupyter-infra/jupyter-deploy/main/docs/source/templates/"
    "aws-ec2-jupyterlab-template/"
)

_HEADING_RE = re.compile(r"^(#{3,6}) ")
_ADMONITION_RE = re.compile(r"```\{(note|warning|important|tip)\}\n(.*?)\n```", re.DOTALL)


def _promote_headings(line: str) -> str:
    """Promote headings h3–h6 by one level (### -> ##, #### -> ###, etc.).

    Leaves h1 and h2 unchanged so both README (### under ##) and docs
    (## at top level) normalize to the same depth.
    """
    if _HEADING_RE.match(line):
        return line[1:]
    return line


def _admonitions_to_blockquotes(text: str) -> str:
    """Rewrite MyST admonitions as the `> **Kind:** ...` blockquotes PyPI can render.

    The docs use fenced MyST admonitions (```{note}), which PyPI and GitHub display as
    raw code blocks, so the README carries the same text as a blockquote instead.
    """

    def _to_blockquote(match: re.Match[str]) -> str:
        kind = match.group(1).capitalize()
        lines = match.group(2).strip("\n").splitlines()
        return "\n".join([f"> **{kind}:** {lines[0]}"] + [f"> {line}" for line in lines[1:]])

    return _ADMONITION_RE.sub(_to_blockquote, text)


def _normalize(text: str) -> str:
    """Normalize markdown for comparison.

    - Convert MyST admonitions to blockquotes
    - Promote all headings by one level (### -> ##, #### -> ###, etc.)
    - Replace absolute GitHub raw image URLs with relative paths
    - Strip trailing whitespace on each line
    """
    lines = _admonitions_to_blockquotes(text.strip()).splitlines()
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


def _extract_lines_between(text: str, after: str, before: str | None) -> str:
    """Extract lines between two heading markers (exclusive); `before=None` reads to the end."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if start is None and line.strip() == after:
            start = i + 1
            continue
        if start is not None and before is not None and line.strip() == before:
            return "\n".join(lines[start:i])
    if start is not None:
        return "\n".join(lines[start:])
    raise ValueError(f"Could not find range between {after!r} and {before!r}")


class TestReadmeDocsConsistency(unittest.TestCase):
    """Verify that duplicated content between README.md and docs pages stays in sync."""

    readme: str
    index_md: str
    prerequisites_md: str
    user_guide_md: str
    architecture_md: str
    details_md: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.readme = README.read_text()
        cls.index_md = (DOCS_DIR / "index.md").read_text()
        cls.prerequisites_md = (DOCS_DIR / "prerequisites.md").read_text()
        cls.user_guide_md = (DOCS_DIR / "user-guide.md").read_text()
        cls.architecture_md = (DOCS_DIR / "architecture.md").read_text()
        cls.details_md = (DOCS_DIR / "details.md").read_text()

    def _assert_in_sync(self, readme_section: str, doc_section: str, page: str) -> None:
        self.assertEqual(
            _normalize(readme_section),
            _normalize(doc_section),
            f"README.md drifted from docs {page}",
        )

    def test_header_description(self) -> None:
        """The opening description must match between README and index.md."""
        self._assert_in_sync(
            _extract_lines_between(self.readme, "# Jupyter Deploy AWS EC2 JupyterLab template", "## 10k View"),
            _extract_lines_between(self.index_md, "# AWS EC2 JupyterLab Template", "## 10k View"),
            "index.md",
        )

    def test_10k_view(self) -> None:
        """The 10k View section must match between README and index.md."""
        self._assert_in_sync(
            _extract_lines_between(self.readme, "## 10k View", "## Prerequisites"),
            _extract_lines_between(self.index_md, "## 10k View", "## Next Steps"),
            "index.md",
        )

    def test_prerequisites_section(self) -> None:
        """Prerequisites must match between README and prerequisites.md."""
        self._assert_in_sync(
            _extract_lines_between(self.readme, "## Prerequisites", "## Usage"),
            _extract_lines_between(self.prerequisites_md, "# Prerequisites", None),
            "prerequisites.md",
        )

    def test_user_guide_section(self) -> None:
        """Usage must match between README and user-guide.md."""
        self._assert_in_sync(
            _extract_lines_between(self.readme, "## Usage", "## Architecture"),
            _extract_lines_between(self.user_guide_md, "# User Guide", None),
            "user-guide.md",
        )

    def test_architecture_section(self) -> None:
        """The Architecture section must match between README and architecture.md."""
        self._assert_in_sync(
            _extract_lines_between(self.readme, "## Architecture", "## Details"),
            _extract_lines_between(self.architecture_md, "# Architecture", None),
            "architecture.md",
        )

    def test_details_section(self) -> None:
        """The Details section must match between README and details.md."""
        self._assert_in_sync(
            _extract_lines_between(self.readme, "## Details", "## License"),
            _extract_lines_between(self.details_md, "# Details", None),
            "details.md",
        )

    def test_readme_has_no_myst_admonitions(self) -> None:
        """PyPI cannot render MyST admonitions; the README must use blockquotes instead."""
        self.assertIsNone(_ADMONITION_RE.search(self.readme), "README.md contains a MyST admonition")

    def test_license_link(self) -> None:
        """Both README and index.md must reference the MIT License."""
        mit_pattern = re.compile(r"\bMIT License\b", re.IGNORECASE)
        self.assertTrue(mit_pattern.search(self.readme), "README.md is missing MIT License reference")
        self.assertTrue(mit_pattern.search(self.index_md), "docs index.md is missing MIT License reference")
