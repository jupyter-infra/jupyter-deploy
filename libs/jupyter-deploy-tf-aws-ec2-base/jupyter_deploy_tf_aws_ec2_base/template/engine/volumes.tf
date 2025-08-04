# Additional volume configurations
# This file manages optional EBS and EFS volumes that can be attached to the Jupyter instance

# STEP 1: EBS creation or reference
# Create additional EBS volumes when 'name' is specified
resource "aws_ebs_volume" "additional_volumes" {
  for_each = {
    for idx, ebs_mount in var.additional_ebs_mounts :
    idx => ebs_mount if lookup(ebs_mount, "name", null) != null
  }

  availability_zone = data.aws_subnet.first_subnet_of_default_vpc.availability_zone
  size              = try(tonumber(lookup(each.value, "size_gb", "30")), 30)
  type              = lookup(each.value, "type", "gp3")
  encrypted         = true

  tags = merge(
    local.combined_tags,
    {
      Name = "${lookup(each.value, "name", "")}-${local.doc_postfix}"
    }
  )
}

# Import the referenced EBS volumes when 'id' is specified
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


# STEP 2: EFS creation or reference
# Create EFS file systems when 'name' is specified
resource "aws_efs_file_system" "additional_file_systems" {
  for_each = {
    for idx, efs_mount in var.additional_efs_mounts :
    idx => efs_mount if lookup(efs_mount, "name", null) != null
  }

  encrypted = true
  tags = merge(
    local.combined_tags,
    {
      Name = "${lookup(each.value, "name", "")}-${local.doc_postfix}"
    }
  )
}

# Import the referenced EFS filesystems when 'id' is specified
data "aws_efs_file_system" "referenced_file_systems" {
  for_each = {
    for idx, efs_mount in var.additional_efs_mounts :
    idx => lookup(efs_mount, "id", "") if lookup(efs_mount, "id", null) != null
  }
  file_system_id = each.value
}


# STEP 3: Generate the volumes init script
locals {
  # combine created and referenced EBS volumes into a single map
  resolved_ebs_mounts = [
    for idx, ebs_mount in var.additional_ebs_mounts : {
      volume_id   = lookup(ebs_mount, "id", null) != null ? lookup(ebs_mount, "id", "") : aws_ebs_volume.additional_volumes[idx].id
      mount_point = ebs_mount["mount_point"]
      # Starts with /dev/sdg and increments
      # jupyter-data mounts on /dev/sdf, so we start one letter after
      device_name = "/dev/sd${substr("ghijklmnopqrstuvwxyz", idx, 1)}"
    }
  ]
  # combine created and referenced EFS file systems into a single map
  resolved_efs_mounts = [
    for idx, efs_mount in var.additional_efs_mounts : {
      file_system_id = lookup(efs_mount, "id", null) != null ? lookup(efs_mount, "id", "") : aws_efs_file_system.additional_file_systems[idx].id
      mount_point    = efs_mount["mount_point"]
    }
  ]

  # Do NOT depend on the attachments to avoid a circular dependency issue
  # instance -> attachment -> cloudinit-volume -> ssm-document -> instance
  cloudinit_volumes_script = templatefile("${path.module}/../services/cloudinit-volumes.sh.tftpl", {
    ebs_volumes = local.resolved_ebs_mounts
    efs_volumes = local.resolved_efs_mounts
    aws_region  = data.aws_region.current.region
  })
}


# STEP 4: Associate EBS and EFS to the EC2 instance
# first for EBS volumes
resource "aws_volume_attachment" "additional_ebs_attachments" {
  for_each = {
    for idx, ebs_mount in local.resolved_ebs_mounts :
    idx => {
      volume_id   = ebs_mount["volume_id"]
      device_name = ebs_mount["device_name"]
    }
  }
  device_name = each.value.device_name
  volume_id   = each.value.volume_id
  instance_id = aws_instance.ec2_jupyter_server.id
}

# second for EFS file systems
resource "aws_security_group" "efs_security_group" {
  count       = length(var.additional_efs_mounts) > 0 ? 1 : 0
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
resource "aws_efs_mount_target" "additional_efs_targets" {
  for_each = {
    for idx, efs_mount in local.resolved_efs_mounts :
    idx => {
      file_system_id = efs_mount["file_system_id"]
      mount_point    = efs_mount["mount_point"]
    }
  }
  file_system_id  = each.value.file_system_id
  subnet_id       = data.aws_subnet.first_subnet_of_default_vpc.id
  security_groups = [aws_security_group.efs_security_group[0].id]
}
