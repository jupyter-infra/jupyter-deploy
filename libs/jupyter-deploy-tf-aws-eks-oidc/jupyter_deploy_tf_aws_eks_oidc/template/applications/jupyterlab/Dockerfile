FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

USER root

RUN apt-get update && apt-get upgrade -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash jovyan

RUN mkdir -p /etc/jupyter
COPY jupyter_server_config.py /etc/jupyter/

RUN mkdir -p /opt/uv/jupyter
COPY pyproject.toml /opt/uv/jupyter/pyproject.toml
RUN uv sync --directory /opt/uv/jupyter

COPY jupyter-start.sh /usr/local/bin/
COPY jupyter-reset.sh /usr/local/bin/

RUN chmod -R a+r /opt/uv
RUN chmod -R a+r /etc/jupyter
RUN chmod +x /usr/local/bin/jupyter-start.sh
RUN chmod +x /usr/local/bin/jupyter-reset.sh
RUN chown -R jovyan:jovyan /home/jovyan

WORKDIR /home/jovyan
USER jovyan

ENTRYPOINT ["/usr/local/bin/jupyter-start.sh"]
