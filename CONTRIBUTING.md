# Contributing guidelines
-----

## Project setup
This project leverages [uv](https://docs.astral.sh/uv/getting-started/) to manage dependencies,
run tools such as linter, type-checker, testing, or publishing.
Fork and clone the repository to your local workspace, then install `uv`.

This is a monorepo containing multiple packages managed as a uv workspace. After cloning the repository, you can simply run:

```bash
uv sync
```

This will automatically handle installation of all packages and their dependencies.

## Interact with the library
Activate the virtual env: `source .venv/bin/activate`

Then verify the CLI install with: `jupyter-deploy --help`

## Run tools
This project uses:
1. [ruff](https://docs.astral.sh/ruff/) for linting, formatting and import sorting
2. [mypy](https://mypy-lang.org/) for type checking enforcement
3. [pytest](https://docs.pytest.org/en/stable/) to run unit and integration tests

You can access each tool with `uv` commands.

### Lint & order imports
```bash
uv run ruff check
```

You can attempt to fix issues by running
```bash
uv run ruff check --fix
```

### Format your code
`ruff` is a code formatter in addition to a linter,
do not forget to format the code before raising a pull request:
```bash
uv run ruff format
```

furthermore, when contributing HCL files (.tf), run terraform formatting:
```bash
terraform fmt -write=true -recursive
```

### Verify formatting
To check that you have run formatting, run:
```bash
uv run --script scripts/verify_format.py
```

and
```bash
terraform fmt -check -recursive
```

### Enforce type checking
```bash
uv run mypy
```

### Unit tests
```bash
uv run pytest
```

### Integration tests
To be added
