# Configuration file for jupyter-server.
c = get_config()  #noqa

#  Choices: any of [0, 10, 20, 30, 40, 50, 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL']
c.Application.log_level = 'INFO'

c.ServerApp.root_dir = '/home/jovyan'
c.ServerApp.terminado_settings = {
    'shell_command': ['bash', '-c', '. /opt/uv/jupyter/.venv/bin/activate; cd ~; bash']
}

c.FileContentsManager.root_dir = '/home/jovyan'
c.AsyncFileContentsManager.root_dir = '/home/jovyan'
