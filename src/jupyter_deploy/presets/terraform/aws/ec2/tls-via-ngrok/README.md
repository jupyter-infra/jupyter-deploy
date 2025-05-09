# AWS EC2 instance running a Jupyter Server using ngrok for TLS
------
This terraform project creates an EC2 instance in the default VPC that connects to ngrok for TLS.

The instance is configured so that you can access it using [AWS SSM](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html).

This project:
- places the instance in the first subnet of the default VPC
- select the latest AL 2023 AMI for `x86_64` architecture
- sets up an IAM role to enable SSM access
- passes on the root volume of the AMI
- adds an EBS volume which will mount on the Jupyter Server container
- creates an SSM instance-startup script, which references 3 files:
    - `cloudinit.sh` for the basic setup of the instance
    - `docker-compose.yml` for the docker services to run in the instance
    - `docker-startup.sh` to run the docker-compose up cmd and post docker-start instructions
- creates an SSM association, which runs the startup script on the instance

## Usage
This terraform project is meant to be used with `jupyter-deploy`.

## Requirements
| Name | Version |
|---|---|
| terraform | >= 1.0 |
| aws | >= 4.66 |

## Providers
| Name | Version |
|---|---|
| aws | >= 4.66 |

## Modules
No modules.

## Resources
| Name | Type |
|---|---|
| [aws_security_group](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group) | resource |
| [aws_instance](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance) | resource |
| [aws_iam_role](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role_policy_attachment](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource | 
| [aws_iam_instance_profile](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_instance_profile) | resource |
| [aws_ebs_volume.jupyter_data](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ebs_volume) | resource |
| [aws_volume_attachment](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/volume_attachment) | resource |
| [aws_ssm_document](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ssm_document) | resource |
| [aws_ssm_association](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ssm_association) | resource |

## Inputs
| Name | Type | Default | Description |
|---|---|---|---|
| aws_region | `string` | `null` | AWS region where the resources should be created |
| instance_type | `string` | `t3.micro` | The type of instance to start |
| key_name | `string` | `null` | The name of key pair |
| ami_id | `string` | `null` | The ID of the AMI to use for the instance |
| jupyter_data_volume_size | `number` | `30` | The size in GB of the EBS volume the Jupyter Server has access to |
| jupyter_data_volume_type | `string` | `gp3` | The type of EBS volume the Jupyter Server will has access to |
| iam_role_prefix | `string` | `JD-TlsViaNgrok-Exec` | The prefix for the name of the IAM role for the instance |
| custom_tags | `map(string)` | `{}` | The custom tags to add to all the resources |
| cloudinit.sh | file | - | bash script to install packages, mount volumes and setup permissions |
| docker-compose.yml | file | docker compose file to start the docker services |
| docker-startup.sh | file | bash script to run docker-compose and post docker-start instructions |

## Outputs
| Name | Description |
|---|---|
| [aws_instance.id](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance#id-2) | The ID of the EC2 instance |
