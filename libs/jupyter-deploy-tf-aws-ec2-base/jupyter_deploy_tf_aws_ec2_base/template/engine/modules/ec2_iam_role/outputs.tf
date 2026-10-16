output "instance_profile_name" {
  description = "Name of the instance profile to assign to the EC2 instance."
  # Sourced from the time_sleep trigger (not the resource directly) so consumers wait for
  # the IAM propagation delay before using the name — see time_sleep in main.tf.
  value = time_sleep.instance_profile_propagation.triggers["instance_profile_name"]
}

output "execution_role_name" {
  description = "Name of the IAM role for the EC2 instance."
  value       = aws_iam_role.execution_role.name
}