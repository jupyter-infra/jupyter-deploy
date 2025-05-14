# Output the instance ID
output "instance_id" {
  value = aws_instance.ec2_jupyter_server.id
}

# Output the AMI ID
output "ami_id" {
  value = aws_instance.ec2_jupyter_server.ami
}

# Output the ARN of the AWS Secret where the ngrok token is stored
output "secret_arn" {
  value = aws_secretsmanager_secret.ngrok_secret.arn
}