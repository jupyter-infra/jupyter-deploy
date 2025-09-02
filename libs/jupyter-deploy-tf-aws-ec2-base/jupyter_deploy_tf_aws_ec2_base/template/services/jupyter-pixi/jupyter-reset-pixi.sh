#!/bin/bash
set -e

echo "Resetting Jupyter environment (pixi)..."

if [ -d "/home/jovyan/.venv" ]; then
    echo "Removing existing virtual environment..."
    rm -rf /home/jovyan/.venv
fi

if [ -f "/home/jovyan/pyproject.toml" ]; then
    echo "Removing existing pyproject.toml..."
    rm -f /home/jovyan/pyproject.toml
fi

if [ -f "/home/jovyan/pixi.lock" ]; then
    echo "Removing existing pixi.lock..."
    rm -f /home/jovyan/pixi.lock
fi

if [ -d "/home/jovyan/.jupyter" ]; then
    echo "Cleaning Jupyter config..."
    rm -rf /home/jovyan/.jupyter
fi

# Clean up kernels
if [ -d "/home/jovyan/.kernels" ]; then
    echo "Cleaning kernels config..."
    rm -rf /home/jovyan/.kernels
fi

if [ -d "/home/jovyan/.local" ]; then
    echo "Removing existing local config..."
    rm -rf /home/jovyan/.local
fi

cp /opt/pixi/jupyter/pixi.toml /home/jovyan/
cp /opt/pixi/jupyter/pixi.lock /home/jovyan/

echo "Recreating pixi environment..."
cd /home/jovyan && pixi install --locked

echo "Setting up UV kernel..."
mkdir -p /home/jovyan/.kernels/uv-kernel
cp /opt/uv/kernel/pyproject.toml /home/jovyan/.kernels/uv-kernel
cp /opt/uv/kernel/uv.lock /home/jovyan/.kernels/uv-kernel
uv sync --directory /home/jovyan/.kernels/uv-kernel --locked
uv run --directory /home/jovyan/.kernels/uv-kernel \
    python -m ipykernel install --user --name python3-uv --display-name "Python 3 (UV)"

pixi run jupyter lab \
    --no-browser \
    --ip=0.0.0.0 \
    --IdentityProvider.token=