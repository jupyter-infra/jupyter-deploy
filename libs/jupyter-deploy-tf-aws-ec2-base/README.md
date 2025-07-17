# AWS EC2 instance running a Jupyter Server using a Traefik proxy
------
This terraform project creates an EC2 instance in the default VPC and route 53 records in a domain you own.
Within the EC2 instance, it runs a `jupyter` service, a `traefik` service for proxy and an `oauth` sidecar for authentication and authorization.

The instance is configured so that you can access it using [AWS SSM](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html).

This project:
- places the instance in the first subnet of the default VPC
- select the latest AL 2023 AMI for `x86_64` architecture
- sets up an IAM role to enable SSM access
- passes on the root volume of the AMI
- adds an EBS volume which will mount on the Jupyter Server container
- configures automatic rotation for all log files under /var/log/services/ with customizable settings
- creates an SSM instance-startup script, which references several files:
    - `cloudinit.sh.tftpl` for the basic setup of the instance
    - `docker-compose.yml.tftpl` for the docker services to run in the instance
    - `docker-startup.sh.tftpl` to run the docker-compose up cmd and post docker-start instructions
    - `traefik.yml.tftpl` traefik configuration file
    - `dockerfile.jupyter` for the Jupyter container
    - `jupyter-start.sh` the entrypoint script for the Jupyter container
    - `jupyter-reset.sh` the fallback script if the Jupyter container fails to start
    - `pyproject.jupyter.toml` for Python dependencies of the base environment where the Jupyter server runs
    - `jupyter_server_config.py` for Jupyter server configuration
    - `dockerfile.logrotator` for a sidecar container responsible to rotate logs
    - `logrotator-start.sh.tftpl` to configure logrotate
    - `check-status-internal.sh` as a utility script to verify that the services are up and the TLS certificates are available
    - `get-status.sh` the utility script to translate the return code of `check-status` script to a human-readable status
    - `update-auth.sh` the utility script to update the authorized org, teams, and/or users
    - `get-auth.sh` the utility script to retrieve the authorized org, teams, and/or users
- creates an SSM association, which runs the startup script on the instance
- creates the Route 53 Hosted Zone for the domain unless it already exists
- adds DNS records to the Route 53 Hosted Zone
- creates an AWS Secret to store the OAuth App client secret
- provides two presets default values for the template variables:
    - `defaults-all.tfvars` comprehensive preset with all the recommended values
    - `defaults-base.tfvars` more limited preset; it will prompt user to select the instance type and volume size

## Prerequisites
- a domain that you own verifiable by route 53
    - [instructions](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/welcome-domain-registration.html) to register a domain
    - [instructions](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/domain-register.html#domain-register-procedure-section) to acquire a domain
- a GitHub OAuth App
    - [instructions](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app) to create a new app
    - you'll need the app client ID and client secret
- at least one of the following for GitHub authorization:
    - a list of GitHub usernames to authorize
    - the name of a GitHub organization to authorize the members of 

## Usage
This terraform project is meant to be used with `jupyter-deploy`.

### Installation (with pip):
Create or activate a python environment.

```bash
pip install jupyter-deploy
pip install jupyter-deploy-tf-aws-ec2-base
```

### Project setup
Consider making `my-jupyter-deployment` a git repository.
```bash
mkdir my-jupyter-deployment
cd my-jupyter-deployment

jd init . -E terraform -P aws -I ec2 -T base
```

### Configure and create the infrastructure
```bash
jd config
jd up
```

### Access your notebook
```bash

jd open
```

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
| [aws_default_vpc](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/default_vpc) | resource |
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
| region | `string` | `us-west-2` | The AWS region where the resources should be created |
| instance_type | `string` | `t3.medium` | The type of instance to start |
| key_pair_name | `string` | `null` | The name of key pair |
| ami_id | `string` | `null` | The ID of the AMI to use for the instance |
| volume_size_gb | `number` | `30` | The size in GB of the EBS volume the Jupyter Server has access to |
| volume_type | `string` | `gp3` | The type of EBS volume the Jupyter Server will has access to |
| iam_role_prefix | `string` | `Jupyter-deploy-ec2-base` | The prefix for the name of the IAM role for the instance |
| oauth_app_secret_prefix | `string` | `Jupyter-deploy-ec2-base` | The prefix for the name of the AWS secret where to store your OAuth app client secret |
| letsencrypt_email | `string` | Required | An email for letsencrypt to notify about certificate expirations |
| domain | `string` | Required | A domain that you own |
| subdomain | `string` | Required | A sub-domain of `domain` to add DNS records |
| oauth_provider | `string` | `github` | The OAuth provider to use |
| oauth_allowed_org | `string` | `""` | The GitHub organization to allowlist |
| oauth_allowed_teams | `list(string)` | `[]` | The list of GitHub teams to allowlist |
| oauth_allowed_usernames | `list(string)` | `[]` | The list of GitHub usernames to allowlist |
| oauth_app_client_id | `string` | Required | The client ID of the OAuth app |
| oauth_app_client_secret | `string` | Required | The client secret of the OAuth app |
| log_files_rotation_size_mb | `number` | `50` | The size in megabytes at which to rotate log files |
| log_files_retention_count | `number` | `10` | The maximum amount of rotated log files to retain for a log group |
| log_files_retention_days | `number` | `180` | The maximum number of log files to retain at any given time for a log group |
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
| `region` | The AWS region where the resources were created |
| `server_status_check_document` | Name of the SSM document to verify if the server is ready to serve traffic |
| `auth_check_document` | Name of the SSM document to view authorized users, teams and organization |
| `auth_users_update_document` | Name of the SSM document to change the authorized users |
| `auth_teams_update_document` | Name of the SSM document to change the authorized teams |
| `auth_org_set_document` | Name of the SSM document to allowlist an organization |
| `auth_org_unset_document` | Name of the SSM document to remove the allowlisted organization |
