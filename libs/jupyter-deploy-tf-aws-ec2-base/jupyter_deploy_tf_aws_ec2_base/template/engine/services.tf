# Variables consistency checks
locals {
  github_auth_valid = var.oauth_provider != "github" || (var.oauth_allowed_usernames != null && length(var.oauth_allowed_usernames) > 0) || (var.oauth_allowed_org != null && length(var.oauth_allowed_org) > 0)
  teams_have_org    = var.oauth_allowed_teams == null || length(var.oauth_allowed_teams) == 0 || (var.oauth_allowed_org != null && length(var.oauth_allowed_org) > 0)
}

# Read the local files defining the instance and docker services setup
# Files for the UV (standard) environment
data "local_file" "dockerfile_jupyter" {
  filename = "${path.module}/../services/jupyter/dockerfile.jupyter"
}

data "local_file" "jupyter_start" {
  filename = "${path.module}/../services/jupyter/jupyter-start.sh"
}

data "local_file" "jupyter_reset" {
  filename = "${path.module}/../services/jupyter/jupyter-reset.sh"
}

data "local_file" "jupyter_server_config_uv" {
  filename = "${path.module}/../services/jupyter/jupyter_server_config.py"
}

# Files for the Pixi environment
data "local_file" "dockerfile_jupyter_pixi" {
  filename = "${path.module}/../services/jupyter-pixi/dockerfile.jupyter.pixi"
}

data "local_file" "jupyter_start_pixi" {
  filename = "${path.module}/../services/jupyter-pixi/jupyter-start-pixi.sh"
}

data "local_file" "jupyter_reset_pixi" {
  filename = "${path.module}/../services/jupyter-pixi/jupyter-reset-pixi.sh"
}

data "local_file" "jupyter_server_config_pixi" {
  filename = "${path.module}/../services/jupyter-pixi/jupyter_server_config_pixi.py"
}

# Other services
data "local_file" "dockerfile_logrotator" {
  filename = "${path.module}/../services/logrotator/dockerfile.logrotator"
}

data "local_file" "fluent_bit_conf" {
  filename = "${path.module}/../services/fluent-bit/fluent-bit.conf"
}

data "local_file" "parsers_conf" {
  filename = "${path.module}/../services/fluent-bit/parsers.conf"
}

data "local_file" "cloudinit_volumes_tftpl" {
  filename = "${path.module}/../services/cloudinit-volumes.sh.tftpl"
}

data "local_file" "oauth_error_500_html_tftpl" {
  filename = "${path.module}/../services/static/oauth_error_500.html.tftpl"
}

data "local_file" "service_unavailable_html_tftpl" {
  filename = "${path.module}/../services/static/service_unavailable.html.tftpl"
}

data "local_file" "pyproject_jupyter" {
  filename = "${path.module}/../services/jupyter/pyproject.jupyter.toml"
}

data "local_file" "pyproject_kernel_uv" {
  filename = "${path.module}/../services/jupyter/pyproject.kernel.toml"
}

data "local_file" "pyproject_kernel_pixi" {
  filename = "${path.module}/../services/jupyter-pixi/pyproject.kernel.toml"
}

