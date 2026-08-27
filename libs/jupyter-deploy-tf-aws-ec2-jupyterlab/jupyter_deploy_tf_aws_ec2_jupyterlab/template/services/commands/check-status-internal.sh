#!/bin/bash
set -e

exec > >(tee -a /var/log/jupyter-deploy/check-status.log) 2>&1

REQUIRED_CONTAINERS=("jupyter" "traefik" "auth-sidecar")
CERT_FILE="/opt/docker/certs/cert.pem"
STARTED_FLAG="/opt/docker/started.txt"
STATUS_STATE_FILE="/var/run/check-status-state"

log_message() {
  local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
  echo "[$timestamp] $*"
}

get_previous_state() {
  if [ -f "$STATUS_STATE_FILE" ]; then
    cat "$STATUS_STATE_FILE"
  else
    echo ""
  fi
}

save_current_state() {
  local state=$1
  echo "$state" > "$STATUS_STATE_FILE"
}

check_started_flag() {
  if [ ! -f "$STARTED_FLAG" ]; then
    return 1
  fi
  return 0
}

check_docker_running() {
  if ! docker info >/dev/null 2>&1; then
    log_message "Docker daemon is not running"
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

    # If the container has a health check but isn't healthy yet
    # mark as initializing until the health check passes.
    if echo "$container_status" | grep -q "(health" && ! echo "$container_status" | grep -q "(healthy)"; then
      log_message "Starting: container $container is in transition health state"
      return 1  # Return 1 for starting state
    fi
    # container is OK
  done

  return 0
}

check_certs() {
  # Self-signed cert is generated at boot and copied to /opt/docker/certs. If missing,
  # the instance is still initializing (generate-cert.sh has not completed).
  if [ ! -s "$CERT_FILE" ]; then
    log_message "Initializing: self-signed cert not present yet: $CERT_FILE"
    return 1
  fi
  return 0
}

check_jupyter_ready() {
  # Try to reach a JupyterLab resource to verify it's functional
  if docker exec jupyter curl -sf "http://localhost:8888/lab/favicon.ico" >/dev/null 2>&1; then
    return 0
  else
    log_message "Containers running but Jupyter not ready yet"
    return 1
  fi
}

# Main status check
main() {
  set +e

  if ! check_started_flag; then
    save_current_state "INITIALIZING"
    exit 10 # INITIALIZING
  fi

  if ! check_docker_running; then
    save_current_state "STOPPED"
    exit 20 # STOPPED
  fi

  check_containers
  container_status=$?

  check_certs
  cert_status=$?
  set -e

  if [ "$container_status" -eq 2 ]; then
    save_current_state "STOPPED"
    exit 20 # STOPPED
  elif [ "$cert_status" -eq 1 ]; then
    save_current_state "FETCHING_CERTIFICATES"
    exit 30 # FETCHING_CERTIFICATES
  elif [ "$container_status" -eq 0 ] && [ "$cert_status" -eq 0 ]; then
    # Containers are running and certs are available, check if Jupyter is ready
    check_jupyter_ready
    jupyter_status=$?

    if [ "$jupyter_status" -eq 0 ]; then
      log_message "In-service: containers running, cert available, Jupyter responding"
      save_current_state "IN_SERVICE"
      exit 0 # IN_SERVICE
    else
      save_current_state "STARTING"
      exit 40 # STARTING (containers up but Jupyter not ready)
    fi
  else
    save_current_state "OUT_OF_SERVICE"
    exit 50 # OUT_OF_SERVICE
  fi
}

main