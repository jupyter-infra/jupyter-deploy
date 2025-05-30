# AWS Provider Configuration
provider "aws" {
  region = var.aws_region
}

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

data "aws_iam_policy" "ssm_managed_policy" {
  arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

locals {
  default_tags = {
    Source   = "jupyter-deploy"
    Template = "aws-ec2-tls-via-ngrok"
    Version  = "1.0.0"
  }

  combined_tags = merge(
    local.default_tags,
    var.custom_tags,
  )
}

# Retrieve the first subnet in the default VPC
data "aws_subnets" "default_vpc_subnets" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_subnet" "first_subnet_of_default_vpc" {
  id = tolist(data.aws_subnets.default_vpc_subnets.ids)[0]
}

# Define security group for EC2 instance
resource "aws_security_group" "ec2_jupyter_server_sg" {
  name        = "jupyter-deploy-tls-via-ngrok-sg"
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
  owners      = ["amazon"]

  filter {
    name   = "owner-alias"
    values = ["amazon"]
  }

  filter {
    name   = "name"
    values = ["al2023-ami-*"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"] # Specify architecture (optional)
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name   = "virtualization-type"
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

  assume_role_policy    = data.aws_iam_policy_document.server_assume_role_policy.json
  force_detach_policies = true
  tags                  = local.combined_tags
}

resource "aws_iam_role_policy_attachment" "execution_role_ssm_policy_attachment" {
  role       = aws_iam_role.execution_role.name
  policy_arn = data.aws_iam_policy.ssm_managed_policy.arn
}

# Define the instance profile
resource "aws_iam_instance_profile" "server_instance_profile" {
  role        = aws_iam_role.execution_role.name
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

# AWS Secret for the ngrok token
resource "aws_secretsmanager_secret" "ngrok_secret" {
  name_prefix = "${var.ngrok_token_secret_prefix}-"
  tags        = local.combined_tags
}

data "aws_iam_policy_document" "ngrok_secret_reader_policy_document" {
  statement {
    sid = "SecretsManagerReadNgrokSecret"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]
    resources = [
      aws_secretsmanager_secret.ngrok_secret.arn
    ]
  }
}
resource "aws_iam_policy" "ngrok_secret_reader_policy" {
  name_prefix = "ngrok-secret-reader-"
  tags        = local.combined_tags
  policy      = data.aws_iam_policy_document.ngrok_secret_reader_policy_document.json
}
resource "aws_iam_role_policy_attachment" "ngrok_secret_reader" {
  role       = aws_iam_role.execution_role.name
  policy_arn = aws_iam_policy.ngrok_secret_reader_policy.arn
}

resource "aws_ssm_parameter" "ngrok_secret_arn" {
  name  = "/jupyter-deploy/ngrok-secret-arn"
  type  = "String"
  value = aws_secretsmanager_secret.ngrok_secret.arn
  tags  = local.combined_tags
}

# Read the local files
data "local_file" "cloud_init" {
  filename = "${path.module}/cloudinit.sh"
}

data "local_file" "docker_startup" {
  filename = "${path.module}/docker-startup.sh"
}

data "local_file" "docker_compose" {
  filename = "${path.module}/docker-compose.yml"
}


data "local_file" "dockerfile_jupyter" {
  filename = "${path.module}/dockerfile.jupyter"
}

# variables consistency checks
locals {
  google_emails_valid      = var.oauth_provider != "google" || length(var.oauth_google_allowed_emails) > 0
  github_usernames_valid   = var.oauth_provider != "github" || length(var.oauth_github_allowed_usernames) > 0
  ngrok_authtoken_provided = length(var.ngrok_auth_token) > 0
}

locals {
  ngrok_config = templatefile("${path.module}/ngrok.yml.tftpl", {
    oauth_provider           = var.oauth_provider
    allowed_google_emails    = join(",", [for email in var.oauth_google_allowed_emails : "'${email}'"])
    allowed_github_usernames = join(",", [for username in var.oauth_github_allowed_usernames : "'${username}'"])
    domain_name              = var.ngrok_domain_name
  })
}

# SSM into the instance and execute the start-up scripts
locals {
  # In order to inject the file content with the correct 
  indent_count                = 10
  indent_str                  = join("", [for i in range(local.indent_count) : " "])
  cloud_init_indented         = join("\n${local.indent_str}", compact(split("\n", data.local_file.cloud_init.content)))
  docker_compose_indented     = join("\n${local.indent_str}", compact(split("\n", data.local_file.docker_compose.content)))
  dockerfile_jupyter_indented = join("\n${local.indent_str}", compact(split("\n", data.local_file.dockerfile_jupyter.content)))
  docker_startup_indented     = join("\n${local.indent_str}", compact(split("\n", data.local_file.docker_startup.content)))
  ngrok_config_indented       = join("\n${local.indent_str}", compact(split("\n", local.ngrok_config)))
}

locals {
  ssm_startup_content = <<DOC
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
          tee /opt/docker/ngrok.yml << 'EOF'
          ${local.ngrok_config_indented}
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
    fileexists("${path.module}/docker-compose.yml"),
    fileexists("${path.module}/docker-startup.sh"),
    fileexists("${path.module}/dockerfile.jupyter"),
  ])

  files_not_empty = alltrue([
    length(data.local_file.cloud_init.content) > 0,
    length(data.local_file.docker_compose.content) > 0,
    length(data.local_file.docker_startup.content) > 0,
    length(data.local_file.dockerfile_jupyter) > 0,
  ])

  docker_compose_valid = can(yamldecode(data.local_file.docker_compose.content))
  ssm_content_valid    = can(yamldecode(local.ssm_startup_content))
  ngrok_config_valid   = can(yamldecode(local.ngrok_config))
}

