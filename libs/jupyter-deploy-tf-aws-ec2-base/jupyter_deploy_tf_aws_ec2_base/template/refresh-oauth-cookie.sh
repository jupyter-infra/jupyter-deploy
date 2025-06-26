#!/bin/bash
set -e

exec > >(tee -a /var/log/jupyter-deploy/refresh-oauth-cookie.log) 2>&1

OAUTH_SECRET=$(openssl rand -base64 32 | tr -- '+/' '-_')

if grep -q "^OAUTH_SECRET=" /opt/docker/.env; then
    sed -i "s/^OAUTH_SECRET=.*/OAUTH_SECRET=${OAUTH_SECRET}/" /opt/docker/.env
else
    echo "OAUTH_SECRET=${OAUTH_SECRET}" >> /opt/docker/.env
fi
echo "Updated OAuth cookie secret."
