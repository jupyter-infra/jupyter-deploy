# Define EBS volume for the notebook data (will mount on /home/jovyan)
resource "aws_ebs_volume" "jupyter_data" {
  availability_zone = var.availability_zone
  size              = var.volume_size_gb
  type              = var.volume_type
  encrypted         = true

  tags = merge(
    var.combined_tags,
    {
      Name = "jupyter-data-${var.postfix}"
    }
  )
}

# Attach the main jupyter data volume to the EC2 instance
resource "aws_volume_attachment" "jupyter_data_attachment" {
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.jupyter_data.id
  instance_id = var.instance_id
}

# STEP 1: EBS creation or reference
# Create additional EBS volumes when 'name' is specified
resource "aws_ebs_volume" "additional_volumes" {
  for_each = {
    for idx, ebs_mount in var.additional_ebs_mounts :
    idx => ebs_mount if lookup(ebs_mount, "name", null) != null
  }

  availability_zone = var.availability_zone
  size              = try(tonumber(lookup(each.value, "size_gb", "30")), 30)
  type              = lookup(each.value, "type", "gp3")
  encrypted         = true

  tags = merge(
    var.combined_tags,
    {
      Name = "${lookup(each.value, "name", "")}-${var.postfix}"
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
    var.combined_tags,
    {
      Name = "${lookup(each.value, "name", "")}-${var.postfix}"
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

# Get default subnet for EFS mount target
data "aws_subnets" "default" {
  filter {
    name   = "availability-zone"
    values = [var.availability_zone]
  }
}

data "aws_subnet" "default" {
  id = data.aws_subnets.default.ids[0]
}

# STEP 3: Generate the volumes mappings
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

  # List of EBS volumes with persist=true
  persist_ebs_volumes = [
    for idx, ebs_mount in var.additional_ebs_mounts :
    "aws_ebs_volume.additional_volumes[\"${idx}\"]"
    if lookup(ebs_mount, "persist", "") == "true"
  ]

  # List of EFS file systems with persist=true
  persist_efs_file_systems = [
    for idx, efs_mount in var.additional_efs_mounts :
    "aws_efs_file_system.additional_file_systems[\"${idx}\"]"
    if lookup(efs_mount, "persist", "") == "true"
  ]

  # Removed cloudinit_volumes_script - moved to main.tf
}

# STEP 4: Associate EBS and EFS to the EC2 instance
# first for additional EBS volumes
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
  instance_id = var.instance_id
}

# Use the security group provided by the network module

# Create mount targets for EFS file systems
resource "aws_efs_mount_target" "additional_efs_targets" {
  for_each = {
    for idx, efs_mount in local.resolved_efs_mounts :
    idx => {
      file_system_id = efs_mount["file_system_id"]
      mount_point    = efs_mount["mount_point"]
    }
  }
  file_system_id  = each.value.file_system_id
  subnet_id       = data.aws_subnet.default.id
  security_groups = length(var.additional_efs_mounts) > 0 && var.efs_security_group_id != null ? [var.efs_security_group_id] : []
}