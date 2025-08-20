#!/bin/bash
set -e

# Script to control the Jupyter server container and related services
# Usage: 
#   sudo sh update-server.sh start [all|jupyter|traefik|oauth]    - Start all services or a specific service
#   sudo sh update-server.sh stop [all|jupyter|traefik|oauth]     - Stop all services or a specific service
#   sudo sh update-server.sh restart [all|jupyter|traefik|oauth]  - Restart all services or a specific service

LOG_FILE="/var/log/jupyter-deploy/update-server.log"
DOCKER_DIR="/opt/docker"
STARTUP_SCRIPT="${DOCKER_DIR}/docker-startup.sh"

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"
exec 2> >(tee -a "$LOG_FILE" >&2)

ACTION=$1
SERVICE=${2:-all} # Default to 'all' if not specified

log_message() {
  local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
  echo "[$timestamp] $*" >> "$LOG_FILE"
}

validate_args() {
  # Validate action
  if [ "$ACTION" != "start" ] && [ "$ACTION" != "stop" ] && [ "$ACTION" != "restart" ]; then
    log_message "Error: Invalid action. Must be 'start', 'stop', or 'restart'"
    echo "Error: Invalid action. Must be 'start', 'stop', or 'restart'"
    echo "Usage: sudo update-server.sh [start|stop|restart] [all|jupyter|traefik|oauth]"
    exit 1
  fi

  # Validate service
  if [ "$SERVICE" != "all" ] && [ "$SERVICE" != "jupyter" ]; then
    log_message "Warning: Non-standard service specified: $SERVICE"
    echo "Warning: Non-standard service specified: $SERVICE"
    echo "Possible values are: 'all', 'jupyter', 'traefik' or 'oauth'"
  fi
}

start_services() {
  log_message "Starting services (service: $SERVICE)..."
  cd "$DOCKER_DIR"
  
  if [ "$SERVICE" = "all" ]; then
    log_message "Running startup script to start all services"
    sh "$STARTUP_SCRIPT"
  else
    log_message "Starting $SERVICE container"
    docker-compose up -d "$SERVICE"
  fi
  
  log_message "Services started successfully"
}

stop_services() {
  log_message "Stopping services (service: $SERVICE)..."
  cd "$DOCKER_DIR"
  
  if [ "$SERVICE" = "all" ]; then
    log_message "Stopping all containers"
    docker-compose down
  else
    log_message "Stopping $SERVICE container"
    docker-compose stop "$SERVICE"
  fi
  
  log_message "Services stopped successfully"
}

restart_services() {
  log_message "Restarting services (service: $SERVICE)..."
  cd "$DOCKER_DIR"
  
  if [ "$SERVICE" = "all" ]; then
    log_message "Stopping all containers"
    docker-compose down
    
    log_message "Starting all containers via startup script"
    sh "$STARTUP_SCRIPT"
  else
    log_message "Restarting $SERVICE container"
    docker-compose stop "$SERVICE"
    docker-compose up -d "$SERVICE"
  fi
  
  log_message "Services restarted successfully"
}

# Main execution
validate_args

case "$ACTION" in
  start)
    start_services
    ;;
  stop)
    stop_services
    ;;
  restart)
    restart_services
    ;;
esac

log_message "Server update completed: $ACTION $SERVICE"
echo "Server update completed: $ACTION $SERVICE"