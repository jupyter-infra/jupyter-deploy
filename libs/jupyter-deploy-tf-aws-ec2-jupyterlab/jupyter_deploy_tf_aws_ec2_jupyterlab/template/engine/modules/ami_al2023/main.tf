/**
 * AMI Selection Module for Amazon Linux 2023
 * 
 * This module selects the appropriate Amazon Linux 2023 AMI based on the EC2 instance type
 * using the AWS EC2 instance type data source:
 * 
 * CPU Architecture Detection:
 * - Detects architecture (x86_64 or arm64) using ProcessorInfo.SupportedArchitecture
 * - Gives precedence to x86_64 if an instance supports multiple architectures
 * 
 * Accelerator Detection:
 * - Detects GPU capabilities using the gpus attribute of the instance type
 * - Detects Neuron (AWS Inferentia/Trainium) capabilities using inference_accelerators attribute
 * 
 * AMI Selection Logic:
 * - CPU instances, x86_64: Standard Amazon Linux 2023 x86_64 AMI
 * - CPU instances, arm64: Standard Amazon Linux 2023 arm64 AMI
 * - GPU instances, x86_64: NVIDIA GPU DLAMI with Amazon Linux 2023
 * - GPU instances, arm64: ARM64 GPU DLAMI with Amazon Linux 2023
 * - Neuron instances, x86_64: Neuron DLAMI with AWS Inferentia/Trainium support
 * - Neuron instances, arm64: Falls back to standard ARM64 Amazon Linux 2023
 * 
 * SSM parameters used:
 * - x86_64 AL2023: /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64
 * - arm64 AL2023: /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64
 * - x86_64 GPU DLAMI: /aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-amazon-linux-2023/latest/ami-id
 * - arm64 GPU DLAMI: /aws/service/deeplearning/ami/arm64/base-oss-nvidia-driver-gpu-amazon-linux-2023/latest/ami-id
 * - Neuron DLAMI: /aws/service/neuron/dlami/base/amazon-linux-2023/latest/image_id (x86_64 only)
 */

# Data source to get instance type capabilities
data "aws_ec2_instance_type" "capabilities" {
  instance_type = var.instance_type
}

# Retrieve the latest standard AL 2023 AMI for both x86_64 and arm64
data "aws_ssm_parameter" "amazon_linux_2023_x86" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "aws_ssm_parameter" "amazon_linux_2023_arm" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

data "aws_ami" "amazon_linux_2023_x86" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "image-id"
    values = [data.aws_ssm_parameter.amazon_linux_2023_x86.value]
  }
}

data "aws_ami" "amazon_linux_2023_arm" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "image-id"
    values = [data.aws_ssm_parameter.amazon_linux_2023_arm.value]
  }
}

# Retrieve the latest GPU DLAMI with AL2023 - architecture specific
data "aws_ssm_parameter" "gpu_dlami_x86" {
  name = "/aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-amazon-linux-2023/latest/ami-id"
}

# AWS also offers GPU DLAMIs for ARM64/Graviton
data "aws_ssm_parameter" "gpu_dlami_arm" {
  name = "/aws/service/deeplearning/ami/arm64/base-oss-nvidia-driver-gpu-amazon-linux-2023/latest/ami-id"
}

data "aws_ami" "gpu_dlami_x86" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "image-id"
    values = [data.aws_ssm_parameter.gpu_dlami_x86.value]
  }
}

data "aws_ami" "gpu_dlami_arm" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "image-id"
    values = [data.aws_ssm_parameter.gpu_dlami_arm.value]
  }
}

# Retrieve the latest Neuron DLAMI with AL2023 (x86_64 architecture)
data "aws_ssm_parameter" "neuron_dlami" {
  name = "/aws/service/neuron/dlami/base/amazon-linux-2023/latest/image_id"
}

data "aws_ami" "neuron_dlami" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "image-id"
    values = [data.aws_ssm_parameter.neuron_dlami.value]
  }
}

locals {
  # Accelerator detection using the data source with safe error handling
  has_gpu    = try(length(data.aws_ec2_instance_type.capabilities.gpus) > 0, false)
  has_neuron = try(length(data.aws_ec2_instance_type.capabilities.neuron_devices) > 0, false)

  # For outputs compatibility
  has_gpu_datasource    = local.has_gpu
  has_neuron_datasource = local.has_neuron

  # Architecture detection using ProcessorInfo.SupportedArchitecture with safe error handling
  supported_architectures = try(data.aws_ec2_instance_type.capabilities.supported_architectures, ["x86_64"])

  # If x86_64 is supported, use it. Otherwise, use arm64 if supported.
  # This gives x86_64 precedence as requested
  architecture = contains(local.supported_architectures, "x86_64") ? "x86_64" : contains(local.supported_architectures, "arm64") ? "arm64" : "x86_64"

  # Determine instance type category based on accelerator
  instance_category = local.has_neuron ? "neuron" : (local.has_gpu ? "gpu" : "cpu")

  # Create AMI selection map based on instance category and architecture
  ami_selection_map = {
    # CPU instances
    "cpu_x86_64" = data.aws_ami.amazon_linux_2023_x86.id
    "cpu_arm64"  = data.aws_ami.amazon_linux_2023_arm.id

    # GPU instances
    "gpu_x86_64" = data.aws_ami.gpu_dlami_x86.id
    "gpu_arm64"  = data.aws_ami.gpu_dlami_arm.id

    # Neuron instances
    "neuron_x86_64" = data.aws_ami.neuron_dlami.id
    "neuron_arm64"  = data.aws_ami.neuron_dlami.id # Fallback for theoretical future ARM Neuron instances
  }

  # Create lookup key by combining category and architecture
  ami_lookup_key = "${local.instance_category}_${local.architecture}"

  arch_ami_fallback = local.architecture == "arm64" ? data.aws_ami.amazon_linux_2023_arm.id : data.aws_ami.amazon_linux_2023_x86.id

  # Select the appropriate AMI based on instance category and architecture
  ami_id = lookup(local.ami_selection_map, local.ami_lookup_key, local.arch_ami_fallback)
}