locals {
  # Generate the templated HTML files
  oauth_error_500_templated = templatefile("${path.module}/../services/static/oauth_error_500.html.tftpl", {
    full_domain = module.network.full_domain
  })

  service_unavailable_templated = templatefile("${path.module}/../services/static/service_unavailable.html.tftpl", {
    full_domain = module.network.full_domain
  })

  # TOML files - most are now static, only pixi.jupyter.toml needs templating for cpu_architecture
  pyproject_jupyter_content = data.local_file.pyproject_jupyter.content

  pixi_jupyter_templated = templatefile("${path.module}/../services/jupyter-pixi/pixi.jupyter.toml.tftpl", {
    cpu_architecture = module.ami_al2023.cpu_architecture
  })

  kernel_uv_content = data.local_file.pyproject_kernel_uv.content

  kernel_pixi_content = data.local_file.pyproject_kernel_pixi.content

  # Select the correct files based on package manager type
  dockerfile_content            = var.jupyter_package_manager == "pixi" ? data.local_file.dockerfile_jupyter_pixi.content : data.local_file.dockerfile_jupyter.content
  jupyter_toml_content          = var.jupyter_package_manager == "pixi" ? local.pixi_jupyter_templated : local.pyproject_jupyter_content
  jupyter_start_content         = var.jupyter_package_manager == "pixi" ? data.local_file.jupyter_start_pixi.content : data.local_file.jupyter_start.content
  jupyter_reset_content         = var.jupyter_package_manager == "pixi" ? data.local_file.jupyter_reset_pixi.content : data.local_file.jupyter_reset.content
  jupyter_server_config_content = var.jupyter_package_manager == "pixi" ? data.local_file.jupyter_server_config_pixi.content : data.local_file.jupyter_server_config_uv.content
  kernel_pyproject_content      = var.jupyter_package_manager == "pixi" ? local.kernel_pixi_content : local.kernel_uv_content
  jupyter_toml_filename         = var.jupyter_package_manager == "pixi" ? "pixi.jupyter.toml" : "pyproject.jupyter.toml"

  # Compute hash of all files that affect docker compose image builds (jupyter, log-rotator)
  # This hash is used to determine if a rebuild is necessary
  build_affecting_files = [
    local.dockerfile_content,
    local.jupyter_toml_content,
    local.jupyter_start_content,
    local.jupyter_reset_content,
    local.jupyter_server_config_content,
    local.kernel_pyproject_content,
    data.local_file.dockerfile_logrotator.content,
    local.logrotator_start_file,
  ]
  images_build_hash = sha256(join("\n", local.build_affecting_files))

  allowed_github_usernames = var.oauth_allowed_usernames != null ? join(",", [for username in var.oauth_allowed_usernames : "${username}"]) : ""
  allowed_github_org       = var.oauth_allowed_org != null ? var.oauth_allowed_org : ""
  allowed_github_teams     = var.oauth_allowed_teams != null ? join(",", [for team in var.oauth_allowed_teams : "${team}"]) : ""
  cloud_init_file = templatefile("${path.module}/../services/cloudinit.sh.tftpl", {
    allowed_github_usernames = local.allowed_github_usernames
    allowed_github_org       = local.allowed_github_org
    allowed_github_teams     = local.allowed_github_teams
  })
  docker_startup_file = templatefile("${path.module}/../services/docker-startup.sh.tftpl", {
    oauth_secret_arn = module.secret.secret_arn,
  })
  sync_acme_file = templatefile("${path.module}/../services/sync-acme.sh.tftpl", {
    certs_secret_arn = module.certs_secret.secret_arn,
    full_domain      = module.network.full_domain,
  })
  upload_acme_file = templatefile("${path.module}/../services/commands/upload-acme.sh.tftpl", {
    certs_secret_arn = module.certs_secret.secret_arn,
  })
  docker_compose_file = templatefile("${path.module}/../services/docker-compose.yml.tftpl", {
    oauth_provider           = var.oauth_provider
    full_domain              = module.network.full_domain
    github_client_id         = var.oauth_app_client_id
    aws_region               = data.aws_region.current.id
    allowed_github_usernames = local.allowed_github_usernames
    allowed_github_org       = local.allowed_github_org
    allowed_github_teams     = local.allowed_github_teams
    ebs_mounts               = module.volumes.resolved_ebs_mounts
    efs_mounts               = module.volumes.resolved_efs_mounts
    has_gpu                  = module.ami_al2023.has_gpu
    has_neuron               = module.ami_al2023.has_neuron
  })
  traefik_config_file = templatefile("${path.module}/../services/traefik/traefik.yml.tftpl", {
    letsencrypt_notification_email = var.letsencrypt_email
  })
  logrotator_start_file = templatefile("${path.module}/../services/logrotator/logrotator-start.sh.tftpl", {
    logrotate_size   = "${var.log_files_rotation_size_mb}M"
    logrotate_copies = var.log_files_retention_count
    logrotate_maxage = var.log_files_retention_days
  })
}

