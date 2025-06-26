#!/bin/bash
set -e

# Usage: sudo sh refresh-oauth-cookie.sh

# Generate a new random OAuth cookie secret
OAUTH_SECRET=$(openssl rand -base64 32 | tr -- '+/' '-_')

# Update the OAUTH_SECRET var in the Docker .env file
# Or create it if it doesn't exist yet (i.e. when docker-startup is run on instance create)
if grep -q "^OAUTH_SECRET=" /opt/docker/.env; then
    sed -i "s/^OAUTH_SECRET=.*/OAUTH_SECRET=${OAUTH_SECRET}/" /opt/docker/.env
else
    echo "OAUTH_SECRET=${OAUTH_SECRET}" >> /opt/docker/.env
fi
echo "Updated OAuth cookie secret."
