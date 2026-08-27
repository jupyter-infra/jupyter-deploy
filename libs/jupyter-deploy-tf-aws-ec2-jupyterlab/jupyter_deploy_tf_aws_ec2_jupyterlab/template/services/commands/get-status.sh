#!/bin/bash
# Return code handling:
# - Uses 'set +e' (not 'set -e') to allow check-status-internal.sh to return semantic exit codes
# - check-status-internal.sh returns codes like 0=IN_SERVICE, 10=INITIALIZING, 20=STOPPED, etc.
# - This script maps those codes to status strings and always exits 0
# - Exiting 0 is correct: successfully querying the status (even if status is bad) is not an error
# - Would only exit non-zero if the query itself failed (e.g., permission denied)
set +e

sh /usr/local/bin/check-status-internal.sh >/dev/null
STATUS=$?

case $STATUS in
  0)
    echo "IN_SERVICE"
    ;;
  10)
    echo "INITIALIZING"
    ;;
  20)
    echo "STOPPED"
    ;;
  30)
    echo "FETCHING_CERTIFICATES"
    ;;
  40)
    echo "STARTING"
    ;;
  50)
    echo "OUT_OF_SERVICE"
    ;;
  *)
    echo "UNKNOWN"
    ;;
esac