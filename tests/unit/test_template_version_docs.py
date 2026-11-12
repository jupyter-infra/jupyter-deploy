"""Guard the Terraform and provider version tables in the template docs against drift from the code.

Each template's `engine/main.tf` declares its `required_version` and `required_providers`; the docs
repeat them in `| Name | Version |` tables under a `Requirements` or `Providers` heading. Nothing ties
the two together, so a bumped constraint silently leaves the docs behind.

The source of truth is `engine/main.tf`: a constraint it does not declare must not be documented, and
every constraint it declares must be. Tables with other columns (e.g. `| Name | Purpose |`) are not
version tables and are skipped.
"""

import re
import tempfile
import unittest
from pathlib import Path

import hcl2  # type: ignore[import-untyped]
from jupyter_deploy.engine.terraform.tf_varfiles import strip_hcl2_quotes

REPO_ROOT = Path(__file__).parent.parent.parent
TEMPLATES_DOCS = REPO_ROOT / "docs" / "source" / "templates"

# Every template package, mapped to the docs that carry its version tables.
VERSION_DOCS: dict[str, list[Path]] = {
    "jupyter-deploy-tf-aws-ec2-base": [
        REPO_ROOT / "libs" / "jupyter-deploy-tf-aws-ec2-base" / "README.md",
        TEMPLATES_DOCS / "aws-base-template" / "details.md",
    ],
    "jupyter-deploy-tf-aws-ec2-jupyterlab": [
        REPO_ROOT / "libs" / "jupyter-deploy-tf-aws-ec2-jupyterlab" / "README.md",
        TEMPLATES_DOCS / "aws-ec2-jupyterlab-template" / "details.md",
    ],
    "jupyter-deploy-tf-aws-eks-oidc": [
        TEMPLATES_DOCS / "aws-eks-oidc-template" / "details.md",
    ],
    "jupyter-infra-tf-aws-iam-ci": [
        REPO_ROOT / "libs" / "jupyter-infra-tf-aws-iam-ci" / "README.md",
    ],
}

_HEADING_RE = re.compile(r"^#{1,6} (.+)$")
_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")
VERSION_TABLE_HEADINGS = ("Requirements", "Providers")


def template_main_tfs() -> dict[str, Path]:
    """Return each template package's `engine/main.tf`, keyed by package directory name."""
    return {path.parents[3].name: path for path in sorted(REPO_ROOT.glob("libs/*/*/template/engine/main.tf"))}


def declared_constraints(main_tf: Path) -> dict[str, str]:
    """Return the version constraints `main_tf` declares, under `terraform` for `required_version`."""
    with open(main_tf) as f:
        parsed = hcl2.load(f)
    constraints: dict[str, str] = {}
    for block in parsed.get("terraform", []):
        if "required_version" in block:
            constraints["terraform"] = strip_hcl2_quotes(block["required_version"])
        for providers in block.get("required_providers", []):
            for name, raw_spec in providers.items():
                # python-hcl2 v8 keeps comments under dunder keys such as `__inline_comments__`
                if name.startswith("__"):
                    continue
                # strip only the spec: strip_hcl2_quotes would turn the `null` provider's name into None
                spec = strip_hcl2_quotes(raw_spec)
                if "version" not in spec:
                    raise ValueError(f"{main_tf}: provider `{name}` declares no `version` constraint")
                constraints[name] = spec["version"]
    return constraints


def version_tables(text: str) -> dict[str, dict[str, str]]:
    """Return the `| Name | Version |` table under each Requirements/Providers heading, keyed by heading.

    A table ends at the first line that is not a table row. Lines inside code fences are ignored.
    """
    tables: dict[str, dict[str, str]] = {}
    heading = ""
    rows: dict[str, str] | None = None
    in_table = False
    in_fence = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not line.startswith("|"):
            in_table = False
            rows = None
            if m := _HEADING_RE.match(line):
                heading = m.group(1).strip()
            continue
        if heading not in VERSION_TABLE_HEADINGS:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not in_table:
            # first row of a table: its header decides whether it is a version table
            in_table = True
            if cells == ["Name", "Version"]:
                if heading in tables:
                    raise ValueError(f"several `| Name | Version |` tables under the `{heading}` heading")
                rows = tables[heading] = {}
            continue
        if rows is None or all(_SEPARATOR_CELL_RE.match(cell) for cell in cells):
            continue
        if len(cells) != 2:
            raise ValueError(f"`{heading}` version table row does not have 2 cells: {line!r}")
        rows[cells[0]] = cells[1]
    return tables


class TestVersionTables(unittest.TestCase):
    def test_parses_aligned_separator(self) -> None:
        text = "## Requirements\n| Name | Version |\n|:---|---:|\n| aws | >= 6.0 |\n"
        self.assertEqual(version_tables(text), {"Requirements": {"aws": ">= 6.0"}})

    def test_skips_other_tables_under_same_heading(self) -> None:
        text = (
            "## Providers\n| Name | Version |\n|---|---|\n| aws | >= 6.0 |\n"
            "\n| Name | Purpose |\n|---|---|\n| aws | AWS |\n"
        )
        self.assertEqual(version_tables(text), {"Providers": {"aws": ">= 6.0"}})

    def test_rejects_second_version_table_under_same_heading(self) -> None:
        text = "## Providers\n| Name | Version |\n|---|---|\n\n| Name | Version |\n|---|---|\n"
        with self.assertRaisesRegex(ValueError, "several"):
            version_tables(text)

    def test_rejects_one_cell_row(self) -> None:
        text = "## Requirements\n| Name | Version |\n|---|---|\n| aws |\n"
        with self.assertRaisesRegex(ValueError, "2 cells"):
            version_tables(text)

    def test_ignores_code_fences(self) -> None:
        text = "## Requirements\n```\n# Providers\n| Name | Version |\n| aws | 1 |\n```\n"
        self.assertEqual(version_tables(text), {})

    def test_rejects_provider_without_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            main_tf = Path(tmp) / "main.tf"
            main_tf.write_text('terraform {\n  required_providers {\n    aws = { source = "hashicorp/aws" }\n  }\n}\n')
            with self.assertRaisesRegex(ValueError, "`aws` declares no `version`"):
                declared_constraints(main_tf)


class TestTemplateVersionDocs(unittest.TestCase):
    def test_every_template_is_mapped(self) -> None:
        self.assertEqual(
            sorted(template_main_tfs()),
            sorted(VERSION_DOCS),
            "VERSION_DOCS must list exactly the packages with a template/engine/main.tf",
        )

    def test_version_tables_match_main_tf(self) -> None:
        for package, main_tf in template_main_tfs().items():
            declared = declared_constraints(main_tf)
            providers = {name: version for name, version in declared.items() if name != "terraform"}
            for doc in VERSION_DOCS.get(package, []):
                with self.subTest(doc=str(doc.relative_to(REPO_ROOT))):
                    tables = version_tables(doc.read_text())
                    self.assertEqual(
                        tables.get("Requirements", {}),
                        declared,
                        f"{doc.name} Requirements table drifted from {main_tf.relative_to(REPO_ROOT)}",
                    )
                    self.assertEqual(
                        tables.get("Providers", providers),
                        providers,
                        f"{doc.name} Providers table drifted from {main_tf.relative_to(REPO_ROOT)}",
                    )