# Map of all script files to upload to S3
# These files will be downloaded by the SSM document instead of being embedded
# Note: cloudinit.sh and cloudinit-volumes.sh remain embedded in SSM document for visibility
locals {
  # Lists of filenames for SSM document downloads
  deployment_scripts_filenames = ["update-auth.sh", "refresh-oauth-cookie.sh", "check-status-internal.sh", "get-status.sh", "get-auth.sh", "update-server.sh", "upload-acme.sh", "sync-acme.sh"]
  deployment_docker_filenames  = ["docker-compose.yml", "traefik.yml", "dockerfile.jupyter", "jupyter-start.sh", "jupyter-reset.sh", "pyproject.kernel.toml", "jupyter_server_config.py", "dockerfile.logrotator", "logrotator-start.sh", "fluent-bit.conf", "parsers.conf", ".build-manifest"]

  all_script_files = {
    # Startup scripts (docker-startup only, cloudinit stays in SSM)
    "deployment-scripts/docker-startup.sh" = {
      content      = local.docker_startup_file
      content_type = "text/x-shellscript"
    }

    # Utility scripts from commands
    "deployment-scripts/update-auth.sh" = {
      content      = data.local_file.update_auth.content
      content_type = "text/x-shellscript"
    }
    "deployment-scripts/refresh-oauth-cookie.sh" = {
      content      = data.local_file.refresh_oauth_cookie.content
      content_type = "text/x-shellscript"
    }
    "deployment-scripts/check-status-internal.sh" = {
      content      = data.local_file.check_status.content
      content_type = "text/x-shellscript"
    }
    "deployment-scripts/get-status.sh" = {
      content      = data.local_file.get_status.content
      content_type = "text/x-shellscript"
    }
    "deployment-scripts/get-auth.sh" = {
      content      = data.local_file.get_auth.content
      content_type = "text/x-shellscript"
    }
    "deployment-scripts/update-server.sh" = {
      content      = data.local_file.update_server.content
      content_type = "text/x-shellscript"
    }
    "deployment-scripts/upload-acme.sh" = {
      content      = local.upload_acme_file
      content_type = "text/x-shellscript"
    }
    "deployment-scripts/sync-acme.sh" = {
      content      = local.sync_acme_file
      content_type = "text/x-shellscript"
    }
    # Docker and service configuration files
    "deployment-docker/docker-compose.yml" = {
      content      = local.docker_compose_file
      content_type = "text/yaml"
    }
    "deployment-docker/dockerfile.jupyter" = {
      content      = local.dockerfile_content
      content_type = "text/plain"
    }
    "deployment-docker/${local.jupyter_toml_filename}" = {
      content      = local.jupyter_toml_content
      content_type = "text/plain"
    }
    "deployment-docker/pyproject.kernel.toml" = {
      content      = local.kernel_pyproject_content
      content_type = "text/plain"
    }
    "deployment-docker/jupyter-start.sh" = {
      content      = local.jupyter_start_content
      content_type = "text/x-shellscript"
    }
    "deployment-docker/jupyter-reset.sh" = {
      content      = local.jupyter_reset_content
      content_type = "text/x-shellscript"
    }
    "deployment-docker/jupyter_server_config.py" = {
      content      = local.jupyter_server_config_content
      content_type = "text/x-python"
    }
    "deployment-docker/traefik.yml" = {
      content      = local.traefik_config_file
      content_type = "text/yaml"
    }
    "deployment-docker/dockerfile.logrotator" = {
      content      = data.local_file.dockerfile_logrotator.content
      content_type = "text/plain"
    }
    "deployment-docker/logrotator-start.sh" = {
      content      = local.logrotator_start_file
      content_type = "text/x-shellscript"
    }
    "deployment-docker/fluent-bit.conf" = {
      content      = data.local_file.fluent_bit_conf.content
      content_type = "text/plain"
    }
    "deployment-docker/parsers.conf" = {
      content      = data.local_file.parsers_conf.content
      content_type = "text/plain"
    }
    "deployment-docker/static/oauth_error_500.html" = {
      content      = local.oauth_error_500_templated
      content_type = "text/html"
    }
    "deployment-docker/static/service_unavailable.html" = {
      content      = local.service_unavailable_templated
      content_type = "text/html"
    }
    "deployment-docker/.build-manifest" = {
      content      = local.images_build_hash
      content_type = "text/plain"
    }
  }

  # Compute hash of all deployment script files
  # This hash triggers SSM association re-execution when scripts change
  scripts_files_hash = sha256(join("\n", [for k, v in local.all_script_files : v.content]))

  # Compute hash of SSM-embedded scripts (cloud-init + volume-init)
  # These are not in all_script_files but are embedded directly in the SSM document.
  # Changes to these (e.g. volume configuration) must also trigger re-execution.
  ssm_embedded_hash = sha256(join("\n", [local.cloud_init_file, local.cloudinit_volumes_script]))
}

