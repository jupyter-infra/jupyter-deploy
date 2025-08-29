# mypy: disable-error-code=name-defined
c = get_config()  # noqa

#  Choices: any of [0, 10, 20, 30, 40, 50, 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL']
c.Application.log_level = "INFO"

c.ServerApp.root_dir = "/home/jovyan"
c.ServerApp.terminado_settings = {
    "shell_command": [
        "bash",
        "-c",
        "echo \"This is a pixi-managed shell, use 'pixi add' instead of 'pip'!\"; bash",
    ]
}
