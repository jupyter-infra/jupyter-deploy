FROM ghcr.io/jupyter-infra/remote-access-server:v0.1.0-rc.2 AS remote-access

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

USER root

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends supervisor && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash jovyan

# Carrier image: no entrypoint of its own, it exists to hand over this binary.
COPY --from=remote-access /remote-access-server /usr/local/bin/remote-access-server

RUN mkdir -p /etc/jupyter
COPY jupyter_server_config.py /etc/jupyter/

RUN mkdir -p /opt/uv/jupyter
COPY pyproject.toml /opt/uv/jupyter/pyproject.toml
RUN uv sync --directory /opt/uv/jupyter

COPY jupyter-start.sh /usr/local/bin/
COPY jupyter-reset.sh /usr/local/bin/
COPY supervisord.conf /etc/supervisor/supervisord.conf

RUN chmod -R a+r /opt/uv
RUN chmod -R a+r /etc/jupyter
RUN chmod +x /usr/local/bin/jupyter-start.sh
RUN chmod +x /usr/local/bin/jupyter-reset.sh
RUN chown -R jovyan:jovyan /home/jovyan

# Set explicitly rather than relying on the passwd lookup: the host key defaults
# to $HOME/.ssh, which has to resolve onto the mounted volume to survive a restart.
ENV HOME=/home/jovyan

# The uv environment is created at runtime, under the volume that mounts over
# /home/jovyan. Putting it on PATH here is what makes an SSH session land on the
# workspace interpreter and kernels instead of the system Python; a plain shell
# never runs `uv run`, so without this `python` is the wrong one.
ENV PATH=/home/jovyan/.venv/bin:$PATH

ENV REMOTE_ACCESS_AUTOSTART=false

WORKDIR /home/jovyan
USER jovyan

ENTRYPOINT ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