# Generate the cloudinit_volumes_script directly in services.tf
locals {
  # Generate the cloudinit script for mounting volumes
  cloudinit_volumes_script = templatefile("${path.module}/../services/cloudinit-volumes.sh.tftpl", {
    ebs_volumes = module.volumes.resolved_ebs_mounts
    efs_volumes = module.volumes.resolved_efs_mounts
    aws_region  = data.aws_region.current.id
  })
}

# SSM into the instance and execute the start-up scripts
locals {
  # In order to inject the file content with the correct
  indent_count                   = 10
  indent_str                     = join("", [for i in range(local.indent_count) : " "])
  cloud_init_indented            = join("\n${local.indent_str}", compact(split("\n", local.cloud_init_file)))
  docker_compose_indented        = join("\n${local.indent_str}", compact(split("\n", local.docker_compose_file)))
  dockerfile_jupyter_indented    = join("\n${local.indent_str}", compact(split("\n", local.dockerfile_content)))
  jupyter_start_indented         = join("\n${local.indent_str}", compact(split("\n", local.jupyter_start_content)))
  jupyter_reset_indented         = join("\n${local.indent_str}", compact(split("\n", local.jupyter_reset_content)))
  docker_startup_indented        = join("\n${local.indent_str}", compact(split("\n", local.docker_startup_file)))
  toml_jupyter_indented          = join("\n${local.indent_str}", compact(split("\n", local.jupyter_toml_content)))
  pyproject_kernel_indented      = join("\n${local.indent_str}", compact(split("\n", local.kernel_pyproject_content)))
  jupyter_server_config_indented = join("\n${local.indent_str}", compact(split("\n", local.jupyter_server_config_content)))
  traefik_config_indented        = join("\n${local.indent_str}", compact(split("\n", local.traefik_config_file)))
  dockerfile_logrotator_indented = join("\n${local.indent_str}", compact(split("\n", data.local_file.dockerfile_logrotator.content)))
  fluent_bit_conf_indented       = join("\n${local.indent_str}", compact(split("\n", data.local_file.fluent_bit_conf.content)))
  parsers_conf_indented          = join("\n${local.indent_str}", compact(split("\n", data.local_file.parsers_conf.content)))
  logrotator_start_file_indented = join("\n${local.indent_str}", compact(split("\n", local.logrotator_start_file)))
  update_auth_indented           = join("\n${local.indent_str}", compact(split("\n", data.local_file.update_auth.content)))
  refresh_oauth_cookie_indented  = join("\n${local.indent_str}", compact(split("\n", data.local_file.refresh_oauth_cookie.content)))
  check_status_indented          = join("\n${local.indent_str}", compact(split("\n", data.local_file.check_status.content)))
  get_status_indented            = join("\n${local.indent_str}", compact(split("\n", data.local_file.get_status.content)))
  get_auth_indented              = join("\n${local.indent_str}", compact(split("\n", data.local_file.get_auth.content)))
  update_server_indented         = join("\n${local.indent_str}", compact(split("\n", data.local_file.update_server.content)))
  oauth_error_500_indented       = join("\n${local.indent_str}", compact(split("\n", local.oauth_error_500_templated)))
  cloudinit_volumes_indented     = join("\n${local.indent_str}", compact(split("\n", local.cloudinit_volumes_script)))
}

