# Terraform provider configuration
terraform {
  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

provider "github" {}

data "aws_region" "current" {}
data "aws_partition" "current" {}

# Fetch the default VPC
data "aws_vpc" "default" {
  default = true
}

# Fetch availability zones
data "aws_availability_zones" "available_zones" {
  state = "available"
}

locals {
  default_tags = {
    Source = "jupyter-deploy"
    Template = "aws-ec2-traefik"
    Version = "1.0.0"
  }

  combined_tags = merge(
    local.default_tags,
    var.custom_tags,
  )
}

# Retrieve the first subnet in the default VPC
data "aws_subnets" "default_vpc_subnets" {
  filter {
    name = "vpc-id"
    values = [data.aws_vpc.default.id] 
  }
}

data "aws_subnet" "first_subnet_of_default_vpc" {
  id = tolist(data.aws_subnets.default_vpc_subnets.ids)[0]
}

# Define security group for EC2 instance
resource "aws_security_group" "ec2_jupyter_server_sg" {
  name        = "jupyter-deploy-traefik-sg"
  description = "Security group for the EC2 instance serving the JupyterServer"
  vpc_id      = data.aws_vpc.default.id

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.combined_tags
}

# Define the AMI
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners = ["amazon"]

  filter {
    name = "owner-alias"
    values = ["amazon"]
  }

  filter {
    name = "name"
    values = ["al2023-ami-*"]
  }

  filter {
    name = "architecture"
    values = ["x86_64"]  # Specify architecture (optional)
  }

  filter {
    name = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  root_block_device = [
    for device in data.aws_ami.amazon_linux_2023.block_device_mappings :
    device if device.device_name == data.aws_ami.amazon_linux_2023.root_device_name
  ][0]
}


# Define EC2 instance
resource "aws_instance" "ec2_jupyter_server" {
  ami                    = coalesce(var.ami_id, data.aws_ami.amazon_linux_2023.id)
  instance_type          = var.instance_type
  subnet_id              = data.aws_subnet.first_subnet_of_default_vpc.id
  vpc_security_group_ids = [aws_security_group.ec2_jupyter_server_sg.id]
  key_name               = var.key_name
  tags                   = local.combined_tags
  
  # Root volume configuration
  root_block_device {
    volume_size = local.root_block_device.ebs.volume_size
    volume_type = try(local.root_block_device.ebs.volume_type, "gp3")
    encrypted   = try(local.root_block_device.ebs.encrypted, true)
  }

  # IAM instance profile configuration
  iam_instance_profile = aws_iam_instance_profile.server_instance_profile.name
}

# Define the IAM role
data "aws_iam_policy_document" "server_assume_role_policy" {
  statement {
    sid     = "EC2AssumeRole"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.${data.aws_partition.current.dns_suffix}"]
    }
  }
}

resource "aws_iam_role" "execution_role" {
  name_prefix = "${var.iam_role_name_prefix}-"
  description = "Execution role for the JupyterServer instance, with access to SSM"

  assume_role_policy = data.aws_iam_policy_document.server_assume_role_policy.json
  force_detach_policies = true
  tags = local.combined_tags
}

data "aws_iam_policy" "ssm_managed_policy" {
  arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "execution_role_ssm_policy_attachment" {
  role = aws_iam_role.execution_role.name
  policy_arn = data.aws_iam_policy.ssm_managed_policy.arn
}

data "aws_iam_policy_document" "route53_dns_delegation" {
  statement {
    sid   = "Route53DnsDelegation"
    actions = [
      "route53:ListHostedZones",     // Find the zone for your domain
      "route53:GetChange",           // Check record creation status
      "route53:ChangeResourceRecordSets" // Create/delete TXT records
    ]
    resources = [
      "*"
    ]
  }
}

resource "aws_iam_policy" "route53_dns_delegation" {
  name_prefix = "route53-dns-delegation-"
  tags = local.combined_tags
  policy = data.aws_iam_policy_document.route53_dns_delegation.json
}
resource "aws_iam_role_policy_attachment" "route53_dns_delegation" {
  role = aws_iam_role.execution_role.name
  policy_arn = aws_iam_policy.route53_dns_delegation.arn
}

# Define the instance profile
resource "aws_iam_instance_profile" "server_instance_profile" {
  role = aws_iam_role.execution_role.name
  name_prefix = "${var.iam_role_name_prefix}-"
  lifecycle {
    create_before_destroy = true
  }
  tags = local.combined_tags
}

# Define EBS volume
resource "aws_ebs_volume" "jupyter_data" {
  availability_zone = aws_instance.ec2_jupyter_server.availability_zone
  size              = var.jupyter_data_volume_size
  type              = var.jupyter_data_volume_type
  encrypted         = true

  tags = local.combined_tags
}

# Attach EBS volume to EC2 instance
resource "aws_volume_attachment" "jupyter_data_attachment" {
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.jupyter_data.id
  instance_id = aws_instance.ec2_jupyter_server.id
}

# AWS Secret for the GitHub oauth app client secret
resource "aws_secretsmanager_secret" "oauth_github_client_secret" {
  name_prefix = "${var.oauth_github_app_name}-"
  tags = local.combined_tags
}

data "aws_iam_policy_document" "oauth_github_client_secret" {
  statement {
    sid   = "SecretsManagerReadGitHubAppClientSecret"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]
    resources = [
      aws_secretsmanager_secret.oauth_github_client_secret.arn
    ]
  }
}

