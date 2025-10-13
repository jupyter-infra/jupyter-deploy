# Contributing guidelines
-----

## Project setup
This project leverages [uv](https://docs.astral.sh/uv/getting-started/) to manage dependencies,
run tools such as linter, type-checker, testing, or publishing.
The monorepo contains multiple packages managed as a `uv` [workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/).

Fork and clone the repository to your local workspace, then install `uv`.

```bash
# Use the sync command to create your python virtual environment,
# download the dependencies and install all packages
uv sync
```

You should see a `.venv` directory under the root of the project.

## Interact with the library
```bash
# Activate the virtual environment
source .venv/bin/activate

# Verify the CLI installation with
jupyter-deploy --help
```

## Run tools
This project uses:
1. [ruff](https://docs.astral.sh/ruff/) for linting, formatting and import sorting
2. [mypy](https://mypy-lang.org/) for type checking enforcement
3. [pytest](https://docs.pytest.org/en/stable/) to run unit and integration tests

You can access each tool with the `uv` commands.

### Lint your code
```bash
# Run the linter
uv run ruff check

# You can attempt to fix linter issues
uv run ruff check --fix
```

### Format your code
`ruff` is a code formatter in addition to a linter

```bash
# Format the code before raising a pull request
uv run ruff format

# When contributing HCL files (.tf), run terraform formatting
terraform fmt -write=true -recursive
```

### Verify formatting
```bash
# Check that you have formatted your Python code
uv run --script scripts/verify_format.py

# and your HCL files
terraform fmt -check -recursive
```

### Enforce type checking
```bash
uv run mypy
```

### Run unit tests
```bash
uv run pytest
```

### Run integration tests
To be added
