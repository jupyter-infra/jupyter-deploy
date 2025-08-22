from typing import Annotated

import typer

from jupyter_deploy import cmd_utils
from jupyter_deploy.handlers.access import user_handler

users_app = typer.Typer(
    help=("""Control access to your jupyter app at user level."""),
    no_args_is_help=True,
)


@users_app.command()
def add(
    users: Annotated[list[str], typer.Argument(help="Name of the users to add to the allowlist.")],
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project."),
    ] = None,
) -> None:
    """Add user(s) to the list authorized to access the Jupyter app.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = user_handler.UsersHandler()
        handler.add_users(users)


@users_app.command()
def remove(
    users: Annotated[list[str], typer.Argument(help="Name of the users to remove from the allowlist.")],
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project."),
    ] = None,
) -> None:
    """Remove user(s) from the list authorized to access the Jupyter app.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = user_handler.UsersHandler()
        handler.remove_users(users)


@users_app.command()
def set(
    users: Annotated[list[str], typer.Argument(help="Names of the users to allowlist.")],
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project."),
    ] = None,
) -> None:
    """Set the list of username(s) authorized to access the Jupyter app.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = user_handler.UsersHandler()
        handler.set_users(users)


# use a cmd alias because mypy shows an 'valid-type' error if we just call the method 'list'
@users_app.command("list")
def list_users(
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project."),
    ] = None,
) -> None:
    """Show the name(s) of user(s) authorized to access the Jupyter app.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = user_handler.UsersHandler()
        users = handler.list_users()
        console = handler.get_console()

        if users:
            console.print(f"Allowlisted usernames: [bold cyan]{', '.join(users)}[/]")
        else:
            console.print("Allowlisted usernames: [bold cyan]None[/]")
