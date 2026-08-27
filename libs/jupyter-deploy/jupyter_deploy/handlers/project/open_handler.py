import socket
import webbrowser
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from jupyter_deploy.connection_utils import https_connection, resolve_ips
from jupyter_deploy.engine.engine_open import EngineOpenHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.engine.supervised_execution import DisplayManager, NullDisplay
from jupyter_deploy.engine.terraform import tf_open, tf_variables
from jupyter_deploy.enum import OpenMode
from jupyter_deploy.exceptions import (
    DetachedNotSupportedError,
    OpenWebBrowserError,
    UrlNotAvailableError,
    UrlNotSecureError,
)
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.provider import manifest_command_runner as cmd_runner
from jupyter_deploy.provider.resolved_clidefs import ResolvedCliParameter, StrResolvedCliParameter
from jupyter_deploy.proxy.proxy_manager import ProxyManager


@dataclass
class OpenHealthResult:
    url: str
    healthy: bool
    detail: str


def _is_secure_open_url(url: str) -> bool:
    """Return True if the URL is safe for `jd open` to launch in a browser.

    Safe = HTTPS (encrypted in transit) or an http loopback URL (never leaves the machine,
    so no in-transit exposure). Loopback is what the ec2-jupyterlab template uses: the
    browser talks to the local proxy on http://127.0.0.1:PORT, and the proxy handles TLS
    to the remote instance.
    """
    if url.startswith("https://"):
        return True
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "http":
        return False
    return (parsed.hostname or "").lower() in ("localhost", "127.0.0.1")