resource "aws_iam_policy" "oauth_github_client_secret" {
  name_prefix = "${var.oauth_github_app_name}-"
  tags = local.combined_tags
  policy = data.aws_iam_policy_document.oauth_github_client_secret.json
}
resource "aws_iam_role_policy_attachment" "oauth_github_client_secret" {
  role = aws_iam_role.execution_role.name
  policy_arn = aws_iam_policy.oauth_github_client_secret.arn
}

resource "aws_ssm_parameter" "oauth_github_secret_aws_secret_arn" {
  name    = "/jupyter-deploy/oauth-github-app-client-secret-arn"
  type    = "String"
  value   = aws_secretsmanager_secret.oauth_github_client_secret.arn
  tags    = local.combined_tags 
}

# Read the local files
data "local_file" "cloud_init" {
  filename = "${path.module}/cloudinit.sh"
}

data "local_file" "docker_startup" {
  filename = "${path.module}/docker-startup.sh"
}

data "local_file" "dockerfile_jupyter" {
  filename = "${path.module}/dockerfile.jupyter"
}

# variables consistency checks
locals {
  full_domain = "${subdomain_name}.${domain_name}"
  github_usernames_valid = var.oauth_provider != "github" || length(var.oauth_github_allowed_usernames) > 0
}

locals {
  docker_compose_file = templatefile("${path.module}/docker-compose.yml.tftpl", {
    full_domain               = local.full_domain
    allowed_github_usernames  = join(",", [for username in var.oauth_github_allowed_usernames : "'${username}'"])
  })
  traefik_config_file = templatefile("${path.module}/traefik.yml.tftpl", {
    letsencrypt_notification_email  = var.letsencrypt_notification_email
  })
}

# SSM into the instance and execute the start-up scripts
locals {
  # In order to inject the file content with the correct 
  indent_count = 10
  indent_str = join("", [for i in range(local.indent_count) : " "])
  cloud_init_indented = join("\n${local.indent_str}", compact(split("\n", data.local_file.cloud_init.content)))
  docker_compose_indented = join("\n${local.indent_str}", compact(split("\n", local.docker_compose_file)))
  dockerfile_jupyter_indented = join("\n${local.indent_str}", compact(split("\n", data.local_file.dockerfile_jupyter.content)))
  docker_startup_indented = join("\n${local.indent_str}", compact(split("\n", data.local_file.docker_startup.content)))
  traefik_config_indented = join("\n${local.indent_str}", compact(split("\n", local.traefik_config_file)))
}

locals {
  ssm_startup_content=<<DOC
schemaVersion: '2.2'
description: Setup docker, mount volume, copy docker-compose, start docker services
mainSteps:
  - action: aws:runShellScript
    name: CloudInit
    inputs:
      runCommand:
        - |
          ${local.cloud_init_indented}

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
    fileexists("${path.module}/cloudinit.sh"),
    fileexists("${path.module}/docker-startup.sh"),
    fileexists("${path.module}/dockerfile.jupyter"),
  ])
  
  files_not_empty = alltrue([
    length(data.local_file.cloud_init.content) > 0,
    length(data.local_file.docker_startup.content) > 0,
    length(data.local_file.dockerfile_jupyter) > 0,
  ])

  docker_compose_valid = can(yamldecode(local.docker_compose_file))
  ssm_content_valid = can(yamldecode(local.ssm_startup_content))
  traefik_config_valid = can(yamldecode(local.traefik_config_file))
}

resource "aws_ssm_document" "instance_startup_instructions" {
  name            = "instance-startup-instructions"
  document_type   = "Command"
  document_format = "YAML"

  content = local.ssm_startup_content
  tags = local.combined_tags
  lifecycle {
    precondition {
      condition     = local.github_usernames_valid
      error_message = "If you use github as oauth provider, provide at least 1 github username"
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
      condition     = length(local.ssm_startup_content) < 64000  # leaving some buffer
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

# Seed the AWS Secret with the OAuth GitHub client secret
resource "null_resource" "store_oauth_github_client_secret" {
  triggers = {
    secret_arn = aws_secretsmanager_secret.oauth_github_client_secret.arn
  }
  provisioner "local-exec" {
    command = <<EOT
      CLIENT_SECRET="${var.oauth_github_app_secret_id}"
      aws secretsmanager put-secret-value \
        --secret-id ${aws_secretsmanager_secret.oauth_github_client_secret.arn} \
        --secret-string "$CLIENT_SECRET" \
        --region ${data.aws_region.current.name}
      EOT
  }

  depends_on = [
    aws_secretsmanager_secret.oauth_github_client_secret
  ]
}

resource "aws_ssm_association" "instance_startup_with_secret" {
  name = aws_ssm_document.instance_startup_instructions.name
  targets {
    key    = "InstanceIds"
    values = [aws_instance.ec2_jupyter_server.id]
  }
  automation_target_parameter_name = "InstanceIds"
  max_concurrency = "1"
  max_errors      = "0"
  wait_for_success_timeout_seconds = 300
  tags = local.combined_tags

  depends_on = [
    aws_ssm_parameter.oauth_github_secret_aws_secret_arn,
    null_resource.store_oauth_github_client_secret
  ]
}
