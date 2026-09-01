# mypy: disable-error-code=name-defined
c = get_config()  # noqa

c.Application.log_level = "INFO"

# This server is reached through the local jupyter-deploy client proxy. The proxy rewrites the
# browser's Origin/Referer to the upstream origin (https://<instance-ip>:<port>) so they match the
# Host the server sees, and Jupyter's default same-origin check passes with no allow_origin override
# needed. The real access boundary is the auth sidecar (STS-identity ForwardAuth) plus pinned TLS.

c.ServerApp.root_dir = "/home/jovyan"
c.ServerApp.terminado_settings = {
    "shell_command": [
        "bash",
        "-c",
        "echo \"This is a UV-managed environment, use 'uv add' or 'uv pip' instead of 'pip'!\"; bash",
    ]
}
