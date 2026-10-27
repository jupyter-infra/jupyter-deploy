#!/bin/bash
set -e

mkdir -p /var/log/jupyter-deploy
exec > >(tee /var/log/jupyter-deploy/docker-compose.log) 2>&1

echo "Running docker-startup script as: $(whoami)"
cd /opt/docker

# Ensure the self-signed cert is present (idempotent — copies from the data volume).
if [ ! -f /opt/docker/certs/cert.pem ] || [ ! -f /opt/docker/certs/key.pem ]; then
    echo "Certificate missing under /opt/docker/certs, (re)generating..."
    sh /usr/local/bin/generate-cert.sh
fi

# attempt to allocate 95% of memory to jupyter
# while keeping enough memory for other containers
TOTAL_MEMORY_MB=$(free -m | awk '/^Mem:/{print $2}')
MAX_MEM_RESERVATION_MB=$((TOTAL_MEMORY_MB - 384))
PERC_MEM_RESERVATION_MB=$((TOTAL_MEMORY_MB * 95 / 100))

JUPYTER_MEM_LIMIT_MB=$(( PERC_MEM_RESERVATION_MB < MAX_MEM_RESERVATION_MB ? PERC_MEM_RESERVATION_MB : MAX_MEM_RESERVATION_MB ))
JUPYTER_MEM_RESERVATION_MB=$((JUPYTER_MEM_LIMIT_MB / 2))

# Read the IAM principal allowlist (seeded first-boot by cloudinit, then owned at runtime by
# `jd users`/`jd teams`). docker-compose interpolates these into the auth-sidecar env, so the live
# lists survive reboots/redeploys without being baked into the compose file.
read_allowlist_section() {
    local section=$1
    if [ -f /etc/AUTH_ALLOWLIST ]; then
        sed -n "/^\[$section\]$/,/^\[/p" /etc/AUTH_ALLOWLIST | grep -v "^\[$section\]$" | grep -v "^\[" | tr -d '\n' | tr -d ' '
    fi
}
ROLE_NAME_ALLOWLIST=$(read_allowlist_section roles)
USER_NAME_ALLOWLIST=$(read_allowlist_section users)

tee /opt/docker/.env >/dev/null << EOFENV
SERVICE_UID=$(id -u service-user)
SERVICE_GID=$(id -g service-user)
DOCKER_GID=$(getent group docker | cut -d: -f3)
JUPYTER_MEM_LIMIT_MB=${JUPYTER_MEM_LIMIT_MB}
JUPYTER_MEM_RESERVATION_MB=${JUPYTER_MEM_RESERVATION_MB}
ROLE_NAME_ALLOWLIST=${ROLE_NAME_ALLOWLIST}
USER_NAME_ALLOWLIST=${USER_NAME_ALLOWLIST}
BEDROCK_ENABLED=$(grep -q 'container_name: bedrock-sidecar' docker-compose.yml && echo true || echo false)
EOFENV
echo "Saved environment file /opt/docker/.env"

if ! docker compose -f docker-compose.yml config > /dev/null; then
    echo "Invalid docker-compose configuration"
    exit 1
else
    echo "Validated docker compose file"
fi

SHOULD_BUILD=""
if [ -f /opt/docker/.build-manifest.prev ]; then
    if ! diff -q /opt/docker/.build-manifest /opt/docker/.build-manifest.prev > /dev/null 2>&1; then
        echo "Build manifest changed: rebuilding images"
        SHOULD_BUILD="--build"
    else
        echo "Build manifest unchanged: reusing images"
    fi
else
    echo "No previous build manifest"
    SHOULD_BUILD="--build"
fi

# Save current manifest for next run
cp /opt/docker/.build-manifest /opt/docker/.build-manifest.prev

# Set timeouts based on whether we're building or not
# Building takes longer, especially for GPU images
if [ "$SHOULD_BUILD" = "--build" ]; then
    TIMEOUT_FIRST=600  # 10 minutes for build
    TIMEOUT_RETRY=300  # 5 minutes for retry
else
    TIMEOUT_FIRST=120  # 2 minutes without build
    TIMEOUT_RETRY=60   # 1 minute for retry
fi

# Jupyter's network (fixed subnet 172.30.250.0/24 in docker-compose.yml) cannot reach IMDS: user code
# holds only the app role's credentials. Bypassable from a container with /var/run/docker.sock
# (tracked separately). The network is IPv4-only, so there is no IPv6 route to fd00:ec2::254 to block.
iptables -C DOCKER-USER -s 172.30.250.0/24 -d 169.254.169.254 -j DROP 2>/dev/null || iptables -I DOCKER-USER 1 -s 172.30.250.0/24 -d 169.254.169.254 -j DROP

echo "Starting docker compose"
if ! docker compose up -d --force-recreate $SHOULD_BUILD --wait --wait-timeout $TIMEOUT_FIRST; then
    echo "First attempt failed, trying with cleanup..."
    docker compose down || true
    docker system prune -f --volumes || true

    if ! docker compose up -d --force-recreate $SHOULD_BUILD --wait --wait-timeout $TIMEOUT_RETRY; then
        echo "Second attempt failed, restarting Docker daemon..."
        systemctl restart docker
        sleep 10
        docker compose up -d --force-recreate $SHOULD_BUILD --wait --wait-timeout $TIMEOUT_RETRY
    fi
fi
echo "docker compose complete"

echo "Waiting for containers to stabilize..."
sleep 2

touch /opt/docker/started.txt
chmod 644 /opt/docker/started.txt
