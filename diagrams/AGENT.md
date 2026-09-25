# Diagrams

Architecture diagrams written in [d2](https://d2lang.com/), compiled to SVG.

## Structure

- `diagrams/<template>/` — d2 source files, one per diagram
- `diagrams/shared/icons/` — SVG icons shared across diagrams

Compiled SVGs are output to `docs/source/templates/<template-docs-dir>/diagrams/`.
The mapping is defined in the `docs-diagrams` justfile recipe.

## Compiling diagrams

From the repo root: `just docs-diagrams`

This compiles all `.d2` files and writes SVGs to the mapped docs directories.

## Where diagrams are used

- **Docs site**: referenced with relative paths (e.g. `diagrams/overview.svg`)
- **README on PyPI/GitHub**: referenced with absolute GitHub raw URLs, e.g.
  `https://raw.githubusercontent.com/jupyter-infra/jupyter-deploy/main/docs/source/templates/aws-base-template/diagrams/overview.svg`

A unit test per template (`libs/<template-package>/tests/unit/test_docs_consistency.py`)
verifies that diagram references stay in sync between the README and docs pages.

## Adding icons

1. Place the SVG in `diagrams/shared/icons/`
2. Add an attribution row in `diagrams/shared/icons/ATTRIBUTION.md`
3. Reference the icon in d2 with `icon: ../../shared/icons/<name>.svg`

Most icons come from [simple-icons](https://github.com/simple-icons/simple-icons) (CC0 1.0).
Ensure each icon has an open-license (MIT, CC0, etc), or ask the user to confirm. 
Add ATTRIBUTION.md for per-icon license details.

## Adding a new diagram

1. Create a `.d2` file in the appropriate `diagrams/<template>/` directory
2. If the template is new, add an output mapping in the `docs-diagrams` justfile recipe
3. Run `just docs-diagrams` to compile
4. Reference the SVG in the docs page (relative path) and README (absolute GitHub raw URL)
