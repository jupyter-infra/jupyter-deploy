# Read all command scripts from services/commands
data "local_file" "check_status" {
  filename = "${path.module}/../services/commands/check-status-internal.sh"
}

data "local_file" "get_status" {
  filename = "${path.module}/../services/commands/get-status.sh"
}

data "local_file" "update_server" {
  filename = "${path.module}/../services/commands/update-server.sh"
}

# Define SSM documents for all commands
locals {
  ssm_status_check   = <<DOC
schemaVersion: '2.2'
description: Check the status of the docker services in the instance.
mainSteps:
  - action: aws:runShellScript
    name: CheckStatus
    inputs:
      runCommand:
        - |
          sh /usr/local/bin/get-status.sh

DOC
  ssm_server_update  = <<DOC
schemaVersion: '2.2'
description: Control the server containers (start, stop, restart).
parameters:
  action:
    type: String
    description: "The action to perform on the server (start, stop, restart)."
    default: start
    allowedValues:
      - start
      - stop
      - restart
  service:
    type: String
    description: "The service to act on (all, jupyter, traefik or auth-sidecar)."
    default: all
    allowedValues:
      - all
      - jupyter
      - traefik
      - auth-sidecar
mainSteps:
  - action: aws:runShellScript
    name: UpdateServer
    inputs:
      runCommand:
        - |
          sh /usr/local/bin/update-server.sh {{action}} {{service}}
DOC
  ssm_server_logs    = <<DOC
schemaVersion: '2.2'
description: Returns the container logs.
parameters:
  service:
    type: String
    description: "The service whose logs to print (jupyter, traefik or auth-sidecar)."
    default: jupyter
    allowedValues:
      - jupyter
      - traefik
      - auth-sidecar
  extra:
    type: String
    description: "The additional parameters to pass to docker logs."
    default: "-n 100"
mainSteps:
  - action: aws:runShellScript
    name: Logs
    inputs:
      runCommand:
        - |
          if [ -z "{{extra}}" ]; then
            EXTRA="-n 100"
          else
            EXTRA="{{extra}}"
          fi
          docker logs {{service}} $EXTRA
DOC
  ssm_server_exec    = <<DOC
schemaVersion: '2.2'
description: Execute a command inside a service container.
parameters:
  service:
    type: String
    description: "The service in which to execute the command (jupyter, traefik or auth-sidecar)."
    default: jupyter
    allowedValues:
      - jupyter
      - traefik
      - auth-sidecar
  commands:
    type: String
    description: "The command to execute inside the container."
mainSteps:
  - action: aws:runShellScript
    name: ExecCommand
    inputs:
      runCommand:
        - |
          docker exec {{service}} {{commands}}
DOC
  ssm_server_connect = <<DOC
schemaVersion: '1.0'
description: Start an interactive shell session inside a service container.
sessionType: InteractiveCommands
parameters:
  service:
    type: String
    description: "The service container to connect to (jupyter or traefik)."
    default: jupyter
    allowedValues:
      - jupyter
      - traefik
properties:
  linux:
    commands: "case {{service}} in jupyter) docker exec -it {{service}} /bin/bash;; traefik) docker exec -it {{service}} /bin/sh;; esac"
    runAsElevated: true
DOC
}

# Create SSM documents for each command
resource "aws_ssm_document" "instance_status_check" {
  name            = "instance-status-check-${local.doc_postfix}"
  document_type   = "Command"
  document_format = "YAML"

  content = local.ssm_status_check
  tags    = local.combined_tags
}

resource "aws_ssm_document" "server_update" {
  name            = "server-update-${local.doc_postfix}"
  document_type   = "Command"
  document_format = "YAML"

  content = local.ssm_server_update
  tags    = local.combined_tags
}

resource "aws_ssm_document" "server_logs" {
  name            = "server-logs-${local.doc_postfix}"
  document_type   = "Command"
  document_format = "YAML"

  content = local.ssm_server_logs
  tags    = local.combined_tags
}

resource "aws_ssm_document" "server_exec" {
  name            = "server-exec-${local.doc_postfix}"
  document_type   = "Command"
  document_format = "YAML"

  content = local.ssm_server_exec
  tags    = local.combined_tags
}

resource "aws_ssm_document" "server_connect" {
  name            = "server-connect-${local.doc_postfix}"
  document_type   = "Session"
  document_format = "YAML"

  content = local.ssm_server_connect
  tags    = local.combined_tags
}