locals {
  ssm_startup_content = <<DOC
schemaVersion: '2.2'
description: Setup docker, mount volumes, copy docker-compose, start docker services
mainSteps:
  - action: aws:runShellScript
    name: DownloadUtilityScripts
    inputs:
      onFailure: exit
      runCommand:
        - |
          mkdir -p /usr/local/bin
          mkdir -p /var/log/jupyter-deploy
          for script in ${join(" ", local.deployment_scripts_filenames)}; do
            aws s3 cp s3://${module.s3_bucket.bucket_name}/deployment-scripts/$script /usr/local/bin/$script
            chmod 755 /usr/local/bin/$script
          done
          chmod 644 /usr/local/bin/update-auth.sh /usr/local/bin/refresh-oauth-cookie.sh

  - action: aws:runShellScript
    name: CloudInit
    inputs:
      onFailure: exit
      runCommand:
        - |
          ${local.cloud_init_indented}

  - action: aws:runShellScript
    name: MountAdditionalVolumes
    inputs:
      onFailure: exit
      runCommand:
        - |
          ${local.cloudinit_volumes_indented}

  - action: aws:runShellScript
    name: DownloadDockerFiles
    inputs:
      onFailure: exit
      runCommand:
        - |
          BUCKET="${module.s3_bucket.bucket_name}"
          mkdir -p /opt/docker/static

          aws s3 cp s3://$BUCKET/deployment-docker/static/oauth_error_500.html /opt/docker/static/oauth_error_500.html
          aws s3 cp s3://$BUCKET/deployment-docker/static/service_unavailable.html /opt/docker/static/service_unavailable.html

          for file in ${join(" ", local.deployment_docker_filenames)}; do
            aws s3 cp s3://$BUCKET/deployment-docker/$file /opt/docker/$file
          done

          aws s3 cp s3://$BUCKET/deployment-scripts/docker-startup.sh /opt/docker/docker-startup.sh
          chmod 755 /opt/docker/docker-startup.sh
          aws s3 cp s3://$BUCKET/deployment-docker/${local.jupyter_toml_filename} /opt/docker/${local.jupyter_toml_filename}

  - action: aws:runShellScript
    name: SyncCertificates
    inputs:
      onFailure: exit
      runCommand:
        - |
          sh /usr/local/bin/sync-acme.sh

  - action: aws:runShellScript
    name: StartDockerServices
    inputs:
      onFailure: exit
      runCommand:
        - |
          sh /opt/docker/docker-startup.sh
DOC

  # Additional validations
  has_required_files = alltrue([
    fileexists("${path.module}/../services/jupyter/dockerfile.jupyter"),
    fileexists("${path.module}/../services/jupyter/jupyter-start.sh"),
    fileexists("${path.module}/../services/jupyter/jupyter-reset.sh"),
    fileexists("${path.module}/../services/jupyter/jupyter_server_config.py"),
    fileexists("${path.module}/../services/jupyter/pyproject.jupyter.toml"),
    fileexists("${path.module}/../services/jupyter/pyproject.kernel.toml"),
    fileexists("${path.module}/../services/jupyter-pixi/dockerfile.jupyter.pixi"),
    fileexists("${path.module}/../services/jupyter-pixi/jupyter-start-pixi.sh"),
    fileexists("${path.module}/../services/jupyter-pixi/jupyter-reset-pixi.sh"),
    fileexists("${path.module}/../services/jupyter-pixi/jupyter_server_config_pixi.py"),
    fileexists("${path.module}/../services/jupyter-pixi/pixi.jupyter.toml.tftpl"),
    fileexists("${path.module}/../services/jupyter-pixi/pyproject.kernel.toml"),
    fileexists("${path.module}/../services/logrotator/dockerfile.logrotator"),
    fileexists("${path.module}/../services/commands/update-auth.sh"),
    fileexists("${path.module}/../services/commands/refresh-oauth-cookie.sh"),
    fileexists("${path.module}/../services/commands/check-status-internal.sh"),
    fileexists("${path.module}/../services/commands/get-status.sh"),
    fileexists("${path.module}/../services/commands/get-auth.sh"),
    fileexists("${path.module}/../services/commands/update-server.sh"),
    fileexists("${path.module}/../services/commands/upload-acme.sh.tftpl"),
    fileexists("${path.module}/../services/sync-acme.sh.tftpl"),
    fileexists("${path.module}/../services/static/oauth_error_500.html.tftpl"),
    fileexists("${path.module}/../services/static/service_unavailable.html.tftpl"),
  ])

  files_not_empty = alltrue([
    length(data.local_file.dockerfile_jupyter) > 0,
    length(data.local_file.jupyter_start) > 0,
    length(data.local_file.jupyter_reset) > 0,
    length(data.local_file.jupyter_server_config_uv) > 0,
    length(data.local_file.pyproject_jupyter) > 0,
    length(data.local_file.pyproject_kernel_uv) > 0,
    length(data.local_file.dockerfile_jupyter_pixi) > 0,
    length(data.local_file.jupyter_start_pixi) > 0,
    length(data.local_file.jupyter_reset_pixi) > 0,
    length(data.local_file.jupyter_server_config_pixi) > 0,
    length(data.local_file.pyproject_kernel_pixi) > 0,
    length(data.local_file.dockerfile_logrotator) > 0,
    length(data.local_file.update_auth) > 0,
    length(data.local_file.refresh_oauth_cookie) > 0,
    length(data.local_file.check_status) > 0,
    length(data.local_file.get_status) > 0,
    length(data.local_file.get_auth) > 0,
    length(data.local_file.update_server) > 0,
    length(local.upload_acme_file) > 0,
    length(local.sync_acme_file) > 0,
    length(data.local_file.oauth_error_500_html_tftpl) > 0,
    length(data.local_file.service_unavailable_html_tftpl) > 0,
  ])

  docker_compose_valid = can(yamldecode(local.docker_compose_file))
  ssm_content_valid    = can(yamldecode(local.ssm_startup_content))
  traefik_config_valid = can(yamldecode(local.traefik_config_file))
}

