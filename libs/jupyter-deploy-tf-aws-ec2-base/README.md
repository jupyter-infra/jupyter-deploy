# Jupyter Deploy AWS EC2 base template

The Jupyter Deploy AWS EC2 base template is an open-source project to run JupyterLab applications
on remote hosts served on your domain with encrypted HTTP (TLS), GitHub OAuth integration, real-time-collaboration, and fast UV-based environments.
It uses Terraform as the infrastructure-as-code engine, deploys the JupyterLab container to an Amazon EC2 instance, and controls access with GitHub identities. 
It places the EC2 instance in the default VPC of your AWS account and adds a DNS record to your domain with Amazon Route53. 

Within the EC2 instance, it leverages `docker-compose` to run a `jupyter` service, a `traefik` sidecar to control ingress and an `oauth2-proxy` middleware to handle oauth with `traefik` ForwardAuth [protocol](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/forwardauth/). The instance only allows ingress on port 443 (HTTPS), and relies on the `ssm-agent` for administrator operations. Refer to [AWS SSM](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html) for more details.

This base template is maintained and supported by AWS.

## Prerequisites
- a domain that you own verifiable by Amazon Route 53
    - [instructions](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/welcome-domain-registration.html) to register a domain
    - [instructions](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/domain-register.html#domain-register-procedure-section) to buy a domain
- a GitHub OAuth App
    - [register](https://github.com/settings/applications/new) a new application
    - choose any application name
    - set `Homepage URL` to: `https://<subdomain>.<domain>`
    - set `Authorization callback URL` to: `https://<subdomain>.<domain>/oauth2/callback`
    - [documentation](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app) to dive deeper
    - write down and save your app client ID and client secret
- select at least one of the following GitHub identities to authorize:
    - a GitHub username (or a list of usernames)
    - a GitHub organization whose members; optionally restrict further by GitHub teams

## Usage
This terraform project is meant to be used with the [jupyter-deploy](https://github.com/jupyter-infra/jupyter-deploy/tree/main/libs/jupyter-deploy) CLI.

### Installation (with pip):
Recommended: create or activate a python virtual environment.

```bash
pip install jupyter-deploy[aws]
pip install jupyter-deploy-tf-aws-ec2-base
```

### Project setup
```bash
mkdir my-jupyter-deployment
cd my-jupyter-deployment

jd init . -E terraform -P aws -I ec2 -T base
```

Consider making `my-jupyter-deployment` a git repository.

### Configure and create the infrastructure
```bash
jd config
jd up
```

### Access your JupyterLab application
```bash
# verify that your host and containers are running
jd host status
jd server status

# open your application on your web browser
jd open
```

### Manage access

```bash
# By GitHub users
jd users list
jd users add USERNAME1 USERNAME2
jd users remove USERNAME1

# By GitHub organization
jd organization get
jd organization set ORGANIZATION
jd organization unset

# Along with GitHub organization, by teams
jd teams list
jd teams add TEAM1 TEAM2
jd teams remove TEAM2
```

### Temporarily stop/start your EC2 instance
```bash
# To stop your instance
jd host stop
jd host status

# To start it again
jd host start
jd server start
jd server status
```

### Manage your EC2 instance
```bash
# connect to your host
jd host connect

# disconnect
exit
```

### Take down all the infrastructure
This operation removes all the resources associated with this project in your AWS account.

```bash
jd down
```

## Details
This project:
- places the instance in the first subnet of the default VPC
- selects the latest Amazon Linux 2023 AMI compatible with the selected instance type
    - standard AL2023 AMI for CPU instances (x86_64 or arm64)
    - DLAMI in the case of GPU or Neuron instances (x86_64 or arm64)
- sets up an IAM role to enable SSM, Route53 and (optionally) EFS access
- passes on the root volume settings of the AMI
- adds an EBS volume which will mount on the Jupyter Server container
- adds an Elastic IP (EIP) to keep the public IP of the instance stable
- writes Docker service logs to disk at `/var/log/services` using `fluent-bit`
- configures automatic rotation for all log files using `logrotate`
- creates an SSM instance-startup script, which references several files:
    - `cloudinit.sh.tftpl` to configure the EC2 instance
    - `docker-compose.yml.tftpl` to configure the Docker services
    - `docker-startup.sh.tftpl` to start the Docker services
    - `cloudinit-volumes.sh.tftpl` to optionally mount additional elastic block store (EBS) or elastic file systems (EFS)
    - `traefik.yml.tftpl` to configure traefik
    - `dockerfile.jupyter` to build the Jupyter container
    - `jupyter-start.sh` to provide entrypoint script for the Jupyter container
    - `jupyter-reset.sh` to provide a fallback if the Jupyter container fails to start
    - `pyproject.jupyter.toml` to configure the Python dependencies of the base environment where the Jupyter server runs
        - note: `pixi.jupyter.toml` if you select `pixi` as dependency manager
    - `jupyter_server_config.py` to configure Jupyter server
    - `dockerfile.logrotator` to configure the sidecar container rotating log files on disk
    - `logrotator-start.sh.tftpl` to configure logrotate
    - `fluent-bit.conf` to configure the fluent-bit service writing Docker service logs to `/var/log/services`
    - `parsers.conf` to configure the fluent-bit Docker parsers
    - `check-status-internal.sh` to verify that the services are up and the TLS certificates are available
    - `get-status.sh` to translate the return code of `check-status` script to a human-readable status
    - `update-auth.sh` to update the authorized org, teams, and/or users
    - `get-auth.sh` to retrieve the authorized org, teams, and/or users
    - `update-server.sh` to update the services running within the host
    - `refresh-oauth-cookie.sh` to rotate the oauth cookie secret and invalidate all issued cookies
- creates an SSM association, which runs the startup script on the instance
- creates the Route 53 Hosted Zone for the domain unless it already exists
- adds the DNS record to the Route 53 Hosted Zone
- creates an AWS Secret to store the OAuth App client secret
- optionally creates or references EBS volumes or EFS and mount them to the home directory of the jupyter app
- provides two presets default values for the template variables:
    - `defaults-all.tfvars` comprehensive preset with all the recommended values
    - `defaults-base.tfvars` more limited preset; it will prompt user to select the instance type and volume size
- creates AWS SSM documents for jupyter-deploy commands

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
| Name | Location |
|---|---|
| `ami_al2023` | `template/engine/modules/ami_al2023` |
| `ec2_iam_role` | `template/engine/modules/ec2_iam_role` |
| `ec2_instance` | `template/engine/modules/ec2_instance` |
| `network` | `template/engine/modules/network` |
| `secret` | `template/engine/modules/secret` |
| `volumes` | `template/engine/modules/volumes` |

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
| [aws_ebs_volume](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ebs_volume)| resource |
| [aws_efs_file_system](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/efs_file_system)| resource |
| [aws_efs_mount_target](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/efs_mount_target) | resource |
| [aws_eip](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/eip) | resource |
| [aws_subnets](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/subnets) | data source |
| [aws_subnet](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/subnet) | data source |
| [aws_ami](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ami) | data source |
| [aws_route53_zone](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/route53_zone) | data source |
| [aws_ebs_volume](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ebs_volume) | data source |
| [aws_efs_file_system](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/efs_file_system) | data source |
| [aws_iam_policy](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy) | data source |
| [aws_iam_policy_document](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [local_file](https://registry.terraform.io/providers/hashicorp/local/latest/docs/data-sources/file) | data source |

## Inputs
| Name | Type | Default | Description |
|---|---|---|---|
| region | `string` | `us-west-2` | The AWS region where to create the resources |
| instance_type | `string` | `t3.medium` | The type of instance to start |
| key_pair_name | `string` | `null` | The name of key pair |
| ami_id | `string` | `null` | The ID of the AMI to use for the instance |
| min_root_volume_size_gb | `number` | `30` | The minimum size in gigabytes of the root EBS volume for the EC2 instance (will use AMI snapshot size if larger) |
| volume_size_gb | `number` | `30` | The size in GB of the EBS volume the Jupyter Server has access to |
| volume_type | `string` | `gp3` | The type of EBS volume the Jupyter Server will has access to |
| iam_role_prefix | `string` | `Jupyter-deploy-ec2-base` | The prefix for the name of the IAM role for the instance |
| oauth_app_secret_prefix | `string` | `Jupyter-deploy-ec2-base` | The prefix for the name of the AWS secret to store your OAuth app client secret |
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
| log_files_retention_count | `number` | `10` | The maximum number of rotated log files to retain for a log group |
| log_files_retention_days | `number` | `180` | The maximum number of days to retain any log files |
| custom_tags | `map(string)` | `{}` | The custom tags to add to all the resources |
| additional_ebs_mounts | `list(map(string))` | `[]` | Elastic block stores to mount on the notebook home directory |
| additional_efs_mounts | `list(map(string))` | `[]` | Elastic file systems to mount on the notebook home directory |

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
| `server_update_document` | Name of the SSM document to control server container operations |
| `auth_org_unset_document` | Name of the SSM document to remove the allowlisted organization |
| `auth_check_document` | Name of the SSM document to view authorized users, teams and organization |
| `auth_users_update_document` | Name of the SSM document to change the authorized users |
| `auth_teams_update_document` | Name of the SSM document to change the authorized teams |
| `auth_org_set_document` | Name of the SSM document to allowlist an organization |
| `auth_org_unset_document` | Name of the SSM document to remove the allowlisted organization |
| `persisting_resources` | List of identifiers of resources that should not be destroyed |

## License

The Jupyter Deploy AWS EC2 base template is licensed under the [MIT License](LICENSE).