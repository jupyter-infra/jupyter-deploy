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

data "local_file" "pyproject_jupyter" {
  filename = "${path.module}/../services/jupyter/pyproject.jupyter.toml"
}

data "local_file" "pyproject_kernel_uv" {
  filename = "${path.module}/../services/jupyter/pyproject.kernel.toml"
}

data "local_file" "pyproject_kernel_pixi" {
  filename = "${path.module}/../services/jupyter-pixi/pyproject.kernel.toml"
}

# Command + startup scripts
data "local_file" "docker_startup" {
  filename = "${path.module}/../services/docker-startup.sh"
}

# Traefik static + dynamic (self-signed TLS) config
data "local_file" "traefik_yml" {
  filename = "${path.module}/../services/traefik/traefik.yml"
}

data "local_file" "traefik_dynamic_yml" {
  filename = "${path.module}/../services/traefik/traefik-dynamic.yml"
}

# Auth sidecar (ForwardAuth: verify STS-identity token, ARN allowlist, x-k8s-aws-id binding)
data "local_file" "auth_sidecar_dockerfile" {
  filename = "${path.module}/../services/auth-sidecar/Dockerfile"
}

data "local_file" "auth_sidecar_main_go" {
  filename = "${path.module}/../services/auth-sidecar/main.go"
}

data "local_file" "auth_sidecar_go_mod" {
  filename = "${path.module}/../services/auth-sidecar/go.mod"
}

