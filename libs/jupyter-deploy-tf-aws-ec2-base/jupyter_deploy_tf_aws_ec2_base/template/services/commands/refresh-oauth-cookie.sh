#!/bin/bash
set -e

exec > >(tee -a /var/log/jupyter-deploy/refresh-oauth-cookie.log) 2>&1

mkdir -p /opt/docker/secrets
# Generate 32 raw bytes for AES encryption — cookie-secret-file requires
# raw binary (not base64), exactly 16, 24, or 32 bytes (AES-128/192/256).
dd if=/dev/urandom bs=32 count=1 2>/dev/null > /opt/docker/secrets/cookie-secret
# This script runs as root (via SSM), but the oauth container runs as
# service-user — chown so the mounted file is readable inside the container.
chown service-user:service-user /opt/docker/secrets/cookie-secret
chmod 600 /opt/docker/secrets/cookie-secret
echo "Updated OAuth cookie secret."
