"""Local client that routes an app from localhost to a jupyter-deploy-managed remote host.

Runs a configured token command, receives a JSON connection bundle on stdout, and
reverse-proxies plain ``http://localhost`` to the remote host over pinned self-signed TLS,
injecting the bundle's rotating auth headers and refreshing them before each ``expires_at``.
It stays cloud-agnostic: it runs an opaque command and parses JSON, importing nothing
cloud-specific.
"""
