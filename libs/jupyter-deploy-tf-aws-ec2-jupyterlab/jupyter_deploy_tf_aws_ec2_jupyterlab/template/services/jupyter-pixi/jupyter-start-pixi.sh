#!/bin/bash
set -e

echo "Setting up pixi environment..."
if [ ! -f "/home/jovyan/pixi.toml" ] || [ ! -f "/home/jovyan/pixi.lock" ]; then
    echo "Did not find pixi environment files in /home/jovyan."
    cp /opt/pixi/jupyter/pixi.toml /home/jovyan/
    cp /opt/pixi/jupyter/pixi.lock /home/jovyan/
else
    echo "Found existing pixi environment files, syncing..."
fi

echo "Installing pixi dependencies..."
cd /home/jovyan && pixi install --locked

echo "Setting up UV kernel..."
mkdir -p /home/jovyan/.kernels/uv-kernel
if [ ! -f "/home/jovyan/.kernels/uv-kernel/pyproject.toml" ] || [ ! -f "/home/jovyan/.kernels/uv-kernel/uv.lock" ]; then
    echo "Did not find UV kernel environment files."
    cp /opt/uv/kernel/pyproject.toml /home/jovyan/.kernels/uv-kernel
    cp /opt/uv/kernel/uv.lock /home/jovyan/.kernels/uv-kernel
else
    echo "Found existing UV kernel environment files, syncing..."
fi
uv sync --directory /home/jovyan/.kernels/uv-kernel --locked
uv run --directory /home/jovyan/.kernels/uv-kernel \
    python -m ipykernel install --user --name python3-uv --display-name "Python 3 (UV)"

# Disable exit on error for the jupyter lab attempt
set +e
pixi run jupyter lab \
    --no-browser \
    --ip=0.0.0.0 \
    --IdentityProvider.token=

jupyter_exit_code=$?
set -e

if [ $jupyter_exit_code -ne 0 ]; then
    echo "Jupyter lab failed to start, calling reset script..."
    /usr/local/bin/jupyter-reset.sh
fi