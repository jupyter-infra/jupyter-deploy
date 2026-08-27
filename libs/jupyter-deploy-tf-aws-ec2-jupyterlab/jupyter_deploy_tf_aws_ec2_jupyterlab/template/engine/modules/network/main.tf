# Retrieve or create the default VPC
# The default VPC should exist in every AWS account/region because AWS creates
# one automatically on account setup.
# However, a user may delete their default VPC, in which case we need to re-create it.
# Terraform preserves the default VPC on `terraform destroy`, which is the desired
# behavior since other jupyter-deploy may rely on it.
resource "aws_default_vpc" "default" {
  tags = {
    Name = "Default VPC"
  }
}

# Retrieve subnets in the default VPC
data "aws_subnets" "default_vpc_subnets" {
  filter {
    name   = "vpc-id"
    values = [aws_default_vpc.default.id]
  }
}

# Security group for the EC2 instance.
#
# Ingress opens :443 to all. The security boundary is the pinned self-signed TLS plus the
# STS-identity token that `jd proxy connect-info` mints — not the network layer.
resource "aws_security_group" "ec2_jupyter_server_sg" {
  name        = "jupyter-deploy-https-${var.postfix}"
  description = "Security group for the EC2 instance serving the jupyter server"
  vpc_id      = aws_default_vpc.default.id

  # Allow all outbound traffic (STS calls from the auth sidecar, image pulls, etc.)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    var.combined_tags,
    {
      Name = "jupyter-sg-${var.postfix}"
    }
  )
}

# HTTPS open to all; pinned TLS + the STS-identity token are the boundary.
resource "aws_vpc_security_group_ingress_rule" "https_open" {
  security_group_id = aws_security_group.ec2_jupyter_server_sg.id
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
  description       = "HTTPS open to all"
  tags = merge(
    var.combined_tags,
    {
      Name = "jupyter-https-open-${var.postfix}"
    }
  )
}

# Create security group for EFS mounts
resource "aws_security_group" "efs_security_group" {
  count       = var.has_efs_filesystems ? 1 : 0
  name        = "jupyter-deploy-efs-${var.postfix}"
  description = "Security group for EFS mount targets"
  vpc_id      = aws_default_vpc.default.id

  # Allow NFS traffic from the EC2 instance
  ingress {
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2_jupyter_server_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    var.combined_tags,
    {
      Name = "jupyter-efs-sg-${var.postfix}"
    }
  )
}
