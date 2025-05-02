# Contributing guidelines
-----

## Project setup
This project leverages [uv](https://docs.astral.sh/uv/getting-started/) to manage dependencies,
run tools such as linter, type-checker, testing, or publishing.
Fork and clone the repository to your local workspace, then install `uv`.

## Interact with the library
Use `uv` to manage your virtual environment, and interact directly with the library:
> uv run python -c "import jupyter_deploy; print(jupyter_deploy.hello())"

Or use the CLI by running `jupyter-deploy --help`

## Run tools
This project uses:
1. [ruff](https://docs.astral.sh/ruff/) for linting, formating and import sorting
2. [mypy](https://mypy-lang.org/) for type checking enforcement
3. [pytest](https://docs.pytest.org/en/stable/) to run unit and integration tests

You can access each tool with `uv` commands.

### Lint & order imports
> uv run ruff check

You can attempt to fix issues by running
> uv run ruff --fix

### Format your code
`ruff` is a code formater in addition to a linter,
do not forget to format the code before raising a pull request:
> uv run ruff format

### Enforce type checking
> uv run mypy

### Unit tests
> uv run pytest tests/unit

Or to target a specific test:
> uv run pytest tests/unit/path/to/test_file.py

### Integration tests
To be added
