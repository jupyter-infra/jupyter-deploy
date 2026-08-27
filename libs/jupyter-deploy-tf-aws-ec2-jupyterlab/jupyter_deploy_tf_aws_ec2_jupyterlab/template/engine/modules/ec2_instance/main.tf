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

  # Calculate root volume size
  # Strategy:
  # 1. Start with AMI's default size (e.g., 8GB for AL2023, 75GB for Deep Learning AMI)
  # 2. Add buffer: max(33% of AMI size, AMI size + 10GB) - ensures at least 10GB headroom
  # 3. Ensure we meet the minimum requirement (if specified)
  # Result: Volume sizes scale naturally with AMI needs while maintaining adequate headroom
  ami_root_size_gb      = try(local.root_block_device.ebs.volume_size, 5)
  root_size_with_buffer = max(ceil(local.ami_root_size_gb * 1.33), local.ami_root_size_gb + 10)
  root_volume_size_gb   = var.min_root_volume_size_gb != null ? max(var.min_root_volume_size_gb, local.root_size_with_buffer) : local.root_size_with_buffer
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
    volume_size = local.root_volume_size_gb
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