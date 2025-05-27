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
Use `uv` to manage your virtual environment, and interact directly with the library:
> uv run python -c "import jupyter_deploy; print(jupyter_deploy.hello())"

Or use the CLI by running `jupyter-deploy --help`

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

To check that you have run formatting, run:
```
uv run --script scripts/verify_format.py
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
