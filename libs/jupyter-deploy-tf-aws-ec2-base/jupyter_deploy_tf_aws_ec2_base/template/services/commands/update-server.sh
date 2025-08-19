#!/bin/bash
set -e

# Script to control the Jupyter server container and related services
# Usage: 
#   sudo sh update-server.sh start [all|jupyter]    - Start all services or just jupyter
#   sudo sh update-server.sh stop [all|jupyter]     - Stop all services or just jupyter
#   sudo sh update-server.sh restart [all|jupyter]  - Restart all services or just jupyter

LOG_FILE="/var/log/jupyter-deploy/update-server.log"
DOCKER_DIR="/opt/docker"
STARTUP_SCRIPT="${DOCKER_DIR}/docker-startup.sh"

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"
exec 2> >(tee -a "$LOG_FILE" >&2)

ACTION=$1
TARGET=${2:-all} # Default to 'all' if not specified

log_message() {
  local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
  echo "[$timestamp] $*" >> "$LOG_FILE"
}

validate_args() {
  # Validate action
  if [ "$ACTION" != "start" ] && [ "$ACTION" != "stop" ] && [ "$ACTION" != "restart" ]; then
    log_message "Error: Invalid action. Must be 'start', 'stop', or 'restart'"
    echo "Error: Invalid action. Must be 'start', 'stop', or 'restart'"
    echo "Usage: sudo update-server.sh [start|stop|restart] [all|jupyter]"
    exit 1
  fi

  # Validate target
  if [ "$TARGET" != "all" ] && [ "$TARGET" != "jupyter" ]; then
    log_message "Error: Invalid target. Must be 'all' or 'jupyter'"
    echo "Error: Invalid target. Must be 'all' or 'jupyter'"
    echo "Usage: sudo update-server.sh [start|stop|restart] [all|jupyter]"
    exit 1
  fi
}

start_services() {
  log_message "Starting services (target: $TARGET)..."
  cd "$DOCKER_DIR"
  
  if [ "$TARGET" = "all" ]; then
    log_message "Running startup script to start all services"
    sh "$STARTUP_SCRIPT"
  else
    log_message "Starting jupyter container"
    docker-compose up -d jupyter
  fi
  
  log_message "Services started successfully"
}

stop_services() {
  log_message "Stopping services (target: $TARGET)..."
  cd "$DOCKER_DIR"
  
  if [ "$TARGET" = "all" ]; then
    log_message "Stopping all containers"
    docker-compose down
  else
    log_message "Stopping jupyter container"
    docker-compose stop jupyter
  fi
  
  log_message "Services stopped successfully"
}

restart_services() {
  log_message "Restarting services (target: $TARGET)..."
  cd "$DOCKER_DIR"
  
  if [ "$TARGET" = "all" ]; then
    log_message "Stopping all containers"
    docker-compose down
    
    log_message "Starting all containers via startup script"
    sh "$STARTUP_SCRIPT"
  else
    log_message "Restarting jupyter container"
    docker-compose stop jupyter
    docker-compose up -d jupyter
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

log_message "Server update completed: $ACTION $TARGET"
echo "Server update completed: $ACTION $TARGET"