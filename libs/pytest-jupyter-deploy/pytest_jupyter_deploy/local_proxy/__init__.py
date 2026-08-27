"""Helpers for templates that expose their app through the local client proxy.

Rung-1 templates (e.g. aws-ec2-jupyterlab) have no public, OAuth-gated URL. The app is
reached from the laptop through ``jupyter-deploy-client-proxy`` — started by ``jd proxy
start`` / ``jd open`` — which binds a loopback port and tunnels to the remote instance over
pinned TLS with a short-lived STS-identity token. This subpackage is the proxy analogue of
:mod:`pytest_jupyter_deploy.oauth2_proxy`.
"""

from pytest_jupyter_deploy.local_proxy.application import LocalProxyApplication

__all__ = ["LocalProxyApplication"]
