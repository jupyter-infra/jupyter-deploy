# AWS Provider Configuration
provider "aws" {
  region = var.aws_region
}

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
    Template = "aws-ec2-tls-via-ngrok"
    Version = "1.0.0"
  }

  combined_tags = merge(
    local.default_tags,
    var.custom_tags,
  )
}

# Define a subnet in the default VPC
resource "aws_subnet" "ec2_jupyter_server_subset" {
  vpc_id            = data.aws_vpc.default.id
  cidr_block        = var.subnet_cidr
  availability_zone = data.aws_availability_zones.available_zones.names[0]
  tags = local.combined_tags
}

# Define security group for EC2 instance
resource "aws_security_group" "ec2_jupyter_server_sg" {
  name        = "jupyter-deploy-tls-via-ngrok-sg"
  description = "Security group for the EC2 instance serving the JupyterServer"
  vpc_id      = data.aws_vpc.default.id

  # Allow SSH access
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow HTTPS access
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

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
data "aws_ami" "amazon_linux_2" {
  most_recent = true
  owners = ["amazon"]

  filter {
    name = "owner-alias"
    values = ["amazon"]
  }

  filter {
    name = "name"
    values = ["amzn2-ami-hvm*"]
  }
}

# Define EC2 instance
resource "aws_instance" "ec2_jupyter_server" {
  ami                    = coalesce(var.ami_id, data.aws_ami.amazon_linux_2.id)
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.ec2_jupyter_server_subset.id
  vpc_security_group_ids = [aws_security_group.ec2_jupyter_server_sg.id]
  key_name               = var.key_name
  tags                   = local.combined_tags
  
  # Root volume configuration
  root_block_device {
    volume_size = 10
    volume_type = "gp2"
    encrypted   = true
  }
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
  name = var.iam_role_name
  description = "Execution role for the JupyterServer instance, with access to SSM"

  assume_role_policy = data.aws_iam_policy_document.assume_role_policy[0].json
  force_detach_policies = true
  tags = local.combined_tags
}

resource "aws_iam_role_policy_attachments_exclusive" "execution_role" {
  role_name = aws_iam_role.execution_role.name
  policy_arns = [
    "arn:${data.aws_partition.current.id}:iam::aws:policy/AmazonSSMManagedInstanceCore"
  ]
}

# Define the instance profile
resource "aws_iam_instance_profile" "server_instance_profile" {
  role = aws_iam_role.execution_role.name
  name = var.iam_role_name
  lifecycle {
    create_before_destroy = true
  }
  tags = local.combined_tags
}

# Define EBS volume
resource "aws_ebs_volume" "jupyter_data" {
  availability_zone = aws_instance.jupyter_server.availability_zone
  size              = 10
  type              = "gp2"
  encrypted         = true

  tags = local.combined_tags
}

# Attach EBS volume to EC2 instance
resource "aws_volume_attachment" "jupyter_data_attachment" {
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.jupyter_data.id
  instance_id = aws_instance.ec2_jupyter_server.id
}