resource "aws_ssm_document" "instance_startup" {
  name            = "instance-startup-${local.doc_postfix}"
  document_type   = "Command"
  document_format = "YAML"

  content = local.ssm_startup_content
  tags    = local.combined_tags

  lifecycle {
    precondition {
      condition     = local.github_auth_valid
      error_message = "If you use github as oauth provider, provide at least 1 github username OR 1 github organization"
    }
    precondition {
      condition     = local.teams_have_org
      error_message = "GitHub teams require an organization. If you specify oauth_allowed_teams, you must also specify oauth_allowed_org"
    }
    precondition {
      condition     = local.has_required_files
      error_message = "One or more required files are missing"
    }
    precondition {
      condition     = local.files_not_empty
      error_message = "One or more required files are empty"
    }
    precondition {
      condition     = length(local.ssm_startup_content) < 30000 # SSM Document hard limit is 65kB. Keep ample buffer.
      error_message = "SSM document content exceeds size limit (current: ${length(local.ssm_startup_content)} bytes, max: 30000)"
    }
    precondition {
      condition     = local.ssm_content_valid
      error_message = "SSM document is not a valid YAML"
    }
    precondition {
      condition     = local.docker_compose_valid
      error_message = "Docker compose is not a valid YAML"
    }
    precondition {
      condition     = local.traefik_config_valid
      error_message = "traefik.yml file is not a valid YAML"
    }
  }
}

# Trigger for forcing SSM association re-execution when scripts change or instance type changes
resource "terraform_data" "scripts_files_trigger" {
  input = {
    scripts_files_hash = local.scripts_files_hash
    ssm_embedded_hash  = local.ssm_embedded_hash
    instance_type      = var.instance_type
  }
}

resource "aws_ssm_association" "instance_startup_with_secret" {
  name = aws_ssm_document.instance_startup.name
  targets {
    key    = "InstanceIds"
    values = [module.ec2_instance.id]
  }
  automation_target_parameter_name = "InstanceIds"
  max_concurrency                  = "1"
  max_errors                       = "0"
  wait_for_success_timeout_seconds = 300
  tags                             = local.combined_tags

  lifecycle {
    replace_triggered_by = [
      terraform_data.scripts_files_trigger.output
    ]
  }

  depends_on = [
    module.secret,
    module.ec2_instance,
    module.volumes
  ]
}
