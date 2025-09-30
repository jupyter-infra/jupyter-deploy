output "id" {
  description = "ID of the EC2 instance."
  value       = aws_instance.ec2_jupyter_server.id
}

output "arn" {
  description = "ARN of the EC2 instance."
  value       = aws_instance.ec2_jupyter_server.arn
}

output "availability_zone" {
  description = "Availability zone of the EC2 instance."
  value       = aws_instance.ec2_jupyter_server.availability_zone
}

output "public_ip" {
  description = "Public IP address of the EC2 instance."
  value       = aws_instance.ec2_jupyter_server.public_ip
}

output "private_ip" {
  description = "Private IP address of the EC2 instance."
  value       = aws_instance.ec2_jupyter_server.private_ip
}

output "root_block_device_id" {
  description = "ID of the root block device."
  value       = aws_instance.ec2_jupyter_server.root_block_device[0].volume_id
}

output "ami" {
  description = "AMI ID used for the EC2 instance."
  value       = aws_instance.ec2_jupyter_server.ami
}

output "instance_type" {
  description = "Instance type of the EC2 instance."
  value       = aws_instance.ec2_jupyter_server.instance_type
}