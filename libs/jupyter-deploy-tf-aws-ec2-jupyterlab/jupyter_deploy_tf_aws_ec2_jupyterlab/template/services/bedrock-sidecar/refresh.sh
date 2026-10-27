#!/bin/sh
# Publishes short-lived credentials for the Bedrock app role to a file the jupyter container
# reads through `credential_process = /bin/cat <file>`, hence the AWS SDK's JSON contract below.
#
# The instance role assumes the app role, which is role chaining: AWS caps chained sessions at
# 1 hour regardless of the role's MaxSessionDuration, so the loop asks for 3600 s and refreshes
# every 15 min. The file is written to a temp name and renamed so a reader never sees partial
# JSON, and made 0444 because this container runs as root while the jupyter user is unprivileged.
#
# Usage: refresh.sh                loop forever
#        refresh.sh -healthcheck   exit 0 iff the published Expiration is more than 5 min away
set -u

CREDS_FILE="${CREDS_FILE:-/creds/credentials.json}"
REFRESH_INTERVAL_S="${REFRESH_INTERVAL_S:-900}"

if [ "${1:-}" = "-healthcheck" ]; then
    expiration=$(sed -n 's/.*"Expiration": *"\([^"]*\)".*/\1/p' "$CREDS_FILE" 2>/dev/null) || exit 1
    [ -n "$expiration" ] || exit 1
    [ "$(date -d "$expiration" +%s)" -gt $(( $(date +%s) + 300 )) ]
    exit $?
fi

: "${BEDROCK_APP_ROLE_ARN:?BEDROCK_APP_ROLE_ARN is required}"

while true; do
    if credentials=$(aws sts assume-role --role-arn "$BEDROCK_APP_ROLE_ARN" --role-session-name jupyter \
            --duration-seconds 3600 \
            --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken,Expiration]' --output text) \
        && set -- $credentials && [ $# -eq 4 ]; then
        printf '{"Version": 1, "AccessKeyId": "%s", "SecretAccessKey": "%s", "SessionToken": "%s", "Expiration": "%s"}\n' \
            "$1" "$2" "$3" "$4" > "$CREDS_FILE.tmp"
        chmod 444 "$CREDS_FILE.tmp"
        mv -f "$CREDS_FILE.tmp" "$CREDS_FILE"
        sleep "$REFRESH_INTERVAL_S"
    else
        echo "assume-role for $BEDROCK_APP_ROLE_ARN failed; retrying in 30 s" >&2
        sleep 30
    fi
done
