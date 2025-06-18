from pathlib import Path

import typer
import yaml
from pydantic import ValidationError
from rich import console as rich_console
from yaml.parser import ParserError
from yaml.scanner import ScannerError

from jupyter_deploy import fs_utils, manifest


class NotADictError(ValueError):
    pass


class BaseProjectHandler:
    """Abstract class responsible for identifying the type of project.

    The current working directory MUST be a jupyter-deploy directory,
    otherwise this class will raise a typer.Exit().
    """

    MANIFEST_FILENAME = "manifest.yaml"

    def __init__(self) -> None:
        """Attempts to identify the engine associated with the project."""
        self._console: rich_console.Console | None = None
        self.project_path = Path.cwd()
        manifest_path = self.project_path / BaseProjectHandler.MANIFEST_FILENAME

        try:
            project_manifest = retrieve_project_manifest(manifest_path)
        except FileNotFoundError as e:
            console = self.get_console()
            console.print(":x: The path does not correspond to a jupyter-deploy project.", style="bold red")
            console.line()
            console.print("Reason: could not find the jupyter-deploy manifest file.", style="red")
            console.print(f"Expected manifest file location: {manifest_path.absolute()}", style="red")
            console.line()
            console.print(
                "Change your working directory to a jupyter-deploy project or create one with [bold]jd init PATH[/].",
                style="red",
            )
            raise typer.Exit(1) from e
        except OSError as e:
            console = self.get_console()
            console.print(":x: Could not access the jupyter-deploy manifest.", style="bold red")
            console.line()
            console.print("Reason: OS error when reading the jupyter-deploy manifest file.", style="red")
            console.print(f"Manifest file location: {manifest_path.absolute()}", style="red")
            console.line()
            console.print(str(e))
            console.line()
            console.print("Verify your file system permissions and try again.", style="red")
            raise typer.Exit(1) from e
        except NotADictError as e:
            console = self.get_console()
            console.print(":x: The jupyter-deploy manifest is invalid.", style="bold red")
            console.line()
            console.print("Reason: expected the jupyter-deploy manifest file to parse as dict.", style="red")
            console.print(f"Attempted to read manifest file at: {manifest_path.absolute()}", style="red")
            raise typer.Exit(1) from e
        except (ParserError, ScannerError) as e:
            console = self.get_console()
            console.print(":x: The jupyter-deploy manifest is invalid.", style="bold red")
            console.line()
            console.print("Reason: cannot parse the jupyter-deploy manifest content as YAML.", style="red")
            console.print(f"Attempted to read manifest file at: {manifest_path.absolute()}", style="red")
            console.line()
            console.print(str(e))
            raise typer.Exit(1) from e
        except ValidationError as e:
            console = self.get_console()
            console.print(":x: The jupyter-deploy manifest is invalid.", style="bold red")
            console.line()
            console.print("Reason: the manifest file does not conform to the expected schema.", style="red")
            console.print(f"Attempted to read manifest file at: {manifest_path.absolute()}", style="red")
            console.line()
            console.print("Details:", style="red")
            for err in e.errors():
                console.print(err)
            raise typer.Exit(1) from e

        self.engine = project_manifest.get_engine()
        self.project_manifest = project_manifest

    def get_console(self) -> rich_console.Console:
        """Return the instance's rich console."""
        if self._console:
            return self._console
        self._console = rich_console.Console()
        return self._console


def retrieve_project_manifest(manifest_path: Path) -> manifest.JupyterDeployManifest:
    """Retrieve the type of project, verify basic requirements, return engine."""
    if not fs_utils.file_exists(manifest_path):
        raise FileNotFoundError("Missing jupyter-deploy manifest.")

    with open(manifest_path) as manifest_file:
        content = yaml.safe_load(manifest_file)

    if not isinstance(content, dict):
        raise NotADictError("Invalid manifest: jupyter-deploy manifest is not a dict.")

    return manifest.JupyterDeployManifest(**content)