class OpenHandler(BaseProjectHandler):
    _handler: EngineOpenHandler

    def __init__(self, display_manager: DisplayManager | None = None) -> None:
        """Base class to manage the open command of a jupyter-deploy project."""
        super().__init__(display_manager=display_manager or NullDisplay())

        # Set when open() drives a proxy-mode template; wait() blocks on its foreground proxy.
        self._proxy: ProxyManager | None = None
        self._proxy_detached = False

        if self.engine == EngineType.TERRAFORM:
            self._handler = tf_open.TerraformOpenHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
            )
            self._variable_handler = tf_variables.TerraformVariablesHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
                display_manager=self.display_manager,
            )
        else:
            raise NotImplementedError(f"OpenHandler implementation not found for engine: {self.engine}")

    def _resolve_scope(self, scope: str | None) -> str:
        output_handler = self._handler.output_handler
        if scope:
            return scope
        try:
            scope_def = output_handler.get_declared_output_def("server_default_scope", StrTemplateOutputDefinition)
            if scope_def.value:
                return scope_def.value
        except (NotImplementedError, KeyError, ValueError):
            pass
        return "default"

    def get_url(self) -> str:
        """Return the URL to access the Jupyter app.

        Raises:
            UrlNotAvailableError: If URL cannot be retrieved or is empty
        """
        return self._handler.get_url()

    def get_server_url(self, name: str, scope: str | None = None) -> str:
        """Resolve and return the URL for a specific server.

        Runs the open.server manifest command which fetches the server resource
        and extracts the access URL from it.

        Raises:
            CommandNotImplementedError: If open.server is not in the manifest
            ResourceNotFoundError: If the server does not exist
            UrlNotAvailableError: If the server has no access URL
        """
        resolved_scope = self._resolve_scope(scope)
        command = self.project_manifest.get_command("open.server")
        output_handler = self._handler.output_handler
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=output_handler,
            variable_handler=self._variable_handler,
        )
        cli_paramdefs: dict[str, ResolvedCliParameter[Any]] = {
            "name": StrResolvedCliParameter(parameter_name="name", value=name),
            "scope": StrResolvedCliParameter(parameter_name="scope", value=resolved_scope),
        }
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)

        try:
            url = runner.get_result_value(command, "open.server.url", str)
        except KeyError as e:
            raise UrlNotAvailableError(
                f"Could not resolve URL for server '{name}' in scope '{resolved_scope}'. Is the server running?"
            ) from e
        if not url:
            raise UrlNotAvailableError(
                f"Could not resolve URL for server '{name}' in scope '{resolved_scope}'. Is the server running?"
            )

        return url

    def open(self, name: str | None = None, scope: str | None = None, detached: bool = False) -> str:
        """Open the application or a specific server in the browser.

        Proxy-mode templates (manifest ``open: {mode: proxy}``) have no public URL: the app is
        reached through the local client proxy, whose lifecycle ``jd open`` owns. Drive a
        :class:`~jupyter_deploy.proxy.proxy_manager.ProxyManager` directly — always start a fresh
        proxy (replacing any already running), attached unless ``detached``, then open the browser
        and return the loopback URL. Call :meth:`wait` afterwards to block on an attached
        (foreground) proxy until Ctrl-C.

        Otherwise, when name is provided, resolves the server URL via the open.server manifest
        command; else falls back to the project open_url output.

        Returns:
            str: The URL that was opened

        Raises:
            UrlNotAvailableError: If URL cannot be retrieved or is empty
            UrlNotSecureError: If URL is not HTTPS or an http loopback URL
            OpenWebBrowserError: If opening URL in browser fails
            CommandNotImplementedError: If name given but open.server not in manifest
            ResourceNotFoundError: If the named server does not exist
        """
        open_config = self.project_manifest.get_open()
        is_proxy_open = open_config.get_mode() == OpenMode.PROXY and name is None
        # --detached backgrounds the local proxy process, which only exists for the proxy open
        # flow; reject it elsewhere rather than silently ignoring it.
        if detached and not is_proxy_open:
            raise DetachedNotSupportedError()
        if is_proxy_open:
            self._proxy = ProxyManager.for_project(self.project_path, self.display_manager)
            self._proxy_detached = detached
            # jd open owns the proxy lifecycle: replace any running proxy with a fresh one. A
            # single spinner covers the whole interaction; the manager narrates each phase
            # (stopping existing / starting / waiting to bind / polling the app) onto it.
            with self.display_manager.spinner("Preparing the local proxy …"):
                self._proxy.restart(detached=detached)
                return self._proxy.open(path=open_config.path)

        url = self.get_url() if name is None else self.get_server_url(name, scope)

        if not _is_secure_open_url(url):
            raise UrlNotSecureError(
                "Insecure URL detected. Only HTTPS or http loopback URLs are allowed for security reasons.",
                url,
            )

        open_status = webbrowser.open(url, new=2)
        if not open_status:
            raise OpenWebBrowserError("Failed to open URL in browser.", url)

        return url

    def wait(self) -> None:
        """Print the proxy-lifecycle hint, then block on a foreground proxy; no-op otherwise.

        Public-URL templates never start a proxy, so this returns immediately. For a detached
        proxy (``jd open -d``) it prints where to stop it and returns; for a foreground proxy it
        prints the Ctrl-C hint and blocks until the proxy is interrupted.
        """
        if self._proxy is None:
            return
        if self._proxy_detached:
            self.display_manager.hint("The proxy keeps running in the background. Stop it with: jd proxy stop")
        else:
            self.display_manager.hint("Interrupt this command (Ctrl-C) to stop the proxy.")
        self._proxy.wait_foreground()

    def health(self, expected_status_code: int = 200, port: int = 443) -> OpenHealthResult:
        """Check connection: DNS resolution and HTTP ping.

        Args:
            expected_status_code: The HTTP status code that indicates healthy.
            port: The port to use for DNS resolution check.

        Raises:
            UrlNotAvailableError: If URL cannot be retrieved.
        """
        url = self.get_url()
        domain = urlparse(url).hostname or ""

        try:
            resolved_ips = resolve_ips(domain, port)
        except (socket.gaierror, ValueError) as e:
            return OpenHealthResult(url=url, healthy=False, detail=f"{domain} does not resolve: {e}")

        try:
            path = urlparse(url).path or "/"
            with https_connection(domain, port) as conn:
                conn.request("GET", path)
                status_code = conn.getresponse().status
        except Exception as e:
            return OpenHealthResult(
                url=url, healthy=False, detail=f"{domain} -> {', '.join(resolved_ips)}, unreachable: {e}"
            )

        healthy = status_code == expected_status_code
        if healthy:
            detail = f"{domain} -> {', '.join(resolved_ips)}, status={status_code}"
        else:
            detail = f"{domain} -> {', '.join(resolved_ips)}, status={status_code} (expected {expected_status_code})"

        return OpenHealthResult(url=url, healthy=healthy, detail=detail)
