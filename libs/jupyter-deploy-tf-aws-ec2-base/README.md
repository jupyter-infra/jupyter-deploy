# AWS EC2 instance running a Jupyter Server using a Traefik proxy
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
- creates an SSM instance-startup script, which references several files:
    - `cloudinit.sh` for the basic setup of the instance
    - `docker-compose.yml.tftpl` for the docker services to run in the instance
    - `docker-startup.sh` to run the docker-compose up cmd and post docker-start instructions
    - `traefik.yml.tftpl` to configure traefik
    - `dockerfile.jupyter` for the Jupyter container
    - `start-jupyter.sh` to start the Jupyter server
    - `pyproject.jupyter.toml` for Python dependencies
    - `jupyter_server_config.py` for Jupyter server configuration
- creates an SSM association, which runs the startup script on the instance
- creates the Route 53 Hosted Zone for the domain unless it already exists
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
| github | ~> 6.0 |

## Providers
| Name | Version |
|---|---|
| aws | >= 4.66 |
| github | ~> 6.0 |

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
| [aws_ebs_volume](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ebs_volume) | resource |
| [aws_volume_attachment](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/volume_attachment) | resource |
| [aws_ssm_document](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ssm_document) | resource |
| [aws_ssm_association](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ssm_association) | resource |
| [aws_route53_zone](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route53_zone) | resource |
| [aws_route53_record](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route53_record) | resource |
| [aws_secretsmanager_secret](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/secretsmanager_secret) | resource |
| [aws_iam_policy](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_policy) | resource |
| [aws_ssm_parameter](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ssm_parameter) | resource |
| [null_resource](https://registry.terraform.io/providers/hashicorp/null/latest/docs/resources/resource) | resource |
| [aws_vpc](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/vpc) | data source |
| [aws_subnets](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/subnets) | data source |
| [aws_subnet](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/subnet) | data source |
| [aws_ami](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ami) | data source |
| [aws_route53_zone](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/route53_zone) | data source |
| [aws_iam_policy](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy) | data source |
| [aws_iam_policy_document](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [local_file](https://registry.terraform.io/providers/hashicorp/local/latest/docs/data-sources/file) | data source |

## Inputs
| Name | Type | Default | Description |
|---|---|---|---|
| region | `string` | `us-west-2` | AWS region where the resources should be created |
| instance_type | `string` | `t3.medium` | The type of instance to start |
| key_pair_name | `string` | `null` | The name of key pair |
| ami_id | `string` | `null` | The ID of the AMI to use for the instance |
| volume_size_gb | `number` | `30` | The size in GB of the EBS volume the Jupyter Server has access to |
| volume_type | `string` | `gp3` | The type of EBS volume the Jupyter Server will has access to |
| iam_role_prefix | `string` | `Jupyter-deploy-ec2-base` | The prefix for the name of the IAM role for the instance |
| oauth_app_secret_prefix | `string` | `Jupyter-deploy-ec2-base` | The prefix for the name of the AWS secret where to store your OAuth app client secret |
| letsencrypt_email | `string` | Required | An email for letsencrypt to notify about certificate expirations |
| domain | `string` | Required | A domain that you own |
| subdomain | `string` | `notebook1.notebooks` | A sub-domain of `domain` to add DNS records |
| oauth_provider | `string` | `github` | The OAuth provider to use |
| oauth_allowed_emails | `list(string)` | Required | The list of GitHub emails to allowlist |
| oauth_app_client_id | `string` | Required | The client ID of the OAuth app |
| oauth_app_client_secret | `string` | Required | The client secret of the OAuth app |
| custom_tags | `map(string)` | `{}` | The custom tags to add to all the resources |

## Outputs
| Name | Description |
|---|---|
| `jupyter_url` | The URL to access your notebook app |
| `auth_url` | The URL for the OAuth callback - do not use directly |
| `instance_id` | The ID of the EC2 instance |
| `ami_id` | The Amazon Machine Image ID used by the EC2 instance |
| `jupyter_server_public_ip` | The public IP assigned to the EC2 instance |
| `secret_arn` | The ARN of the AWS Secret storing the OAuth client secret |
