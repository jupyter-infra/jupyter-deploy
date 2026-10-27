# Placement. Resolving the zone by name (rather than taking whichever subnet happens to be first)
# is what lets a caller escape a zone where the requested instance type is unavailable.
#
# Both lookups are gated on `count` rather than iterated with `for_each`: on a first deploy the
# subnet ids come from a data source filtered on the not-yet-created default VPC, so they are
# unknown at plan time, and `for_each` rejects unknown values outright ("Invalid for_each
# argument"). `count` here depends only on a variable, so it stays plan-time known.
locals {
  # "any" -- a word, not an empty value -- is the sentinel for "no preference", because the CLI
  # cannot express emptiness: `jd config --availability-zone ""` stores '""' in variables.yaml and
  # renders it into tfvars as "\"\"", a two-character zone name. A caller needs something they can
  # actually type to undo a pin. null and "" are accepted too, for a hand-edited variables.yaml.
  normalized_availability_zone = var.availability_zone == null ? "any" : var.availability_zone
  has_zone_preference          = !contains(["any", ""], local.normalized_availability_zone)

  # Splat so an absent (count = 0) data source yields [] rather than an "Invalid index" error, and
  # try() so whichever side is empty simply falls through.
  selected_subnet_id = try(flatten(data.aws_subnets.in_requested_zone[*].ids)[0], var.subnet_ids[0])
}

data "aws_subnets" "in_requested_zone" {
  count = local.has_zone_preference ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }

  filter {
    name   = "availability-zone"
    values = [local.normalized_availability_zone]
  }

  lifecycle {
    postcondition {
      condition = length(self.ids) == 1
      error_message = format(
        "Expected exactly one subnet in availability zone %s, found %d. Pick a zone that has one, or set availability_zone to \"any\" to use the first subnet of the VPC.",
        local.normalized_availability_zone,
        length(self.ids),
      )
    }
  }
}


# The zone is always read back from the subnet actually selected, never taken from the variable:
# the variable may be empty, and everything downstream (EBS placement, the EFS mount-target lookup
# in modules/volumes) needs a real zone name. Reading it here also keeps it plan-time known
# whenever the subnet id is, which is what stops the volumes from churning on every plan.
data "aws_subnet" "selected" {
  id = local.selected_subnet_id
}

# Fail as early as possible when the chosen zone cannot serve the chosen instance type: at plan
# time when the zone was requested explicitly, at apply time otherwise (the zone is not yet known).
# Otherwise the failure comes out of the apply as `Unsupported` when the type is absent from the
# zone, or `InsufficientInstanceCapacity` when it is offered but unavailable -- which the provider
# retries for ~50 minutes while terraform prints only "Still creating...". This checks *offering*,
# not capacity: no AWS API reports capacity, so a zone can pass here and still refuse the launch.
data "aws_ec2_instance_type_offerings" "selected_zone" {
  location_type = "availability-zone"

  filter {
    name   = "instance-type"
    values = [var.instance_type]
  }

  filter {
    name   = "location"
    values = [data.aws_subnet.selected.availability_zone]
  }

  lifecycle {
    postcondition {
      condition = length(self.instance_types) > 0
      error_message = format(
        "Instance type %s is not offered in availability zone %s. Set the availability_zone variable to a zone that offers it, or choose a different instance_type.",
        var.instance_type,
        data.aws_subnet.selected.availability_zone,
      )
    }
  }
}

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
  subnet_id              = local.selected_subnet_id
  vpc_security_group_ids = [var.security_group_id]
  iam_instance_profile   = var.instance_profile_name

  # Request a public IPv4 explicitly rather than relying on the subnet's auto-assign attribute
  # (which security baselines commonly disable). The template needs this address both for the
  # instance to reach SSM/S3/STS and for the client proxy to dial it; there is no EIP.
  associate_public_ip_address = true

  # IMDSv2 only. Hop limit 2 (default 1) reaches the bedrock-sidecar (assumes the bedrock-app role)
  # one docker-bridge hop away; the jupyter network is firewalled off IMDS anyway.
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

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