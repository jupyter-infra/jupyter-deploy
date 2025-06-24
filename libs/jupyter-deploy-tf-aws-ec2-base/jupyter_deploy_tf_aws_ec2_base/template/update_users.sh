#!/bin/bash
set -e

# Script to update the file containing the list of authorized GitHub users
# Usage: 
#   sudo update_users.sh add username1,username2
#   sudo update_users.sh remove username1
#   sudo update_users.sh overwrite username1,username2

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

# Create array w/current users
IFS=',' read -ra CURRENT_USERS <<< "$(cat "$AUTHED_USERS_FILE")"
CURRENT_USERS_ARRAY=("${CURRENT_USERS[@]}")

if [ "$ACTION" == "add" ]; then
    IFS=',' read -ra NEW_USERS <<< "$USERS"
    for user in "${NEW_USERS[@]}"; do
        # Check if user already exists
        if ! echo "${CURRENT_USERS[@]}" | grep -q -w "$user"; then
            CURRENT_USERS_ARRAY+=("$user")
            echo "Added user: $user"
        else
            echo "User already exists: $user"
        fi
    done
elif [ "$ACTION" == "remove" ]; then
    IFS=',' read -ra REMOVE_USERS <<< "$USERS"
    TEMP_ARRAY=()
    
    # Check for users absent in list already
    for remove_user in "${REMOVE_USERS[@]}"; do
        USER_EXISTS=false
        for user in "${CURRENT_USERS_ARRAY[@]}"; do
            if [ "$user" == "$remove_user" ]; then
                USER_EXISTS=true
                break
            fi
        done
        if [ "$USER_EXISTS" == "false" ]; then
            echo "User does not exist: $remove_user"
        fi
    done
    
    # Removal
    for user in "${CURRENT_USERS_ARRAY[@]}"; do
        KEEP=true
        for remove_user in "${REMOVE_USERS[@]}"; do
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
    CURRENT_USERS_ARRAY=()
    IFS=',' read -ra NEW_USERS <<< "$USERS"
    for user in "${NEW_USERS[@]}"; do
        CURRENT_USERS_ARRAY+=("$user")
    done
fi

# Generate the final updated users list and write it back to the file
(IFS=,; echo "${CURRENT_USERS_ARRAY[*]}") > "$AUTHED_USERS_FILE"

# Update the AUTHED_USERS_CONTENT var in the Docker .env file
AUTHED_USERS_CONTENT=$(cat "$AUTHED_USERS_FILE")
sed -i "s/^AUTHED_USERS_CONTENT=.*/AUTHED_USERS_CONTENT=${AUTHED_USERS_CONTENT}/" /opt/docker/.env
echo "Updated authorized users: $AUTHED_USERS_CONTENT"

# Recreate the OAuth container to apply changes
echo "Recreating OAuth container to apply changes..."
cd /opt/docker && docker-compose up -d oauth

echo "Done!"
