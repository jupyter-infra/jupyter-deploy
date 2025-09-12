output "ami_id" {
  description = "The ID of the selected AMI based on instance type"
  value       = local.ami_id
}

output "instance_category" {
  description = "The category of the instance (cpu, gpu, neuron)"
  value       = local.instance_category
}

output "has_gpu" {
  description = "Whether the instance type has GPU capabilities"
  value       = local.has_gpu
}

output "gpu_count" {
  description = "Number of GPUs available on the instance type"
  value       = try(sum([for gpu in data.aws_ec2_instance_type.capabilities.gpus : try(gpu.count, 0)]), 0)
}

output "has_neuron" {
  description = "Whether the instance type has Neuron capabilities"
  value       = local.has_neuron
}

output "neuron_device_count" {
  description = "Number of Inference Accelerator devices available on the instance type"
  value       = try(length(data.aws_ec2_instance_type.capabilities.inference_accelerators), 0)
}

output "cpu_architecture" {
  description = "The CPU architecture of the instance (x86_64 or arm64)"
  value       = local.architecture
}

output "ami_lookup_key" {
  description = "The lookup key used to select the AMI (combination of instance category and architecture)"
  value       = local.ami_lookup_key
}
