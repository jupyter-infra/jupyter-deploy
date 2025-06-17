#!/bin/bash
set -e

if [ -d "/home/jovyan/.jupyter-deploy" ]; then
    rm -rf /home/jovyan/.jupyter-deploy
fi
mkdir -p /home/jovyan/.jupyter-deploy/jupyter

cp /opt/uv/jupyter/pyproject.toml /home/jovyan/.jupyter-deploy/jupyter/
cp /opt/uv/jupyter/uv.lock /home/jovyan/.jupyter-deploy/jupyter/
cp -r /opt/uv/jupyter/.venv /home/jovyan/.jupyter-deploy/jupyter/

uv sync --project /home/jovyan/.jupyter-deploy/jupyter

exec uv run --project /home/jovyan/.jupyter-deploy/jupyter --locked jupyter lab \
    --no-browser \
    --ip=0.0.0.0 \
    --IdentityProvider.token=