#!/bin/bash
set -e

echo "Resetting Jupyter environment (uv)..."

if [ -d "/home/jovyan/.venv" ]; then
    echo "Removing existing virtual environment..."
    rm -rf /home/jovyan/.venv
fi

if [ -f "/home/jovyan/pyproject.toml" ]; then
    echo "Removing existing pyproject.toml..."
    rm -f /home/jovyan/pyproject.toml
fi

if [ -f "/home/jovyan/uv.lock" ]; then
    echo "Removing existing uv.lock..."
    rm -f /home/jovyan/uv.lock
fi

if [ -d "/home/jovyan/.jupyter" ]; then
    echo "Cleaning Jupyter config..."
    rm -rf /home/jovyan/.jupyter
fi

cp /opt/uv/jupyter/pyproject.toml /home/jovyan/
cp /opt/uv/jupyter/uv.lock /home/jovyan/

echo "Recreating uv environment..."
uv sync --locked

uv run jupyter lab \
    --no-browser \
    --ip=0.0.0.0 \
    --IdentityProvider.token=