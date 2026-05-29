# Documentation

Docs are built with Sphinx + MyST Markdown and the Shibuya theme.
Source files live in `docs/source/`.

## Formatting rules

### Product names in body text

Use bold for product names in running text:
- **JupyterLab**, **Jupyter K8s**, **AWS Base Template**, **Fluent Bit**

Use plain text (no bold, no backticks) in headings and `{toctree}` entries:
- `## JupyterLab` — correct
- `## **JupyterLab**` — wrong

### CLI references

Use `jupyter-deploy` (backtick-quoted) instead of "the CLI", "this tool", etc.

### Voice

Prefer active voice over passive. For example:
- "Let's Encrypt provides the TLS certificates" — correct
- "TLS certificates are provided by Let's Encrypt" — avoid

### Headings

Never embed bold (`**`), backticks (`` ` ``), or other inline formatting in
markdown headings (`#`, `##`, `###`, etc.).

### Naming and ordering consistency

Directory names, page titles, and `nav_links` entries must match each other (e.g. `cli-reference/` dir, "CLI Reference" title).
The order of `nav_links` in `conf.py` must match the `{toctree}` order in `index.md`.

### README and docs sync

The base template README and its docs pages share content.
A unit test (`libs/jupyter-deploy-tf-aws-ec2-base/tests/unit/test_docs_consistency.py`)
enforces that they stay in sync.

Key differences the test normalizes:
- README uses `###` where docs use `##` (heading promotion)
- README uses absolute GitHub raw URLs for images; docs use relative paths

When editing content in either place, update the other to match.

## Diagrams

Refer to `diagrams/AGENT.md` for compiling diagrams, adding icons,
and the conventions for referencing SVGs in docs vs README.
