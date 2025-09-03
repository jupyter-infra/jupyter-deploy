#!/bin/bash
set -e

echo "Setting up uv environment..."
cp /opt/uv/jupyter/pyproject.toml /home/jovyan/
cp /opt/uv/jupyter/uv.lock /home/jovyan/

if [ ! -f "/home/jovyan/pyproject.toml" ] || [ ! -f "/home/jovyan/uv.lock" ]; then
    echo "Did not find uv environment files in /home/jovyan."
    cp /opt/uv/jupyter/pyproject.toml /home/jovyan/
    cp /opt/uv/jupyter/uv.lock /home/jovyan/
else
    echo "Found existing uv environment files, syncing..."
fi

uv sync --locked

# Disable exit on error for the jupyter lab attempt
set +e
uv run jupyter lab \
    --no-browser \
    --ip=0.0.0.0 \
    --IdentityProvider.token=

# captures jupyterlab exit code
jupyter_exit_code=$?
set -e

# Check if jupyter lab failed
if [ $jupyter_exit_code -ne 0 ]; then
    echo "Jupyter lab failed to start, calling reset script..."
    /usr/local/bin/jupyter-reset.sh
fi