resource "aws_ssm_document" "instance_startup_instructions" {
  name            = "instance-startup-instructions"
  document_type   = "Command"
  document_format = "YAML"

  content = local.ssm_startup_content
  tags    = local.combined_tags
  lifecycle {
    precondition {
      condition     = local.google_emails_valid
      error_message = "If you use google as oauth provider, provide at least 1 gmail email"
    }
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
      condition     = local.ngrok_config_valid
      error_message = "ngrok.yml file is not a valid YAML"
    }
  }
}

resource "null_resource" "store_ngrok_secret" {
  count = local.ngrok_authtoken_provided ? 1 : 0
  triggers = {
    secret_arn = aws_secretsmanager_secret.ngrok_secret.arn
  }
  provisioner "local-exec" {
    command = <<EOT
      TOKEN="${var.ngrok_auth_token}"
      aws secretsmanager put-secret-value \
        --secret-id ${aws_secretsmanager_secret.ngrok_secret.arn} \
        --secret-string "$TOKEN" \
        --region ${data.aws_region.current.name}
      EOT
  }

  depends_on = [aws_secretsmanager_secret.ngrok_secret]
}

# When ngrok auth token is not provided,
# we need to seed the secret first
resource "aws_ssm_association" "instance_startup_with_secret" {
  count = local.ngrok_authtoken_provided ? 1 : 0

  name = aws_ssm_document.instance_startup_instructions.name
  targets {
    key    = "InstanceIds"
    values = [aws_instance.ec2_jupyter_server.id]
  }
  automation_target_parameter_name = "InstanceIds"
  max_concurrency                  = "1"
  max_errors                       = "0"
  wait_for_success_timeout_seconds = 300
  tags                             = local.combined_tags

  depends_on = [
    aws_ssm_parameter.ngrok_secret_arn,
    null_resource.store_ngrok_secret[0]
  ]
}

# When ngrok auth token is not provided,
# we assume the secret was already seeded elsewhere
resource "aws_ssm_association" "instance_startup_without_secret" {
  count = local.ngrok_authtoken_provided ? 0 : 1

  name = aws_ssm_document.instance_startup_instructions.name
  targets {
    key    = "InstanceIds"
    values = [aws_instance.ec2_jupyter_server.id]
  }
  automation_target_parameter_name = "InstanceIds"
  max_concurrency                  = "1"
  max_errors                       = "0"
  wait_for_success_timeout_seconds = 300
  tags                             = local.combined_tags

  depends_on = [aws_ssm_parameter.ngrok_secret_arn]
}
