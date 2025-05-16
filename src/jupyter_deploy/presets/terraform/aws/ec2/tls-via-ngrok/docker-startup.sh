#!/bin/bash
set -e

exec > >(tee /var/log/jupyter-deploy/docker-compose.log) 2>&1

echo "Running docker-startup script as: $(whoami)"
cd /opt/docker

if ! SECRET_ARN=$(aws ssm get-parameter \
    --name "/jupyter-deploy/ngrok-secret-arn" \
    --query "Parameter.Value" \
    --output text); then
    echo "Error: could not retrieve the ARN of the AWS Secret for the ngrok token"
    exit 1
fi

if ! NGROK_TOKEN=$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_ARN" \
    --query 'SecretString' \
    --output text); then
    echo "Error: could not retrieve the ngrok token from secret: $SECRET_ARN"
    exit 1
fi

if [ -z "$NGROK_TOKEN" ]; then
    echo "Error: retrieved empty token from secret: $SECRET_ARN"
    exit 1
fi

tee /opt/docker/.env >/dev/null << EOFENV
SERVICE_UID=$(id -u service-user)
SERVICE_GID=$(id -g service-user)
DOCKER_GID=$(getent group docker | cut -d: -f3)
NGROK_AUTHTOKEN=${NGROK_TOKEN}
EOFENV
echo "Saved environment file /opt/docker/.env"

if ! docker-compose -f docker-compose.yml config > /dev/null; then
    echo "Invalid docker-compose configuration"
    exit 1
else
    echo "Validated docker-compose file"
fi

echo "Starting docker-compose"
docker-compose up -d
echo "Docker-compose complete"