output "node_group_name" {
  value = aws_eks_node_group.this.node_group_name
}

output "ami_type" {
  value = var.ami_type
}
