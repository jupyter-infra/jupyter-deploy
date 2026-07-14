# ami_type MUST arrive already resolved to a concrete EKS AMI type — do NOT
# reintroduce a `data "aws_ec2_instance_type"` here. A data source declared inside
# a module inherits the module's `depends_on` (this module depends_on
# null_resource.core_node_addons), so the read is deferred to apply-time
# ("known after apply") whenever that dependency has a pending change. That makes
# ami_type unknown at plan time and FORCES a full node-group replacement on every
# re-apply, even when the AMI type is unchanged. Resolution therefore happens at
# the root, where there is no depends_on to defer the read (see main.tf).
resource "aws_eks_node_group" "this" {
  cluster_name    = var.cluster_name
  node_group_name = var.node_group_name
  node_role_arn   = var.node_role_arn
  subnet_ids      = var.subnet_ids
  ami_type        = var.ami_type

  instance_types = [var.instance_type]
  disk_size      = var.disk_size_gb

  labels = {
    "jupyter-deploy/role" = var.role_label
  }

  scaling_config {
    min_size     = var.min_size
    max_size     = var.max_size
    desired_size = var.desired_size
  }

  tags = var.combined_tags

  # Cluster Autoscaler moves desired_size within min/max (see platform_cluster_autoscaler.tf);
  # ignore it so a subsequent `jd up` doesn't fight CA by resetting the count to var.desired_size.
  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }
}
