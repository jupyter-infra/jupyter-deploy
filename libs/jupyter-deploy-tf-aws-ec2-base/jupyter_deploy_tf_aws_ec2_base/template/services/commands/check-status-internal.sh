#!/bin/bash
set -e

exec > >(tee -a /var/log/jupyter-deploy/check-status.log) 2>&1

# Required containers that must be running
REQUIRED_CONTAINERS=("jupyter" "traefik" "oauth")
ACME_FILE="/opt/docker/acme.json"
STARTED_FLAG="/opt/docker/started.txt"

log_message() {
  local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
  echo "[$timestamp] $*"
}

check_started_flag() {
  if [ ! -f "$STARTED_FLAG" ]; then
    return 1
  fi
  return 0
}

check_docker_running() {
  if ! docker info >/dev/null 2>&1; then
    return 1
  fi
  return 0
}

check_containers() {
  # Check if all containers exist
  for container in "${REQUIRED_CONTAINERS[@]}"; do
    container_status=$(docker ps --format json --filter "name=^${container}$" 2>/dev/null | jq -r '.Status // empty')

    if [ -z "$container_status" ]; then
      log_message "Stopped: container $container does not exist"
      return 2
    fi
    
    # Check if container is explicitly restarting
    if echo "$container_status" | grep -q "Restarting"; then
      log_message "Out-of-service: container $container is stuck in a restart loop"
      return 3
    fi

    # Check for excessive restarts
    if echo "$container_status" | grep -q "restarts)"; then
      restart_info=$(echo "$container_status" | grep -o '([0-9]* restarts)')
      restart_count=$(echo "$restart_info" | grep -o '[0-9]*')
      if [ "$restart_count" -gt 3 ]; then
        log_message "Out-of-service: container $container has restarted $restart_count times"
        return 3
      fi
    fi

    if echo "$container_status" | grep -q "(unhealthy)"; then
      log_message "Out-of-service: container $container is unhealthy"
      return 3
    fi

    # If the container has a health check but isn't healthy yet, mark it as initializing until the health check passes.
    if echo "$container_status" | grep -q "(health" && ! echo "$container_status" | grep -q "(healthy)"; then
      log_message "Starting: container $container is in transition health state"
      return 1  # Return 1 for starting state
    fi

    # if we get here, this container is OK
  done

  return 0
}

check_certs() {
  if [ ! -f "$ACME_FILE" ]; then
    log_message "Initializing: ACME file does not exist: $ACME_FILE"
    return 1
  fi
  
  if [ ! -s "$ACME_FILE" ] || [ "$(stat -c%s "$ACME_FILE")" -lt 500 ]; then
    log_message "Initializing: ACME file exists but either empty or too small to contain certs"
    return 1
  fi
  
  # Parse the certs file, check that it has at least one cert
  if jq -e '.letsencrypt.Certificates | length > 0' "$ACME_FILE" >/dev/null 2>&1; then
    return 0
  fi
  
  log_message "Initializing: ACME file does not have certificates yet"
  return 1
}

# Main status check
main() {
  set +e
  if ! check_started_flag; then
    exit 10 # INITIALIZING
  fi

  if ! check_docker_running; then
    exit 20 # STOPPED
  fi
  
  check_containers
  container_status=$?
  
  check_certs
  cert_status=$?
  set -e
  
  # Determine overall status
  if [ "$container_status" -eq 2 ]; then
    exit 20 # STOPPED
  elif [ "$cert_status" -eq 1 ]; then
    exit 30 # FETCHING_CERTIFICATES
  elif [ "$container_status" -eq 0 ] && [ "$cert_status" -eq 0 ]; then
    log_message "In-service: containers are running and TLS certificates are available"
    exit 0 # IN_SERVICE
  else
    echo 40 # OUT_OF_SERVICE
  fi
}

main