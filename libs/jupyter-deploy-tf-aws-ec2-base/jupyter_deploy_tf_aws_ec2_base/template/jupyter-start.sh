#!/bin/bash
set -e

setup_uv_env() {
    echo "Setting up uv environment..."
    cp /opt/uv/jupyter/pyproject.toml /home/jovyan/
    cp /opt/uv/jupyter/uv.lock /home/jovyan/
    uv sync --locked
}

if [ ! -f "/home/jovyan/pyproject.toml" ] || [ ! -f "/home/jovyan/uv.lock" ]; then
    echo "Did not find uv environment files in /home/jovyan."
    setup_uv_env
else
    echo "Found existing uv environment files, syncing..."
    uv sync --locked
fi

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