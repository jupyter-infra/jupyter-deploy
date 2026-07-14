output "node_group_name" {
  value = aws_eks_node_group.this.node_group_name
}

output "ami_type" {
  value = var.ami_type
}

output "autoscaling_group_name" {
  description = "Name of the ASG EKS created for this managed node group (for Cluster Autoscaler discovery tags)."
  value       = aws_eks_node_group.this.resources[0].autoscaling_groups[0].name
}
