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

data "local_file" "update_allowlist" {
  filename = "${path.module}/../services/commands/update-allowlist.sh"
}

data "local_file" "get_allowlist" {
  filename = "${path.module}/../services/commands/get-allowlist.sh"
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
    description: "The service to act on (all, jupyter, traefik, auth-sidecar or bedrock-sidecar)."
    default: all
    allowedValues:
      - all
      - jupyter
      - traefik
      - auth-sidecar
      - bedrock-sidecar
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
    description: "The service whose logs to print (jupyter, traefik, auth-sidecar or bedrock-sidecar)."
    default: jupyter
    allowedValues:
      - jupyter
      - traefik
      - auth-sidecar
      - bedrock-sidecar
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
    description: "The service in which to execute the command (jupyter or traefik). The auth-sidecar image is distroless (no shell), so exec is not supported there."
    default: jupyter
    allowedValues:
      - jupyter
      - traefik
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
  ssm_users_update   = <<DOC
schemaVersion: '2.2'
description: Update the IAM user names allowlisted to access the app (recreates only auth-sidecar).
parameters:
  users:
    type: String
    description: "The IAM user names (comma-separated) to add, remove or set in the allowlist."
    # Constrain to comma-separated bare IAM names. This value is substituted into a root shell
    # by aws:runShellScript, so no whitespace or shell metacharacters (`;`, `$`, backticks, `&`,
    # `|`, newlines). IAM names allow [A-Za-z0-9+=,.@_-]; comma is the list separator.
    allowedPattern: "^[a-zA-Z0-9+=,.@_-]*$"
  action:
    type: String
    description: "The type of action to perform."
    default: add
    allowedValues:
      - add
      - remove
      - set
mainSteps:
  - action: aws:runShellScript
    name: UpdateAllowlistedUsers
    inputs:
      runCommand:
        - "sh /usr/local/bin/update-allowlist.sh users {{action}} {{users}}"
DOC
  ssm_teams_update   = <<DOC
schemaVersion: '2.2'
description: Update the IAM role names allowlisted to access the app (recreates only auth-sidecar).
parameters:
  teams:
    type: String
    description: "The IAM role names (comma-separated) to add, remove or set in the allowlist."
    # Constrain to comma-separated bare IAM names. This value is substituted into a root shell
    # by aws:runShellScript, so no whitespace or shell metacharacters (`;`, `$`, backticks, `&`,
    # `|`, newlines). IAM names allow [A-Za-z0-9+=,.@_-]; comma is the list separator.
    allowedPattern: "^[a-zA-Z0-9+=,.@_-]*$"
  action:
    type: String
    description: "The type of action to perform."
    default: add
    allowedValues:
      - add
      - remove
      - set
mainSteps:
  - action: aws:runShellScript
    name: UpdateAllowlistedRoles
    inputs:
      runCommand:
        - "sh /usr/local/bin/update-allowlist.sh roles {{action}} {{teams}}"
DOC
  ssm_auth_check     = <<DOC
schemaVersion: '2.2'
description: Read the IAM principal names allowlisted to access the app.
parameters:
  category:
    type: String
    description: "Which allowlist to read: 'users' (IAM users) or 'teams' (IAM roles)."
    default: users
    allowedValues:
      - users
      - teams
mainSteps:
  - action: aws:runShellScript
    name: GetAllowlist
    inputs:
      runCommand:
        - "sh /usr/local/bin/get-allowlist.sh {{category}}"
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

resource "aws_ssm_document" "auth_users_update" {
  name            = "auth-users-update-${local.doc_postfix}"
  document_type   = "Command"
  document_format = "YAML"

  content = local.ssm_users_update
  tags    = local.combined_tags
}

resource "aws_ssm_document" "auth_teams_update" {
  name            = "auth-teams-update-${local.doc_postfix}"
  document_type   = "Command"
  document_format = "YAML"

  content = local.ssm_teams_update
  tags    = local.combined_tags
}

resource "aws_ssm_document" "auth_check" {
  name            = "auth-check-${local.doc_postfix}"
  document_type   = "Command"
  document_format = "YAML"

  content = local.ssm_auth_check
  tags    = local.combined_tags
}
