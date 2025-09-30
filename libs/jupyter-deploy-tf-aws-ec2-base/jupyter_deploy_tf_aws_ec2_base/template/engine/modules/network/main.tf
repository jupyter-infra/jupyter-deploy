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

# Retrieve the first subnet in the default VPC
data "aws_subnets" "default_vpc_subnets" {
  filter {
    name   = "vpc-id"
    values = [aws_default_vpc.default.id]
  }
}

data "aws_subnet" "first_subnet_of_default_vpc" {
  id = tolist(data.aws_subnets.default_vpc_subnets.ids)[0]
}

# Create security group for the EC2 instance
resource "aws_security_group" "ec2_jupyter_server_sg" {
  name        = "jupyter-deploy-https-${var.postfix}"
  description = "Security group for the EC2 instance serving the jupyter server"
  vpc_id      = aws_default_vpc.default.id

  # Allow only HTTPS inbound traffic
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow HTTPS traffic"
  }

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.combined_tags
}

# Allocate an Elastic IP address
resource "aws_eip" "jupyter_eip" {
  domain = "vpc"
  tags = merge(
    var.combined_tags,
    {
      Name = "jupyter-eip-${var.postfix}"
    }
  )
}

# DNS handling
# Require that the hosted zone already exists
data "aws_route53_zone" "existing" {
  name         = var.domain
  private_zone = false
}

# Create DNS record for jupyter subdomain
resource "aws_route53_record" "jupyter" {
  zone_id = data.aws_route53_zone.existing.zone_id
  name    = "${var.subdomain}.${var.domain}"
  type    = "A"
  ttl     = 300
  records = [aws_eip.jupyter_eip.public_ip]
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

  tags = var.combined_tags
}