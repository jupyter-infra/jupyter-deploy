# Records logs
sudo mkdir -p /var/log/jupyter-startup
exec > >(tee /var/log/jupyter-startup/docker-compose.log) 2>&1

# Validate the file
if ! docker-compose -f /opt/docker/docker-compose.yml config > /dev/null; then
    echo "Invalid docker-compose configuration"
    exit 1
fi

# Start the container
cd /opt/docker
docker-compose up -d