#!/bin/bash
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
    echo "OUT_OF_SERVICE"
    ;;
  *)
    echo "UNKNOWN"
    ;;
esac