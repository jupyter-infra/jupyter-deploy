# AWS EC2 instance running a Jupyter Server using ngrok for TLS
------
This terraform project creates an EC2 instance in the default VPC and route 53 records in a domain you own.
Within the EC2 instance, it runs a `jupyter` service, a `traefik` service for proxy and an `oauth` sidecar for OAuth.

The instance is configured so that you can access it using [AWS SSM](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html).

This project:
- places the instance in the first subnet of the default VPC
- select the latest AL 2023 AMI for `x86_64` architecture
- sets up an IAM role to enable SSM access
- passes on the root volume of the AMI
- adds an EBS volume which will mount on the Jupyter Server container
- creates an SSM instance-startup script, which references 4 files:
    - `cloudinit.sh` for the basic setup of the instance
    - `docker-compose.yml` for the docker services to run in the instance
    - `docker-startup.sh` to run the docker-compose up cmd and post docker-start instructions
    - `traefik.yml` to configure traefik
- creates an SSM association, which runs the startup script on the instance
- create the Route 53 Hosted Zone for the domain unless it already exists
- adds DNS records to the Route 53 Hosted Zone
- creates an AWS Secret to store the OAuth App client secret

## Prerequisites
- a domain that you own verifiable by route 53
- a GitHub OAuth App: you'll need the app client ID and client Secret
- a list of email addresses to allowlist via GitHub: the email MUST be publicly visible in the GitHub profile of the users 

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
| instance_type | `string` | `t3.medium` | The type of instance to start |
| key_name | `string` | `null` | The name of key pair |
| ami_id | `string` | `null` | The ID of the AMI to use for the instance |
| jupyter_data_volume_size | `number` | `30` | The size in GB of the EBS volume the Jupyter Server has access to |
| jupyter_data_volume_type | `string` | `gp3` | The type of EBS volume the Jupyter Server will has access to |
| iam_role_prefix | `string` | `Jupyter-ec2-traefik` | The prefix for the name of the IAM role for the instance |
| letsencrypt_notification_email | `string` | None | An email for letsencrypt to notify about certificate expirations |
| domain_name | `string` | None | A domain that you own |
| subdomain_name | `string` | `notebook1.notebooks` | A sub-domain of `domain_name` to add DNS records |
| oauth_provider | `github` | `github` | The OAuth provider to use |
| oauth_allowed_github_emails | `list(string)` | [] | The list of GitHub emails to allowlist |
| oauth_github_app_name | `string` | `jupyter-deploy-aws-traefik` | A name for your OAuth app to reference in the AWS secret |
| oauth_github_app_client_id | `string` | None | The client ID of the OAuth app |
| oauth_github_app_client_secret | `string` | None | The client secret of the OAuth app |
| custom_tags | `map(string)` | `{}` | The custom tags to add to all the resources |
| cloudinit.sh | file | - | bash script to install packages, mount volumes and setup permissions |
| docker-compose.yml | file | docker compose file to start the docker services |
| docker-startup.sh | file | bash script to run docker-compose and post docker-start instructions |
| traefik.yml | file | config file for traefik |

## Outputs
| Name | Description |
|---|---|
| `jupyter_url` | The URL to access your notebook app |
| `auth_url` | The URL for the OAuth callback - do not use directly |
| [instance_id](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance#id-2) | The ID of the EC2 instance |
| `ami_id` | The Amazon Machine Image ID used by the EC2 instance |
| [jupyter_server_public_ip](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance#public_ip-1) | The public IP assigned to the EC2 instance |
| [secret_arn](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/secretsmanager_secret#arn-1) | The ARN of the AWS Secret storing the OAuth client secret |
