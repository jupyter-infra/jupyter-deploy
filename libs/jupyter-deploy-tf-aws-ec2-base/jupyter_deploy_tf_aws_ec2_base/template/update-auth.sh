#!/bin/bash
set -e

# Script to update the file containing the list of authorized GitHub entities (users, teams, orgs)
# Usage: 
#   sudo update-auth.sh users [add|remove|overwrite] username1,username2
#   sudo update-auth.sh teams [add|remove|overwrite] team1,team2
#   sudo update-auth.sh org an_org
#   sudo update-auth.sh org [remove]

# File content follows format:

# [org]
#  Org1
#
# [teams]
#  Team1,Team2
#
# [users]
#  User1,User2

exec > >(tee -a /var/log/jupyter-deploy/update-auth.log) 2>&1

AUTHED_ENTITIES_FILE="/etc/AUTHED_ENTITIES"
ENTITY_TYPE=$1
ACTION=$2
VALUES=$3

# Ensure the file exists in case it was manually deleted
touch "$AUTHED_ENTITIES_FILE"

if ! grep -q "\[org\]" "$AUTHED_ENTITIES_FILE"; then
    echo -e "\n[org]" >> "$AUTHED_ENTITIES_FILE"
fi

if ! grep -q "\[teams\]" "$AUTHED_ENTITIES_FILE"; then
    echo -e "\n[teams]" >> "$AUTHED_ENTITIES_FILE"
fi

if ! grep -q "\[users\]" "$AUTHED_ENTITIES_FILE"; then
    echo -e "\n[users]" >> "$AUTHED_ENTITIES_FILE"
fi

get_section_content() {
    local section=$1
    local content=$(sed -n "/^\[$section\]$/,/^\[/p" "$AUTHED_ENTITIES_FILE" | grep -v "^\[$section\]$" | grep -v "^\[" | tr -d '\n' | tr -d ' ')
    echo "$content"
}

update_section() {
    local section=$1
    local content=$2
    sed -i "/^\[$section\]$/,/^\[/ {/^\[$section\]$/!{/^\[/!d}}" "$AUTHED_ENTITIES_FILE"
    if [ -n "$content" ]; then
        sed -i "/^\[$section\]$/a $content" "$AUTHED_ENTITIES_FILE"
    fi
}

REFRESH_OAUTH_COOKIE=false
AUTH_CHANGED=false

if [ "$ENTITY_TYPE" == "org" ]; then
    if [ "$ACTION" == "remove" ]; then
        CURRENT_ORG=$(get_section_content "org")
        if [ -n "$CURRENT_ORG" ]; then
            REFRESH_OAUTH_COOKIE=true
            AUTH_CHANGED=true
            update_section "org" ""
            echo "Removed organization: $CURRENT_ORG"
        else
            echo "No organization is currently set"
        fi
    elif [ -z "$ACTION" ]; then
        echo "Error: Missing either GitHub organization name or remove action"
        echo "Usage: sudo ./update-auth.sh org organization_name"
        echo "       sudo ./update-auth.sh org remove"
        exit 1
    else
        CURRENT_ORG=$(get_section_content "org")
        
        if [ "$CURRENT_ORG" != "$ACTION" ]; then
            REFRESH_OAUTH_COOKIE=true
            AUTH_CHANGED=true
        fi

        update_section "org" "$ACTION"
        echo "Set organization to: $ACTION"
    fi
    
