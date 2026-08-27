# mypy: disable-error-code=name-defined
c = get_config()  # noqa

c.Application.log_level = "INFO"

# This server is reached through the local jupyter-deploy client proxy: the browser's
# Origin is the proxy's loopback (http://127.0.0.1:<random-port>) while the server sees
# the instance IP as Host, so Jupyter's same-origin check blocks every websocket and
# mutating API call. Allow the loopback origin on any port (the proxy picks a fresh port
# each run). The real access boundary is the auth sidecar (STS-identity ForwardAuth) plus
# pinned TLS, not this CORS check.
c.ServerApp.allow_origin_pat = r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$"

c.ServerApp.root_dir = "/home/jovyan"
c.ServerApp.terminado_settings = {
    "shell_command": [
        "bash",
        "-c",
        "echo \"This is a UV-managed environment, use 'uv add' or 'uv pip' instead of 'pip'!\"; bash",
    ]
}
