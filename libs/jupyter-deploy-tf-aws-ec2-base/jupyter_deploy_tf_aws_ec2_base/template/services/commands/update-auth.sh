#!/bin/bash
set -e

# Script to update the file containing the list of authorized GitHub entities (users, teams, orgs)
# Usage: 
#   sudo sh update-auth.sh users [add|remove|set] username1,username2
#   sudo sh update-auth.sh teams [add|remove|set] team1,team2
#   sudo sh update-auth.sh org an_org
#   sudo sh update-auth.sh org [remove]

# File content follows format:
# [org]
# Org1
#
# [teams]
# Team1,Team2
#
# [users]
# User1,User2

LOG_FILE="/var/log/jupyter-deploy/update-auth.log"
touch "$LOG_FILE"
exec 2> >(tee -a "$LOG_FILE" >&2)

AUTHED_ENTITIES_FILE="/etc/AUTHED_ENTITIES"
ENTITY_TYPE=$1
ACTION=$2
VALUES=$3

log_message() {
  local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
  echo "[$timestamp] $*" >> "$LOG_FILE"
}

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

# Check if an operation would remove all authentication restrictions
check_would_remove_all_auth() {
    local entity_type=$1
    local action=$2
    local values=$3

    # Get current values from each section
    local users_content=$(get_section_content "users")
    local org_content=$(get_section_content "org")
    local teams_content=$(get_section_content "teams")

    # Simulate the operation based on entity type and action
    case "$entity_type" in
        "org")
            if [ "$action" == "remove" ]; then
                org_content=""
            fi
            ;;
        "users")
            if [ "$action" == "remove" ]; then
                IFS=',' read -ra input_values <<< "$values"

                # Use explicit variables instead of variable indirection
                IFS=',' read -ra current_values <<< "$users_content"

                if [ "$action" == "remove" ]; then
                    # Simulate removal
                    local temp_array=()
                    for value in "${current_values[@]}"; do
                        local keep=true
                        for remove_value in "${input_values[@]}"; do
                            if [ "$value" == "$remove_value" ]; then
                                keep=false
                                break
                            fi
                        done
                        if [ "$keep" == "true" ]; then
                            temp_array+=("$value")
                        fi
                    done

                    # Update the simulated content
                    if [ ${#temp_array[@]} -gt 0 ]; then
                        users_content=$(IFS=,; echo "${temp_array[*]}")
                    else
                        users_content=""
                    fi
                fi
            fi
            ;;
    esac

    # Check if operation would result in no auth restrictions
    # Teams are not independent from organization, so we only check users and org
    if [ -z "$users_content" ] && [ -z "$org_content" ]; then
        ERROR="Error: This operation would remove all authentication restrictions."
        DECISION_MESSAGE="At least one user or an organization must remain specified."
        log_message "$ERROR"
        log_message "$DECISION_MESSAGE"
        echo "$ERROR"
        echo "$DECISION_MESSAGE"
        exit 1
    fi
}

REFRESH_OAUTH_COOKIE=false
AUTH_CHANGED=false

# Pre-check if the operation would remove all auth restrictions
if [ "$ACTION" == "remove" ]; then
    if [ "$ENTITY_TYPE" == "org" ]; then
        check_would_remove_all_auth "org" "remove" ""
    elif [ "$ENTITY_TYPE" == "users" ]; then
        check_would_remove_all_auth "$ENTITY_TYPE" "$ACTION" "$VALUES"
    fi
    # Note: teams are irrelevant here: they only apply if an organization is set.
    # Even if all teams are removed, the authorization checks that the users
    # belong to the specified organization.
fi

if [ "$ENTITY_TYPE" == "org" ]; then
    if [ "$ACTION" == "remove" ]; then
        CURRENT_ORG=$(get_section_content "org")
        if [ -n "$CURRENT_ORG" ]; then
            REFRESH_OAUTH_COOKIE=true
            AUTH_CHANGED=true
            update_section "org" ""
            log_message "Removed organization: $CURRENT_ORG"
        else
            log_message "No organization is currently set"
        fi
    elif [ -z "$ACTION" ]; then
        ERROR="Error: Missing either GitHub organization name or remove action."
        log_message "$ERROR"
        echo "$ERROR"
        exit 1
    else
        CURRENT_ORG=$(get_section_content "org")
        
        if [ "$CURRENT_ORG" != "$ACTION" ]; then
            REFRESH_OAUTH_COOKIE=true
            AUTH_CHANGED=true
        fi

        update_section "org" "$ACTION"
        log_message "Set organization to: $ACTION"
    fi
    
elif [ "$ENTITY_TYPE" == "users" ] || [ "$ENTITY_TYPE" == "teams" ]; then
    if [ -z "$ACTION" ] || [ -z "$VALUES" ]; then
        ERROR="Error: Missing required parameters."
        log_message "$ERROR"
        echo $ERROR
        echo "Usage: sudo update-auth.sh $ENTITY_TYPE [add|remove|set] value1,value2,..."
        exit 1
    fi

    if [ "$ACTION" != "add" ] && [ "$ACTION" != "remove" ] && [ "$ACTION" != "set" ]; then
        ERROR="Error: Invalid action."
        log_message "$ERROR"
        echo $ERROR
        echo "Usage: sudo update-auth.sh $ENTITY_TYPE [add|remove|set] value1,value2,..."
        exit 1
    fi
    
    CURRENT_VALUES=$(get_section_content "$ENTITY_TYPE")
    
    IFS=',' read -ra INPUT_VALUES <<< "$VALUES"
    IFS=',' read -ra CURRENT_VALUES_ARRAY <<< "$CURRENT_VALUES"
    INPUT_VALUES_SORTED=$(echo "$VALUES" | tr ',' '\n' | sort)
    CURRENT_VALUES_ARRAY=("${CURRENT_VALUES_ARRAY[@]}")
    CURRENT_VALUES_SORTED=$(echo "$CURRENT_VALUES" | tr ',' '\n' | sort)

    if [ "$ACTION" == "add" ]; then
        # Edge case: If we're adding teams, and there are currently no teams but an org is set,
        # we need to refresh cookies as this is a new restriction
        if [ "$ENTITY_TYPE" == "teams" ] && [ -z "$CURRENT_VALUES" ]; then
            ORG_CONTENT=$(get_section_content "org")
            if [ -n "$ORG_CONTENT" ]; then
                REFRESH_OAUTH_COOKIE=true
            fi
        fi

        for value in "${INPUT_VALUES[@]}"; do
            if ! echo "${CURRENT_VALUES_ARRAY[@]}" | grep -q -w "$value"; then
                CURRENT_VALUES_ARRAY+=("$value")
                log_message "Added $ENTITY_TYPE: $value"
                AUTH_CHANGED=true
            else
                log_message "$ENTITY_TYPE already exists: $value"
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
                log_message "$ENTITY_TYPE does not exist: $remove_value"
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
                    log_message "Removed $ENTITY_TYPE: $value"
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
            for value in "$CURRENT_VALUES_SORTED"; do
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
    ERROR="Error: Invalid entity type."
    log_message "$ERROR"
    echo "$ERROR"
    echo "Usage: sudo update-auth.sh [org|teams|users] ..."
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
    log_message "Update will result in removing access to some users: invalidating cookies..."
    sh /usr/local/bin/refresh-oauth-cookie.sh >/dev/null
    log_message "Cookies invalidated."
fi

if [ "$AUTH_CHANGED" = true ]; then
    log_message "Recreating OAuth container to apply changes..."
    cd /opt/docker
    OUTPUT=$(docker-compose up -d oauth 2>&1)
    log_message "Docker compose output:"
    log_message "$OUTPUT"
else
    log_message "No changes detected, skipping OAuth container recreation."
fi
