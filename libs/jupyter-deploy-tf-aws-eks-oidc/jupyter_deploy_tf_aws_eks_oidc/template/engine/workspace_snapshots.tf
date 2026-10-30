# Scheduled snapshots of workspace volumes (#450).
#
# The EBS CSI driver stamps EVERY volume it provisions with combined_tags (extraVolumeTags in
# eks_addons.tf), Prometheus's gp2 volume included, so DeploymentId alone cannot select the
# workspace volumes. The ebs-sc StorageClass therefore adds one more tag, which only the volumes
# it provisions carry, and the lifecycle policy targets that tag.
#
# Snapshots copy their volume's tags (DeploymentId and Source among them), which is what
# null_resource.reap_workspace_volume_snapshots matches on teardown.
locals {
  # Unconditional, so that toggling workspace_volume_snapshots_enabled never changes the
  # StorageClass parameters (immutable, see null_resource.sync_ebs_storage_class).
  workspace_volume_tags = {
    WorkspaceVolume = random_id.postfix.hex
  }
  # The chart renders additionalResourceTags as tagSpecification_<n> = "<key>=<value>".
  workspace_volume_tag_specs = join(" ", sort([for k, v in local.workspace_volume_tags : "${k}=${v}"]))
}

data "aws_iam_policy_document" "dlm_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["dlm.amazonaws.com"]
    }
  }
}

module "dlm_role" {
  count              = var.workspace_volume_snapshots_enabled ? 1 : 0
  source             = "./modules/iam_role"
  role_name          = "${local.resource_name_prefix}-dlm"
  assume_role_policy = data.aws_iam_policy_document.dlm_trust.json
  policy_arns        = ["arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole"]
  combined_tags      = local.combined_tags
}

resource "aws_dlm_lifecycle_policy" "workspace_volumes" {
  count              = var.workspace_volume_snapshots_enabled ? 1 : 0
  description        = "Workspace volume snapshots of jupyter-deploy deployment ${random_id.postfix.hex}"
  execution_role_arn = module.dlm_role[0].role_arn
  state              = "ENABLED"
  tags               = local.combined_tags

  policy_details {
    resource_types = ["VOLUME"]
    target_tags    = local.workspace_volume_tags

    schedule {
      name      = "every-${var.workspace_volume_snapshot_interval_hours}h"
      copy_tags = true

      create_rule {
        interval      = var.workspace_volume_snapshot_interval_hours
        interval_unit = "HOURS"
      }

      retain_rule {
        count = var.workspace_volume_snapshot_retain_count
      }
    }
  }

  # On destroy, the policy goes BEFORE the reaper runs, so it cannot take a snapshot
  # the reaper has already missed.
  depends_on = [null_resource.reap_workspace_volume_snapshots]
}

# Destroy-time: delete this deployment's workspace volume snapshots. DLM retains them past
# the volume's deletion, and nothing else would ever delete them.
#
# NOT count-gated on workspace_volume_snapshots_enabled: disabling the schedule would destroy
# this resource, and so delete every existing snapshot. NOT best-effort either, like
# reap_csi_volumes: a failed list or delete fails the destroy; an already-deleted snapshot
# counts as success, so re-running `jd down` converges.
resource "null_resource" "reap_workspace_volume_snapshots" {
  triggers = {
    deployment_id = random_id.postfix.hex
    region        = var.region
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      region="${self.triggers.region}"

      echo "Reaping workspace volume snapshots of deployment ${self.triggers.deployment_id}..."
      # A plain assignment: under set -e a failed describe-snapshots fails the destroy
      # instead of reading as "no snapshots".
      snapshots=$(aws ec2 describe-snapshots --region "$region" --owner-ids self \
        --filters "Name=tag:DeploymentId,Values=${self.triggers.deployment_id}" "Name=tag:Source,Values=jupyter-deploy" \
        --query 'Snapshots[].SnapshotId' --output text)
      for snap in $snapshots; do
        if out=$(aws ec2 delete-snapshot --region "$region" --snapshot-id "$snap" 2>&1); then
          echo "  Deleted snapshot: $snap"
        elif grep -q "InvalidSnapshot.NotFound" <<<"$out"; then
          echo "  Already deleted: $snap"
        else
          echo "ERROR: failed to delete snapshot $snap: $out" >&2
          exit 1
        fi
      done
      echo "  Workspace volume snapshot reaping complete."
    EOT
  }
}

# Apply-time: StorageClass parameters are immutable, so `helm upgrade` cannot add the tag above
# to the ebs-sc of a cluster deployed before it existed. Delete that StorageClass first, and the
# upgrade recreates it; existing volumes and their PVCs are unaffected, but volumes they provision
# before this tag existed carry none, and are not snapshotted.
#
# Deletes only a StorageClass whose tags differ from the wanted ones, so a re-run is harmless and
# a fresh deploy (no StorageClass yet) is a no-op.
resource "null_resource" "sync_ebs_storage_class" {
  triggers = {
    tag_specs = local.workspace_volume_tag_specs
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    quiet       = true
    command = templatefile("${path.module}/local-sync-ebs-storageclass.sh.tftpl", {
      cluster_name       = local.cluster_name
      region             = var.region
      storage_class_name = "ebs-sc"
      tag_specs          = local.workspace_volume_tag_specs
    })
  }

  depends_on = [null_resource.platform, aws_eks_access_policy_association.admin_role, aws_eks_access_policy_association.admin_user]
}
