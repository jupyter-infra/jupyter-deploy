# Additional volume configurations
# This file manages optional EBS and EFS volumes that can be attached to the Jupyter instance

# Create additional EBS volumes when name is specified
resource "aws_ebs_volume" "additional_volumes" {
  for_each = {
    for idx, ebs_mount in var.additional_ebs_mounts :
    idx => ebs_mount if lookup(ebs_mount, "name", null) != null
  }

  availability_zone = aws_instance.ec2_jupyter_server.availability_zone
  size              = try(tonumber(each.value["size_gb"]), 30)
  type              = lookup(each.value, "type", "gp3")
  encrypted         = true

  tags = merge(
    local.combined_tags,
    {
      Name = "${each.key}-${local.doc_postfix}"
    }
  )
}

# Import the referenced EBS volumes
data "aws_ebs_volume" "referenced_volumes" {
  for_each = {
    for idx, ebs_mount in var.additional_ebs_mounts :
    idx => lookup(ebs_mount, "id", "") if lookup(ebs_mount, "id", null) != null
  }

  filter {
    name   = "volume-id"
    values = [each.value]
  }
}

# Attach EBS volumes to the EC2 instance (both created and referenced)
resource "aws_volume_attachment" "additional_ebs_attachments" {
  for_each = {
    for idx, ebs_mount in var.additional_ebs_mounts :
    idx => {
      volume_id   = lookup(ebs_mount, "id", null) != null ? data.aws_ebs_volume.referenced_volumes[idx].id : aws_ebs_volume.additional_volumes[idx].id
      mount_point = ebs_mount["mount_point"]
      # Starts with /dev/sdg and increments
      # jupyter-data mounts on /dev/sdf, so we start one letter after
      device_name = "/dev/sd${substr("ghijklmnopqrstuvwxyz", idx, 1)}" 
    }
  }

  device_name = each.value.device_name
  volume_id   = each.value.volume_id
  instance_id = aws_instance.ec2_jupyter_server.id
}

# Create EFS file systems when name is specified
resource "aws_efs_file_system" "additional_file_systems" {
  for_each = {
    for idx, efs_mount in var.additional_efs_mounts :
    idx => efs_mount if lookup(efs_mount, "name", null) != null
  }

  encrypted = true
  tags = merge(
    local.combined_tags,
    {
      Name = "${each.key}-${local.doc_postfix}"
    }
  )
}

# Import the referenced EFS filesystems
data "aws_efs_file_system" "referenced_file_systems" {
  for_each = {
    for idx, efs_mount in var.additional_efs_mounts :
    idx => lookup(efs_mount, "id", "") if lookup(efs_mount, "id", null) != null
  }

  file_system_id = each.value
}

# Create EFS mount targets (both created and referenced) in the subnet where the EC2 instance is located
resource "aws_efs_mount_target" "additional_efs_targets" {
  for_each = {
    for idx, efs_mount in var.additional_efs_mounts :
    idx => {
      file_system_id = lookup(efs_mount, "id", null) != null ? data.aws_efs_file_system.referenced_file_systems[idx].id : aws_efs_file_system.additional_file_systems[idx].id
      mount_point    = efs_mount["mount_point"]
    }
  }
  file_system_id  = each.value.file_system_id
  subnet_id       = data.aws_subnet.first_subnet_of_default_vpc.id
  security_groups = [aws_security_group.efs_security_group.id]
}

# Security group for EFS mount targets
resource "aws_security_group" "efs_security_group" {
  name        = "jupyter-deploy-efs-${local.doc_postfix}"
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

  tags = local.combined_tags
}

locals {
  # Generate the volumes init script
  cloudinit_volumes_script = templatefile("${path.module}/../services/cloudinit_volumes.sh.tftpl", {
    ebs_volumes = [
      for idx, ebs_mount in var.additional_ebs_mounts : {
        mount_point = ebs_mount["mount_point"]
        device_name = "/dev/sd${substr("ghijklmnopqrstuvwxyz", idx, 1)}"
      }
    ]
    efs_volumes = [
      for idx, efs_mount in var.additional_efs_mounts : {
        mount_point    = efs_mount["mount_point"]
        file_system_id = lookup(efs_mount, "id", null) != null ? efs_mount["id"] : aws_efs_file_system.additional_file_systems[idx].id
      }
    ]
  })
}
