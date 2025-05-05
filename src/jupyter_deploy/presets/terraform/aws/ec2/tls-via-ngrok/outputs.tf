# Output the public IP of the EC2 instance
output "instance_public_ip" {
  value = aws_instance.ec2_jupyter_server.public_ip
}