elif [ "$ENTITY_TYPE" == "users" ] || [ "$ENTITY_TYPE" == "teams" ]; then
    if [ -z "$ACTION" ] || [ -z "$VALUES" ]; then
        echo "Error: Missing required parameters"
        echo "Usage: sudo ./update-auth.sh $ENTITY_TYPE [add|remove|overwrite] value1,value2,..."
        exit 1
    fi

    if [ "$ACTION" != "add" ] && [ "$ACTION" != "remove" ] && [ "$ACTION" != "overwrite" ]; then
        echo "Error: Invalid action. Use 'add', 'remove', or 'overwrite'"
        echo "Usage: sudo ./update-auth.sh $ENTITY_TYPE [add|remove|overwrite] value1,value2,..."
        exit 1
    fi
    
    CURRENT_VALUES=$(get_section_content "$ENTITY_TYPE")
    
    IFS=',' read -ra INPUT_VALUES <<< "$VALUES"
    IFS=',' read -ra CURRENT_VALUES_ARRAY <<< "$CURRENT_VALUES"
    INPUT_VALUES_SORTED=$(echo "$VALUES" | tr ',' '\n' | sort)
    CURRENT_VALUES_ARRAY=("${CURRENT_VALUES_ARRAY[@]}")
    CURRENT_VALUES_SORTED=$(echo "$CURRENT_VALUES" | tr ',' '\n' | sort)

    if [ "$ACTION" == "add" ]; then
        for value in "${INPUT_VALUES[@]}"; do
            if ! echo "${CURRENT_VALUES_ARRAY[@]}" | grep -q -w "$value"; then
                CURRENT_VALUES_ARRAY+=("$value")
                echo "Added $ENTITY_TYPE: $value"
                AUTH_CHANGED=true
            else
                echo "$ENTITY_TYPE already exists: $value"
            fi
        done
    elif [ "$ACTION" == "remove" ]; then
        TEMP_ARRAY=()
        
        for remove_value in "${INPUT_VALUES[@]}"; do
            VALUE_EXISTS=false
            for value in "${CURRENT_VALUES_ARRAY[@]}"; do
                if [ "$value" == "$remove_value" ]; then
                    VALUE_EXISTS=true
                    break
                fi
            done
            if [ "$VALUE_EXISTS" == "false" ]; then
                echo "$ENTITY_TYPE does not exist: $remove_value"
            else
                REFRESH_OAUTH_COOKIE=true
            fi
        done
        
        # Removal
        for value in "${CURRENT_VALUES_ARRAY[@]}"; do
            KEEP=true
            for remove_value in "${INPUT_VALUES[@]}"; do
                if [ "$value" == "$remove_value" ]; then
                    KEEP=false
                    AUTH_CHANGED=true
                    echo "Removed $ENTITY_TYPE: $value"
                    break
                fi
            done
            if [ "$KEEP" == "true" ]; then
                TEMP_ARRAY+=("$value")
            fi
        done
        CURRENT_VALUES_ARRAY=("${TEMP_ARRAY[@]}")
    else
        # Overwrite
        if [ "$CURRENT_VALUES_SORTED" != "$INPUT_VALUES_SORTED" ]; then
            AUTH_CHANGED=true
            for value in $CURRENT_VALUES_SORTED; do
                if ! echo "$INPUT_VALUES_SORTED" | grep -q "^$value$"; then
                    REFRESH_OAUTH_COOKIE=true
                    break
                fi
            done
        fi

        CURRENT_VALUES_ARRAY=()
        for value in "${INPUT_VALUES[@]}"; do
            CURRENT_VALUES_ARRAY+=("$value")
        done
    fi

    FINAL_VALUES=""
    if [ ${#CURRENT_VALUES_ARRAY[@]} -gt 0 ]; then
        FINAL_VALUES=$(IFS=,; echo "${CURRENT_VALUES_ARRAY[*]}")
    fi
    
    update_section "$ENTITY_TYPE" "$FINAL_VALUES"
    
else
    echo "Error: Invalid entity type. Use 'org', 'teams', or 'users'"
    echo "Usage: sudo ./update-auth.sh [org|teams|users] ..."
    exit 1
fi

AUTHED_USERS_CONTENT=$(get_section_content "users")
AUTHED_ORG_CONTENT=$(get_section_content "org")
AUTHED_TEAMS_CONTENT=$(get_section_content "teams")

sed -i "s/^AUTHED_USERS_CONTENT=.*/AUTHED_USERS_CONTENT=${AUTHED_USERS_CONTENT}/" /opt/docker/.env
sed -i "s/^AUTHED_ORG_CONTENT=.*/AUTHED_ORG_CONTENT=${AUTHED_ORG_CONTENT}/" /opt/docker/.env
sed -i "s/^AUTHED_TEAMS_CONTENT=.*/AUTHED_TEAMS_CONTENT=${AUTHED_TEAMS_CONTENT}/" /opt/docker/.env

# The oauth sidecar vends cookies that get stored on user's webbrowser and linked to a server-side session. 
# Such cookies are opaque to the users, they are encrypted with a secret string. 
# When we remove a user from the allowlist, we need to invalidate their cookie/session so that they loose access 
# immediately. We do so by updating the cookie secret. Note that this action invalidates all sessions/cookies.
if [ "$REFRESH_OAUTH_COOKIE" = true ]; then
    sh /usr/local/bin/refresh-oauth-cookie.sh >/dev/null
fi

if [ "$AUTH_CHANGED" = true ]; then
    echo "Recreating OAuth container to apply changes..."
    cd /opt/docker && docker-compose up -d oauth
fi

echo "Done!"
