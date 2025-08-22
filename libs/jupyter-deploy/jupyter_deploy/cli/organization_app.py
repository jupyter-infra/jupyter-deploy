from typing import Annotated

import typer

from jupyter_deploy import cmd_utils
from jupyter_deploy.handlers.access import organization_handler

organization_app = typer.Typer(
    help=("""Control access to your jupyter app at the organization level."""),
    no_args_is_help=True,
)


@organization_app.command()
def set(
    organization: Annotated[str, typer.Argument(help="Name of the organization to allowlist.")],
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project."),
    ] = None,
) -> None:
    """Allowlist an organization to access the Jupyter app.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = organization_handler.OrganizationHandler()
        handler.set_organization(organization)


@organization_app.command()
def unset(
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project."),
    ] = None,
) -> None:
    """Remove organization-based access to the Jupyter app.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = organization_handler.OrganizationHandler()
        handler.unset_organization()


@organization_app.command()
def get(
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project."),
    ] = None,
) -> None:
    """Show the name of the organization authorized to access the Jupyter app.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = organization_handler.OrganizationHandler()
        organization = handler.get_organization()
        console = handler.get_console()

        if organization:
            console.print(f"Allowlisted organization: [bold cyan]{organization}[/]")
        else:
            console.print("Allowlisted organization: [bold cyan]None[/]")
