# mypy: disable-error-code=name-defined
c = get_config()  # noqa

#  Choices: any of [0, 10, 20, 30, 40, 50, 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL']
c.Application.log_level = "INFO"

c.ServerApp.root_dir = "/home/jovyan"
c.ServerApp.terminado_settings = {
    "shell_command": [
        "bash",
        "-c",
        'export PATH=$(echo $PATH | sed "s|/opt/uv/jupyter/.venv/bin:||"); '
        "echo \"This is a UV-managed shell, use 'uv pip' instead of 'pip'!\"; "
        "bash",
    ]
}