locals {
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

  # Compute hash of all files that affect docker compose image builds (jupyter, auth-sidecar, log-rotator)
  build_affecting_files = [
    local.dockerfile_content,
    local.jupyter_toml_content,
    local.jupyter_start_content,
    local.jupyter_reset_content,
    local.jupyter_server_config_content,
    local.kernel_pyproject_content,
    data.local_file.dockerfile_logrotator.content,
    local.logrotator_start_file,
    data.local_file.auth_sidecar_dockerfile.content,
    data.local_file.auth_sidecar_main_go.content,
    data.local_file.auth_sidecar_go_mod.content,
  ]
  images_build_hash = sha256(join("\n", local.build_affecting_files))

  # cloud-init installs docker + tooling and mounts the data volume. The self-signed cert
  # is generated by generate-cert.sh (which publishes the public PEM to the cert-pin param).
  cloud_init_file = templatefile("${path.module}/../services/cloudinit.sh.tftpl", {})
  generate_cert_file = templatefile("${path.module}/../services/generate-cert.sh.tftpl", {
    cert_pin_ssm_parameter_name = aws_ssm_parameter.cert_pin.name
    aws_region                  = data.aws_region.current.id
  })
  docker_startup_file = data.local_file.docker_startup.content
  docker_compose_file = templatefile("${path.module}/../services/docker-compose.yml.tftpl", {
    aws_region     = data.aws_region.current.id
    deployment_id  = local.doc_postfix
    aws_account_id = data.aws_caller_identity.current.account_id
    role_allowlist = join(",", local.auth_role_names)
    user_allowlist = join(",", local.auth_user_names)
    ebs_mounts     = module.volumes.resolved_ebs_mounts
    efs_mounts     = module.volumes.resolved_efs_mounts
    has_gpu        = module.ami_al2023.has_gpu
    has_neuron     = module.ami_al2023.has_neuron
  })
  traefik_config_file         = data.local_file.traefik_yml.content
  traefik_dynamic_config_file = data.local_file.traefik_dynamic_yml.content
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
  deployment_scripts_filenames = ["check-status-internal.sh", "get-status.sh", "update-server.sh", "generate-cert.sh"]
  deployment_docker_filenames  = ["docker-compose.yml", "traefik.yml", "traefik-dynamic.yml", "dockerfile.jupyter", "jupyter-start.sh", "jupyter-reset.sh", "pyproject.kernel.toml", "jupyter_server_config.py", "dockerfile.logrotator", "logrotator-start.sh", "fluent-bit.conf", "parsers.conf", ".build-manifest"]
  # auth-sidecar sources live under a subdir so the compose build context is ./auth-sidecar
  deployment_sidecar_filenames = ["Dockerfile", "main.go", "go.mod"]

  all_script_files = {
    # Startup scripts (docker-startup only, cloudinit stays in SSM)
    "deployment-scripts/docker-startup.sh" = {
      content      = local.docker_startup_file
      content_type = "text/x-shellscript"
    }

    # Utility scripts from commands
    "deployment-scripts/check-status-internal.sh" = {
      content      = data.local_file.check_status.content
      content_type = "text/x-shellscript"
    }
    "deployment-scripts/get-status.sh" = {
      content      = data.local_file.get_status.content
      content_type = "text/x-shellscript"
    }
    "deployment-scripts/update-server.sh" = {
      content      = data.local_file.update_server.content
      content_type = "text/x-shellscript"
    }
    "deployment-scripts/generate-cert.sh" = {
      content      = local.generate_cert_file
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
    "deployment-docker/traefik-dynamic.yml" = {
      content      = local.traefik_dynamic_config_file
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
    "deployment-docker/.build-manifest" = {
      content      = local.images_build_hash
      content_type = "text/plain"
    }
    # Auth sidecar build context (compose builds ./auth-sidecar)
    "deployment-docker/auth-sidecar/Dockerfile" = {
      content      = data.local_file.auth_sidecar_dockerfile.content
      content_type = "text/plain"
    }
    "deployment-docker/auth-sidecar/main.go" = {
      content      = data.local_file.auth_sidecar_main_go.content
      content_type = "text/plain"
    }
    "deployment-docker/auth-sidecar/go.mod" = {
      content      = data.local_file.auth_sidecar_go_mod.content
      content_type = "text/plain"
    }
  }

  # Compute hash of all deployment script files
  # This hash triggers SSM association re-execution when scripts change
  scripts_files_hash = sha256(join("\n", [for k, v in local.all_script_files : v.content]))

  # Compute hash of SSM-embedded scripts (cloud-init + volume-init)
  ssm_embedded_hash = sha256(join("\n", [local.cloud_init_file, local.cloudinit_volumes_script]))
}

# Generate the cloudinit_volumes_script directly in services.tf
locals {
  cloudinit_volumes_script = templatefile("${path.module}/../services/cloudinit-volumes.sh.tftpl", {
    ebs_volumes = module.volumes.resolved_ebs_mounts
    efs_volumes = module.volumes.resolved_efs_mounts
    aws_region  = data.aws_region.current.id
  })
}

# SSM into the instance and execute the start-up scripts
locals {
  indent_count               = 10
  indent_str                 = join("", [for i in range(local.indent_count) : " "])
  cloud_init_indented        = join("\n${local.indent_str}", compact(split("\n", local.cloud_init_file)))
  cloudinit_volumes_indented = join("\n${local.indent_str}", compact(split("\n", local.cloudinit_volumes_script)))
}

locals {
  ssm_startup_content = <<DOC
schemaVersion: '2.2'
description: Setup docker, mount volumes, generate self-signed cert, copy docker-compose, start docker services
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
          mkdir -p /opt/docker/auth-sidecar

          for file in ${join(" ", local.deployment_docker_filenames)}; do
            aws s3 cp s3://$BUCKET/deployment-docker/$file /opt/docker/$file
          done

          for file in ${join(" ", local.deployment_sidecar_filenames)}; do
            aws s3 cp s3://$BUCKET/deployment-docker/auth-sidecar/$file /opt/docker/auth-sidecar/$file
          done

          aws s3 cp s3://$BUCKET/deployment-scripts/docker-startup.sh /opt/docker/docker-startup.sh
          chmod 755 /opt/docker/docker-startup.sh
          aws s3 cp s3://$BUCKET/deployment-docker/${local.jupyter_toml_filename} /opt/docker/${local.jupyter_toml_filename}

  - action: aws:runShellScript
    name: GenerateCertificates
    inputs:
      onFailure: exit
      runCommand:
        - |
          sh /usr/local/bin/generate-cert.sh

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
    fileexists("${path.module}/../services/commands/check-status-internal.sh"),
    fileexists("${path.module}/../services/commands/get-status.sh"),
    fileexists("${path.module}/../services/commands/update-server.sh"),
    fileexists("${path.module}/../services/docker-startup.sh"),
    fileexists("${path.module}/../services/generate-cert.sh.tftpl"),
    fileexists("${path.module}/../services/traefik/traefik.yml"),
    fileexists("${path.module}/../services/traefik/traefik-dynamic.yml"),
    fileexists("${path.module}/../services/auth-sidecar/Dockerfile"),
    fileexists("${path.module}/../services/auth-sidecar/main.go"),
    fileexists("${path.module}/../services/auth-sidecar/go.mod"),
  ])

  files_not_empty = alltrue([
    length(data.local_file.dockerfile_jupyter.content) > 0,
    length(data.local_file.jupyter_start.content) > 0,
    length(data.local_file.jupyter_reset.content) > 0,
    length(data.local_file.jupyter_server_config_uv.content) > 0,
    length(data.local_file.pyproject_jupyter.content) > 0,
    length(data.local_file.pyproject_kernel_uv.content) > 0,
    length(data.local_file.dockerfile_jupyter_pixi.content) > 0,
    length(data.local_file.jupyter_start_pixi.content) > 0,
    length(data.local_file.jupyter_reset_pixi.content) > 0,
    length(data.local_file.jupyter_server_config_pixi.content) > 0,
    length(data.local_file.pyproject_kernel_pixi.content) > 0,
    length(data.local_file.dockerfile_logrotator.content) > 0,
    length(data.local_file.check_status.content) > 0,
    length(data.local_file.get_status.content) > 0,
    length(data.local_file.update_server.content) > 0,
    length(data.local_file.docker_startup.content) > 0,
    length(local.generate_cert_file) > 0,
    length(data.local_file.traefik_yml.content) > 0,
    length(data.local_file.traefik_dynamic_yml.content) > 0,
    length(data.local_file.auth_sidecar_dockerfile.content) > 0,
    length(data.local_file.auth_sidecar_main_go.content) > 0,
    length(data.local_file.auth_sidecar_go_mod.content) > 0,
  ])

  docker_compose_valid = can(yamldecode(local.docker_compose_file))
  ssm_content_valid    = can(yamldecode(local.ssm_startup_content))
  traefik_config_valid = can(yamldecode(local.traefik_config_file)) && can(yamldecode(local.traefik_dynamic_config_file))
}

resource "aws_ssm_document" "instance_startup" {
  name            = "instance-startup-${local.doc_postfix}"
  document_type   = "Command"
  document_format = "YAML"

  content = local.ssm_startup_content
  tags    = local.combined_tags

  lifecycle {
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
      error_message = "traefik config files are not valid YAML"
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

resource "aws_ssm_association" "instance_startup" {
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
    module.ec2_instance,
    module.volumes,
    # The startup document runs `aws s3 cp` for the whole bundle (scripts, docker files,
    # auth-sidecar build context). Wait for every object to finish uploading before the
    # association fires, so the instance never races a not-yet-uploaded key.
    module.s3_bucket,
  ]
}
