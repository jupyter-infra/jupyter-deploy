# Extract root block device details from the AMI
data "aws_ami" "selected_ami" {
  filter {
    name   = "image-id"
    values = [var.ami_id]
  }
}

locals {
  # Extract AMI details for later use
  root_block_device = [
    for device in data.aws_ami.selected_ami.block_device_mappings :
    device if device.device_name == data.aws_ami.selected_ami.root_device_name
  ][0]
}

# EC2 instance
resource "aws_instance" "ec2_jupyter_server" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [var.security_group_id]
  key_name               = var.key_pair_name
  iam_instance_profile   = var.instance_profile_name

  tags = merge(
    var.combined_tags,
    {
      Name = "jupyter-server-${var.postfix}"
    }
  )

  # Root volume configuration
  root_block_device {
    volume_size = var.min_root_volume_size_gb != null ? max(var.min_root_volume_size_gb, try(local.root_block_device.ebs.volume_size, 1)) : local.root_block_device.ebs.volume_size
    volume_type = try(local.root_block_device.ebs.volume_type, "gp3")
    encrypted   = try(local.root_block_device.ebs.encrypted, true)
    tags = merge(
      var.combined_tags,
      {
        Name = "jupyter-root-${var.postfix}"
      }
    )
  }
}

# Associate the Elastic IP with the EC2 instance
resource "aws_eip_association" "jupyter_eip_assoc" {
  instance_id   = aws_instance.ec2_jupyter_server.id
  allocation_id = var.eip_allocation_id
}