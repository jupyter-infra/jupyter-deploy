#!/bin/bash
set -e

# Script to read the file containing the list of authorized GitHub entities (users, teams, orgs)
# Usage:
#   sudo sh get-auth.sh [users|teams|org]

LOG_FILE="/var/log/jupyter-deploy/get-auth.log"
touch "$LOG_FILE"
exec 2> >(tee -a "$LOG_FILE" >&2)

AUTHED_ENTITIES_FILE="/etc/AUTHED_ENTITIES"
ENTITY_TYPE=$1

log_message() {
  local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
  echo "[$timestamp] $*" >> "$LOG_FILE"
}

get_section_content() {
    local section=$1
    local content=$(sed -n "/^\[$section\]$/,/^\[/p" "$AUTHED_ENTITIES_FILE" | grep -v "^\[$section\]$" | grep -v "^\[" | tr -d '\n' | tr -d ' ')
    echo "$content"
}

if [ "$ENTITY_TYPE" == "org" ]; then
    ORG=$(get_section_content "org")
    log_message "Response [org]: $ORG"
    echo "$ORG"
elif [ "$ENTITY_TYPE" == "users" ]; then
    USERS=$(get_section_content "users")
    log_message "Response [users]: $USERS"
    echo "$USERS"
elif [ "$ENTITY_TYPE" == "teams" ]; then
    TEAMS=$(get_section_content "teams")
    log_message "Response [teams]: $TEAMS"
    echo "$TEAMS"
else
    RESULT="Error: Invalid entity type."
    log_message "$RESULT"
    echo "$RESULT Use 'org', 'teams', or 'users'." 
    exit 1
fi
