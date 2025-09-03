#!/bin/bash
set -e

echo "Setting up pixi environment..."
cp /opt/pixi/jupyter/pixi.toml /home/jovyan/
cp /opt/pixi/jupyter/pixi.lock /home/jovyan/

echo "Installing pixi dependencies..."
cd /home/jovyan && pixi install --locked

echo "Setting up UV kernel..."
mkdir -p /home/jovyan/.kernels/uv-kernel
cp /opt/uv/kernel/pyproject.toml /home/jovyan/.kernels/uv-kernel
cp /opt/uv/kernel/uv.lock /home/jovyan/.kernels/uv-kernel
uv sync --directory /home/jovyan/.kernels/uv-kernel --locked
uv run --directory /home/jovyan/.kernels/uv-kernel \
    python -m ipykernel install --user --name python3-uv --display-name "Python 3 (UV)"

# Disable exit on error for the jupyter lab attempt
set +e
pixi run jupyter lab \
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