#!/bin/bash
set -e

# Script to update the file containing the list of authorized GitHub users
# Usage: 
#   sudo update_users.sh add username1,username2
#   sudo update_users.sh remove username1
#   sudo update_users.sh overwrite username1,username2

exec > >(tee -a /var/log/jupyter-deploy/update-users.log) 2>&1

AUTHED_USERS_FILE="/etc/AUTHED_USERS"
ACTION=$1
USERS=$2

if [ -z "$ACTION" ] || [ -z "$USERS" ]; then
    echo "Error: Missing required parameters"
    echo "Usage: sudo ./update_users.sh [add|remove|overwrite] username1,username2,..."
    exit 1
fi

if [ "$ACTION" != "add" ] && [ "$ACTION" != "remove" ] && [ "$ACTION" != "overwrite" ]; then
    echo "Error: Invalid action. Use 'add', 'remove', or 'overwrite'"
    echo "Usage: sudo ./update_users.sh [add|remove|overwrite] username1,username2,..."
    exit 1
fi

# Ensure the file exists in case it was manually deleted
touch "$AUTHED_USERS_FILE"

IFS=',' read -ra INPUT_USERS <<< "$USERS"
IFS=',' read -ra CURRENT_USERS <<< "$(cat "$AUTHED_USERS_FILE")"
INPUT_USERS_SORTED=$(echo "$USERS" | tr ',' '\n' | sort)
CURRENT_USERS_ARRAY=("${CURRENT_USERS[@]}")
CURRENT_USERS_SORTED=$(cat "$AUTHED_USERS_FILE" | tr ',' '\n' | sort)

REFRESH_OAUTH_COOKIE=false

if [ "$ACTION" == "add" ]; then
    for user in "${INPUT_USERS[@]}"; do
        # Check if user already exists
        if ! echo "${CURRENT_USERS[@]}" | grep -q -w "$user"; then
            CURRENT_USERS_ARRAY+=("$user")
            echo "Added user: $user"
        else
            echo "User already exists: $user"
        fi
    done
elif [ "$ACTION" == "remove" ]; then
    TEMP_ARRAY=()
    
    # Check for users absent in list already
    for remove_user in "${INPUT_USERS[@]}"; do
        USER_EXISTS=false
        for user in "${CURRENT_USERS_ARRAY[@]}"; do
            if [ "$user" == "$remove_user" ]; then
                USER_EXISTS=true
                break
            fi
        done
        if [ "$USER_EXISTS" == "false" ]; then
            echo "User does not exist: $remove_user"
        else
            REFRESH_OAUTH_COOKIE=true
        fi
    done
    
    # Removal
    for user in "${CURRENT_USERS_ARRAY[@]}"; do
        KEEP=true
        for remove_user in "${INPUT_USERS[@]}"; do
            if [ "$user" == "$remove_user" ]; then
                KEEP=false
                echo "Removed user: $user"
                break
            fi
        done
        if [ "$KEEP" == "true" ]; then
            TEMP_ARRAY+=("$user")
        fi
    done
    CURRENT_USERS_ARRAY=("${TEMP_ARRAY[@]}")
else
    # Overwrite
    for user in $CURRENT_USERS_SORTED; do
        if ! echo "$INPUT_USERS_SORTED" | grep -q "^$user$"; then
            REFRESH_OAUTH_COOKIE=true
            break
        fi
    done

    CURRENT_USERS_ARRAY=()
    for user in "${INPUT_USERS[@]}"; do
        CURRENT_USERS_ARRAY+=("$user")
    done
fi

# Generate the final updated users list and write it back to the file
(IFS=,; echo "${CURRENT_USERS_ARRAY[*]}") > "$AUTHED_USERS_FILE"

AUTHED_USERS_CONTENT=$(cat "$AUTHED_USERS_FILE")
sed -i "s/^AUTHED_USERS_CONTENT=.*/AUTHED_USERS_CONTENT=${AUTHED_USERS_CONTENT}/" /opt/docker/.env

# The oauth sidecar vends cookies that get stored on user's webbrowser and linked to a server-side session. 
# Such cookies are opaque to the users, they are encrypted with a secret string. 
# When we remove a user from the allowlist, we need to invalidate their cookie/session so that they loose access 
# immediately. We do so by updating the cookie secret. Note that this action invalidates all sessions/cookies.
if [ "$REFRESH_OAUTH_COOKIE" = true ]; then
    sh /usr/local/bin/refresh-oauth-cookie.sh >/dev/null
fi

echo "Recreating OAuth container to apply changes..."
cd /opt/docker && docker-compose up -d oauth

echo "Done!"
