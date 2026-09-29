#!/bin/bash
set -e

BASE_URL="${JUPYTER_BASE_URL:-/}"

echo "Setting up uv environment..."
# Seed the manifests ONLY when the home volume has none. Copying them
# unconditionally would overwrite the user's own dependencies on every restart,
# and the `uv sync --locked` below would then prune them out of .venv.
if [ ! -f "/home/jovyan/pyproject.toml" ] || [ ! -f "/home/jovyan/uv.lock" ]; then
    echo "Did not find uv environment files in /home/jovyan."
    cp /opt/uv/jupyter/pyproject.toml /home/jovyan/
    cp /opt/uv/jupyter/uv.lock /home/jovyan/
else
    echo "Found existing uv environment files, syncing..."
fi

uv sync --locked

set +e
uv run jupyter lab \
    --no-browser \
    --ip=0.0.0.0 \
    --IdentityProvider.token= \
    --ServerApp.base_url="$BASE_URL"

jupyter_exit_code=$?
set -e

if [ $jupyter_exit_code -ne 0 ]; then
    echo "Jupyter lab failed to start, calling reset script..."
    /usr/local/bin/jupyter-reset.sh
fi
