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

locals {
  # Generate the templated TOML files
  pyproject_jupyter_templated = templatefile("${path.module}/../services/jupyter/pyproject.jupyter.toml.tftpl", {
    has_gpu    = module.ami_al2023.has_gpu
    has_neuron = module.ami_al2023.has_neuron
  })

  pixi_jupyter_templated = templatefile("${path.module}/../services/jupyter-pixi/pixi.jupyter.toml.tftpl", {
    has_gpu          = module.ami_al2023.has_gpu
    has_neuron       = module.ami_al2023.has_neuron
    cpu_architecture = module.ami_al2023.cpu_architecture
  })

  kernel_templated = templatefile("${path.module}/../services/jupyter/pyproject.kernel.toml.tftpl", {
    has_gpu    = module.ami_al2023.has_gpu
    has_neuron = module.ami_al2023.has_neuron
  })

  pixi_kernel_templated = templatefile("${path.module}/../services/jupyter-pixi/pyproject.kernel.toml.tftpl", {
    has_gpu    = module.ami_al2023.has_gpu
    has_neuron = module.ami_al2023.has_neuron
  })

  # Select the correct files based on package manager type
  dockerfile_content            = var.jupyter_package_manager == "pixi" ? data.local_file.dockerfile_jupyter_pixi.content : data.local_file.dockerfile_jupyter.content
  jupyter_toml_content          = var.jupyter_package_manager == "pixi" ? local.pixi_jupyter_templated : local.pyproject_jupyter_templated
  jupyter_start_content         = var.jupyter_package_manager == "pixi" ? data.local_file.jupyter_start_pixi.content : data.local_file.jupyter_start.content
  jupyter_reset_content         = var.jupyter_package_manager == "pixi" ? data.local_file.jupyter_reset_pixi.content : data.local_file.jupyter_reset.content
  jupyter_server_config_content = var.jupyter_package_manager == "pixi" ? data.local_file.jupyter_server_config_pixi.content : data.local_file.jupyter_server_config_uv.content
  kernel_pyproject_content      = var.jupyter_package_manager == "pixi" ? local.pixi_kernel_templated : local.kernel_templated
  jupyter_toml_filename         = var.jupyter_package_manager == "pixi" ? "pixi.jupyter.toml" : "pyproject.jupyter.toml"

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
  docker_compose_file = templatefile("${path.module}/../services/docker-compose.yml.tftpl", {
    oauth_provider           = var.oauth_provider
    full_domain              = module.network.full_domain
    github_client_id         = var.oauth_app_client_id
    aws_region               = data.aws_region.current.region
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

# Generate the cloudinit_volumes_script directly in services.tf
locals {
  # Generate the cloudinit script for mounting volumes
  cloudinit_volumes_script = templatefile("${path.module}/../services/cloudinit-volumes.sh.tftpl", {
    ebs_volumes = module.volumes.resolved_ebs_mounts
    efs_volumes = module.volumes.resolved_efs_mounts
    aws_region  = data.aws_region.current.region
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
  cloudinit_volumes_indented     = join("\n${local.indent_str}", compact(split("\n", local.cloudinit_volumes_script)))
}

locals {
  ssm_startup_content = <<DOC
schemaVersion: '2.2'
description: Setup docker, mount volumes, copy docker-compose, start docker services
mainSteps:
  - action: aws:runShellScript
    name: CloudInit
    inputs:
      runCommand:
        - |
          ${local.cloud_init_indented}

  - action: aws:runShellScript
    name: MountAdditionalVolumes
    inputs:
      runCommand:
        - |
          ${local.cloudinit_volumes_indented}

  - action: aws:runShellScript
    name: SaveDockerFiles
    inputs:
      runCommand:
        - |
          tee /opt/docker/docker-compose.yml << 'EOF'
          ${local.docker_compose_indented}
          EOF
          tee /opt/docker/traefik.yml << 'EOF'
          ${local.traefik_config_indented}
          EOF
          tee /opt/docker/docker-startup.sh << 'EOF'
          ${local.docker_startup_indented}
          EOF
          tee /opt/docker/dockerfile.jupyter << 'EOF'
          ${local.dockerfile_jupyter_indented}
          EOF
          tee /opt/docker/jupyter-start.sh << 'EOF'
          ${local.jupyter_start_indented}
          EOF
          tee /opt/docker/jupyter-reset.sh << 'EOF'
          ${local.jupyter_reset_indented}
          EOF
          tee /opt/docker/${local.jupyter_toml_filename} << 'EOF'
          ${local.toml_jupyter_indented}
          EOF
          tee /opt/docker/pyproject.kernel.toml << 'EOF'
          ${local.pyproject_kernel_indented}
          EOF
          tee /opt/docker/jupyter_server_config.py << 'EOF'
          ${local.jupyter_server_config_indented}
          EOF
          tee /opt/docker/dockerfile.logrotator << 'EOF'
          ${local.dockerfile_logrotator_indented}
          EOF
          tee /opt/docker/logrotator-start.sh << 'EOF'
          ${local.logrotator_start_file_indented}
          EOF
          tee /opt/docker/fluent-bit.conf << 'EOF'
          ${local.fluent_bit_conf_indented}
          EOF
          tee /opt/docker/parsers.conf << 'EOF'
          ${local.parsers_conf_indented}
          EOF
          tee /usr/local/bin/update-auth.sh << 'EOF'
          ${local.update_auth_indented}
          EOF
          chmod 644 /usr/local/bin/update-auth.sh
          tee /usr/local/bin/refresh-oauth-cookie.sh << 'EOF'
          ${local.refresh_oauth_cookie_indented}
          EOF
          chmod 644 /usr/local/bin/refresh-oauth-cookie.sh
          tee /usr/local/bin/check-status-internal.sh << 'EOF'
          ${local.check_status_indented}
          EOF
          tee /usr/local/bin/get-status.sh << 'EOF'
          ${local.get_status_indented}
          EOF
          tee /usr/local/bin/get-auth.sh << 'EOF'
          ${local.get_auth_indented}
          EOF
          tee /usr/local/bin/update-server.sh << 'EOF'
          ${local.update_server_indented}
          EOF

  - action: aws:runShellScript
    name: StartDockerServices
    inputs:
      runCommand:
        - |
          chmod 744 /opt/docker/docker-startup.sh
          sh /opt/docker/docker-startup.sh
DOC

  # Additional validations
  has_required_files = alltrue([
    fileexists("${path.module}/../services/jupyter/dockerfile.jupyter"),
    fileexists("${path.module}/../services/jupyter/jupyter-start.sh"),
    fileexists("${path.module}/../services/jupyter/jupyter-reset.sh"),
    fileexists("${path.module}/../services/jupyter/jupyter_server_config.py"),
    fileexists("${path.module}/../services/jupyter-pixi/dockerfile.jupyter.pixi"),
    fileexists("${path.module}/../services/jupyter-pixi/jupyter-start-pixi.sh"),
    fileexists("${path.module}/../services/jupyter-pixi/jupyter-reset-pixi.sh"),
    fileexists("${path.module}/../services/jupyter-pixi/jupyter_server_config_pixi.py"),
    fileexists("${path.module}/../services/logrotator/dockerfile.logrotator"),
    fileexists("${path.module}/../services/commands/update-auth.sh"),
    fileexists("${path.module}/../services/commands/refresh-oauth-cookie.sh"),
    fileexists("${path.module}/../services/commands/check-status-internal.sh"),
    fileexists("${path.module}/../services/commands/get-status.sh"),
    fileexists("${path.module}/../services/commands/get-auth.sh"),
    fileexists("${path.module}/../services/commands/update-server.sh"),
  ])

  files_not_empty = alltrue([
    length(data.local_file.dockerfile_jupyter) > 0,
    length(data.local_file.jupyter_start) > 0,
    length(data.local_file.jupyter_reset) > 0,
    length(data.local_file.jupyter_server_config_uv) > 0,
    length(data.local_file.dockerfile_jupyter_pixi) > 0,
    length(data.local_file.jupyter_start_pixi) > 0,
    length(data.local_file.jupyter_reset_pixi) > 0,
    length(data.local_file.jupyter_server_config_pixi) > 0,
    length(data.local_file.dockerfile_logrotator) > 0,
    length(data.local_file.update_auth) > 0,
    length(data.local_file.refresh_oauth_cookie) > 0,
    length(data.local_file.check_status) > 0,
    length(data.local_file.get_status) > 0,
    length(data.local_file.get_auth) > 0,
    length(data.local_file.update_server) > 0,
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
      condition     = length(local.ssm_startup_content) < 64000 # leaving some buffer
      error_message = "SSM document content exceeds size limit of 64KB"
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

  depends_on = [
    module.secret,
    module.ec2_instance
  ]
}
