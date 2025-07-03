from typing import Annotated

import typer

from jupyter_deploy import cmd_utils
from jupyter_deploy.handlers.access import team_handler

teams_app = typer.Typer(
    help=("""Control access to your jupyter app at team level."""),
    no_args_is_help=True,
)


@teams_app.command()
def add(
    teams: Annotated[list[str], typer.Argument(help="Names of the team to add to the allowlist.")],
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project."),
    ] = None,
) -> None:
    """Add team(s) to the list authorized to access the Jupyter app.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = team_handler.TeamsHandler()
        handler.add_teams(teams)


@teams_app.command()
def remove(
    teams: Annotated[list[str], typer.Argument(help="Names of the team to remove from the allowlist.")],
    project_dir: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Directory of the jupyter-deploy project."),
    ] = None,
) -> None:
    """Remove team(s) from the list authorized to access the Jupyter app.

    Run either from a jupyter-deploy project directory that you created with `jd init`;
    or pass a --path PATH to such a directory.
    """
    with cmd_utils.project_dir(project_dir):
        handler = team_handler.TeamsHandler()
        handler.remove_teams(teams)
