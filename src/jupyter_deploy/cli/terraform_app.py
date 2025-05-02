import typer

terraform_app = typer.Typer(
    help=(
        "Interact with terraform preset templates, generate set of .tf files "
        "and deploy to the Cloud provider of your choice."
    ),
    no_args_is_help=True,
)


@terraform_app.command()
def generate() -> None:
    """Write a set of terraform .tf files at the target location."""
    pass


@terraform_app.command()
def apply() -> None:
    """Call terraform apply on the .tf files at the target location."""
    pass
