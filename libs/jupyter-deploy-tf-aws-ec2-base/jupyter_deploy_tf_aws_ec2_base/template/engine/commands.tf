# Read all command scripts from services/commands
data "local_file" "update_auth" {
  filename = "${path.module}/../services/commands/update-auth.sh"
}

data "local_file" "get_auth" {
  filename = "${path.module}/../services/commands/get-auth.sh"
}

data "local_file" "check_status" {
  filename = "${path.module}/../services/commands/check-status-internal.sh"
}

data "local_file" "get_status" {
  filename = "${path.module}/../services/commands/get-status.sh"
}

data "local_file" "refresh_oauth_cookie" {
  filename = "${path.module}/../services/commands/refresh-oauth-cookie.sh"
}

data "local_file" "update_server" {
  filename = "${path.module}/../services/commands/update-server.sh"
}

# Define SSM documents for all commands
locals {
  ssm_status_check   = <<DOC
schemaVersion: '2.2'
description: Check the status of the docker services and TLS certs in the instance.
mainSteps:
  - action: aws:runShellScript
    name: CheckStatus
    inputs:
      runCommand:
        - |
          sh /usr/local/bin/get-status.sh

DOC
  ssm_auth_check     = <<DOC
schemaVersion: '2.2'
description: Retrieve and print the auth settings.
parameters:
  category:
    type: String
    description: "The category of authorized entities to list."
    default: users
    allowedValues:
      - users
      - teams
      - org
mainSteps:
  - action: aws:runShellScript
    name: CheckAuth
    inputs:
      runCommand:
        - |
          sh /usr/local/bin/get-auth.sh {{category}}
DOC
  ssm_users_update   = <<DOC
schemaVersion: '2.2'
description: Update allowlisted GitHub usernames
parameters:
  users:
    type: String
    description: "The user names (comma-separated) to add, remove or set in the allowlist."
    # Constrain to comma-separated bare GitHub logins. This value is substituted into a root shell
    # by aws:runShellScript, so no whitespace or shell metacharacters (`;`, `$`, backticks, `&`,
    # `|`, newlines). GitHub logins are [A-Za-z0-9-]; comma is the list separator.
    allowedPattern: "^[a-zA-Z0-9,-]*$"
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
    name: UpdateAuthorizedUsers
    inputs:
      runCommand:
        - |
          sh /usr/local/bin/update-auth.sh users {{action}} {{users}}
DOC
  ssm_teams_update   = <<DOC
schemaVersion: '2.2'
description: Update allowlisted GitHub teams; you must have allowlisted a GitHub organization.
parameters:
  teams:
    type: String
    description: "The team names (comma-separated) to add, remove or set in the allowlist"
    # Constrain to comma-separated bare GitHub team slugs. This value is substituted into a root
    # shell by aws:runShellScript, so no whitespace or shell metacharacters (`;`, `$`, backticks,
    # `&`, `|`, newlines). Team slugs are [A-Za-z0-9-_.]; comma is the list separator.
    allowedPattern: "^[a-zA-Z0-9,._-]*$"
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
    name: UpdateAuthorizedTeams
    inputs:
      runCommand:
        - "sh /usr/local/bin/update-auth.sh teams {{action}} {{teams}}"
DOC
  ssm_org_set        = <<DOC
schemaVersion: '2.2'
description: Set the GitHub organization to allowlist; only one organization may be allowlisted at a time.
parameters:
  organization:
    type: String
    description: "The name of the GitHub organization to allowlist."
    # Same reasoning as the users/teams documents: substituted into a root shell, so restrict to
    # a bare GitHub org login ([A-Za-z0-9-]). Single-valued, so no comma.
    allowedPattern: "^[a-zA-Z0-9-]*$"
mainSteps:
  - action: aws:runShellScript
    name: SetAllowlistedOrganization
    inputs:
      runCommand:
        - "sh /usr/local/bin/update-auth.sh org {{organization}}"
DOC
  ssm_org_unset      = <<DOC
schemaVersion: '2.2'
description: Remove the GitHub organization; rely exclusively on username allowlisting.
mainSteps:
  - action: aws:runShellScript
    name: UnsetAllowlistOrganization
    inputs:
      runCommand:
        - |
          sh /usr/local/bin/update-auth.sh org remove
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
    description: "The service to act on (all, jupyter, traefik, oauth or bedrock-sidecar)."
    default: all
    allowedValues:
      - all
      - jupyter
      - traefik
      - oauth
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
    description: "The service whose logs to print (jupyter, traefik, oauth or bedrock-sidecar)."
    default: jupyter
    allowedValues:
      - jupyter
      - traefik
      - oauth
      - bedrock-sidecar
  extra:
    type: String
    description: "The additional parameters to pass to docker logs."
    default: "-n 100"
    # Substituted into a root shell, and `EXTRA="{{extra}}"` is double-quoted, so `$(...)` and
    # backticks would still expand. Restricted to what a docker-logs flag actually needs:
    # letters, digits, space, `-`, `.`, `:`, `=` covers `-n 100`, `--tail 5`, `--since 10m` and
    # `--since=2026-01-01T00:00:00`. No `;`, `$`, backtick, `&`, `|`, quote, or newline.
    allowedPattern: "^[a-zA-Z0-9 .:=-]*$"
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
    description: "The service in which to execute the command (jupyter, traefik or oauth)."
    default: jupyter
    allowedValues:
      - jupyter
      - traefik
      - oauth
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

locals {
  smm_auth_users_update = can(yamldecode(local.ssm_users_update))
}

# Create SSM documents for each command
resource "aws_ssm_document" "instance_status_check" {
  name            = "instance-status-check-${local.doc_postfix}"
  document_type   = "Command"
  document_format = "YAML"

  content = local.ssm_status_check
  tags    = local.combined_tags
}

resource "aws_ssm_document" "auth_check" {
  name            = "auth-check-${local.doc_postfix}"
  document_type   = "Command"
  document_format = "YAML"

  content = local.ssm_auth_check
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

resource "aws_ssm_document" "auth_org_set" {
  name            = "auth-org-set-${local.doc_postfix}"
  document_type   = "Command"
  document_format = "YAML"

  content = local.ssm_org_set
  tags    = local.combined_tags
}

resource "aws_ssm_document" "auth_org_unset" {
  name            = "auth-org-unset-${local.doc_postfix}"
  document_type   = "Command"
  document_format = "YAML"

  content = local.ssm_org_unset
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