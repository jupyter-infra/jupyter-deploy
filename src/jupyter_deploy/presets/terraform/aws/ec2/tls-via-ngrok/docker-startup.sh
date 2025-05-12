#!/bin/bash
set -e

# Records logs
exec > >(tee /var/log/jupyter-deploy/docker-compose.log) 2>&1

echo "Running docker-startup script as: $(whoami)"
cd /opt/docker

export SERVICE_UID=$(id -u service-user)
export SERVICE_GID=$(id -g service-user)

# Validate the file
if ! docker-compose -f docker-compose.yml config > /dev/null; then
    echo "Invalid docker-compose configuration."
    exit 1
else
    echo "Validated docker-compose file."
fi

# Start the container
echo "Starting docker-compose with UID=$SERVICE_UID : GID=$SERVICE_GID"
docker-compose up -d