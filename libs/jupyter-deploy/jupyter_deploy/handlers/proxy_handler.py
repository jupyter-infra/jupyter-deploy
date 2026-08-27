"""ProxyHandler — orchestrates the local proxy for a jupyter-deploy project.

`jd proxy` (and proxy-mode `jd open`) drive a standalone client proxy that tunnels localhost
to the project's remote host. This handler stays engine/provider-agnostic and thin:

  - ``get_connect_bundle`` runs the manifest's ``proxy.connect-info`` command through the
    generic command runner and maps its results into a :class:`ProxyConnectBundle`. Every
    cloud-specific step (endpoint resolve, cert-pin read, token mint) is declared in the
    manifest and executed by the provider instruction runners — this handler never imports a
    cloud SDK.
  - process lifecycle (``start`` / ``open`` / ``stop`` / ``status`` / ``show``) is delegated to a
    private :class:`~jupyter_deploy.proxy.proxy_manager.ProxyManager` (runtime-directory layout +
    subprocess orchestration, no manifest/engine dependency). The manager is an implementation
    detail — callers use the handler's own verbs, never reach through it. (``jd open`` builds its
    own manager directly via ``ProxyManager.for_project`` rather than routing through this handler.)
"""

from __future__ import annotations

from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.engine_variables import EngineVariablesHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.supervised_execution import DisplayManager, NullDisplay
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.exceptions import CommandNotImplementedError
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.handlers.payloads import ProxyConnectBundle, ProxyStatus
from jupyter_deploy.handlers.resource.resource_utils import collect_results
from jupyter_deploy.manifest import PROXY_CONNECT_INFO_COMMAND
from jupyter_deploy.provider import manifest_command_runner as cmd_runner
from jupyter_deploy.proxy.proxy_manager import ProxyManager


class ProxyHandler(BaseProjectHandler):
    """Orchestrator for the local proxy of a jupyter-deploy project."""

    _outputs_handler: EngineOutputsHandler
    _variable_handler: EngineVariablesHandler

    def __init__(self, display_manager: DisplayManager | None = None) -> None:
        """Instantiate the proxy handler.

        Raises:
            CommandNotImplementedError: If the template does not support the proxy (declares no
                ``proxy.connect-info`` command) — so every ``jd proxy`` command fails fast and
                uniformly on templates without proxy support.
        """
        super().__init__(display_manager=display_manager or NullDisplay())

        if not self.project_manifest.supports_proxy():
            raise CommandNotImplementedError(PROXY_CONNECT_INFO_COMMAND)

        if self.engine == EngineType.TERRAFORM:
            self._outputs_handler = tf_outputs.TerraformOutputsHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
            )
            self._variable_handler = tf_variables.TerraformVariablesHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
                display_manager=self.display_manager,
            )
        else:
            raise NotImplementedError(f"ProxyHandler implementation not found for engine: {self.engine}")

        self._manager = ProxyManager.for_project(self.project_path, self.display_manager)

    # ------------------------------------------------------------------ connect-info

    def get_connect_bundle(self) -> ProxyConnectBundle:
        """Run the manifest connect-info command and return the connection bundle.

        connect-info has no network side effect: it resolves the instance endpoint, reads the
        pinned cert, and mints the token. The security boundary is the STS-identity token over
        pinned self-signed TLS; the security group opens :443 to all.

        Raises:
            CommandNotImplementedError: If the template does not declare proxy.connect-info.
        """
        command = self.project_manifest.get_command(PROXY_CONNECT_INFO_COMMAND)
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._outputs_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs={})
        results = collect_results(runner, command)

        # collect_results parses JSON-valued results, so `headers` arrives as a dict.
        headers = results.get("headers")
        return ProxyConnectBundle(
            host=str(results.get("host", "")),
            port=int(results.get("port", 0)),
            ca_cert=str(results.get("ca_cert", "")),
            headers=headers if isinstance(headers, dict) else {},
            expires_at=str(results.get("expires_at", "")),
        )

    # ------------------------------------------------------------------ lifecycle (delegated)

    def start(self, detached: bool) -> ProxyStatus:
        """Launch a fresh proxy (replacing any running); return its status. See ProxyManager.start."""
        return self._manager.start(detached=detached)

    def open(self, path: str = "/") -> str:
        """Open the browser to the running proxy at ``path``; return the loopback URL.

        Raises:
            NoProxyFoundError: If no confirmed proxy is running.
            OpenWebBrowserError: If opening the URL in the browser fails.
        """
        return self._manager.open(path=path)

    def stop(self) -> list[int]:
        """Stop the running proxy for this project; return the PIDs that were stopped.

        Raises:
            ProxyIdentityUnconfirmedError: If a live record's identity can't be confirmed.
            NoProxyFoundError: If there is no running proxy to stop.
        """
        return self._manager.stop()

    def status(self) -> str:
        """Return the single-word state of the running proxy.

        Raises:
            NoProxyFoundError: If no confirmed running proxy exists.
        """
        return self._manager.status()

    def show(self) -> ProxyStatus:
        """Return detail for the running proxy.

        Raises:
            NoProxyFoundError: If no confirmed running proxy exists.
        """
        return self._manager.show()
