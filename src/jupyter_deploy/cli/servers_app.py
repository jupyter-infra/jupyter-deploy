import typer

servers_app = typer.Typer(
    help=("""Discover, start, stop or exec into server deployed to infrastructure controlled by your IaC templates.""")
)


@servers_app.command()
def list() -> None:
    """List servers running Jupyter notebooks from various Cloud Providers."""
    pass


@servers_app.command()
def describe() -> None:
    """Describe a server running a Jupyter notebook process."""
    pass
