# Jupyter Deploy AWS EC2 base template

The **AWS Base Template** deploys a **JupyterLab** application to a dedicated Amazon EC2 instance,
served on your domain with encrypted HTTPS, GitHub OAuth integration,
real-time collaboration, and fast UV-based environments.

**Documentation:** [jupyter-deploy.readthedocs.io](https://jupyter-deploy.readthedocs.io)

The **AWS Base Template** is maintained and supported by AWS.

## 10k View

When you navigate to the application URL in your web browser, you connect to the EC2 instance over HTTPS. On the first visit, the instance redirects to GitHub for OAuth authentication; once verified, you connect to the `jupyter` container within your EC2 instance and see a **JupyterLab** application in your web browser.

![Overview](https://raw.githubusercontent.com/jupyter-infra/jupyter-deploy/main/docs/source/templates/aws-base-template/diagrams/overview.svg)

## Prerequisites

### Installation

- Install the **JupyterDeploy** CLI with the `aws` option: `uv add "jupyter-deploy[aws]"`
- Install the **AWS EC2 Base** template: `uv add jupyter-deploy-tf-aws-ec2-base`

If you use `pip` instead of `uv`, run `pip install "jupyter-deploy[aws]" jupyter-deploy-tf-aws-ec2-base`.

### AWS account
The template needs to create AWS resources. Your local environment needs access to valid AWS credentials.

If you do not have an AWS account, follow the [official guide](https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-creating.html) to create one.

If you already have an AWS account, make sure your [CLI credentials are configured](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html).

### Get and register a domain
The template serves your **JupyterLab** app to a URL in your own domain. You will need to specify this domain when you configure the project.

If you already own a domain, register it with Amazon Route 53 using this [guide](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/welcome-domain-registration.html).

If you do not own a domain yet, you can buy one through Amazon Route 53 using this [guide](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/domain-register.html#domain-register-procedure-section).

### Setup a GitHub OAuth app

The template gates access to your **JupyterLab** application with GitHub identities. You will need to create a GitHub OAuth app for this purpose.

First, log on to GitHub on your web browser, then use [this link](https://github.com/settings/applications/new) to create a new OAuth app.

You can choose any name for the application; for example `jupyter-deploy-aws-base`.

Set `Homepage URL` to: `https://<subdomain>.<domain>`; for example `https://jupyterlab-app.<domain>`.
`<domain>` corresponds to the domain above. You can choose any `<subdomain>` you like, but it must be a valid domain part (lowercase letters, digits, or hyphens).

Set `Authorization callback URL` to: `https://<subdomain>.<domain>/oauth2/callback`.
Make sure it matches the `<domain>` and `<subdomain>` exactly.

In the next page, write down and save your app client ID. Generate an app client secret, and write it down as well.

Refer to GitHub [documentation](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app) for more details.

## Usage
This terraform project is meant to be used with the [jupyter-deploy](https://github.com/jupyter-infra/jupyter-deploy/tree/main/libs/jupyter-deploy) CLI.

### Installation
Recommended: create or activate a Python virtual environment.

```bash
uv add "jupyter-deploy[aws]" jupyter-deploy-tf-aws-ec2-base
```

Or with pip:

```bash
pip install "jupyter-deploy[aws]" jupyter-deploy-tf-aws-ec2-base
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

## Architecture

### Containers

The application runs as a set of containerized services orchestrated by Docker Compose. [Traefik](https://doc.traefik.io/traefik/) acts as the reverse proxy — it handles TLS termination, routes incoming HTTPS requests, and delegates authentication decisions to [OAuth2 Proxy](https://oauth2-proxy.github.io/oauth2-proxy/) via the [ForwardAuth](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/forwardauth/) middleware. OAuth2 Proxy manages the full [OAuth 2.0](https://datatracker.ietf.org/doc/html/rfc6749) flow with [GitHub as the identity provider](https://oauth2-proxy.github.io/oauth2-proxy/configuration/providers/github), handling redirects, token validation, and session cookies. Traefik forwards authenticated requests to the **JupyterLab** container. A Fluent Bit sidecar collects service logs and a logrotate container manages log retention on disk.

![Containers](https://raw.githubusercontent.com/jupyter-infra/jupyter-deploy/main/docs/source/templates/aws-base-template/diagrams/containers.svg)

### Authentication flow

On first visit, Traefik forwards the request to OAuth2 Proxy, which redirects the browser to GitHub for authentication. GitHub prompts the user to authorize the OAuth App, then redirects back to OAuth2 Proxy with an authorization code. OAuth2 Proxy exchanges the code for an access token, verifies the user's identity against the configured allowlist, sets a session cookie, and lets the request through to **JupyterLab**. The session cookie authenticates subsequent requests without repeating the OAuth dance. See the [OAuth2 Proxy GitHub provider documentation](https://oauth2-proxy.github.io/oauth2-proxy/configuration/providers/github) for details.

![Authentication flow](https://raw.githubusercontent.com/jupyter-infra/jupyter-deploy/main/docs/source/templates/aws-base-template/diagrams/auth-flow.svg)

## Details

### Networking

The template places the EC2 instance in the first subnet of the default VPC in the selected AWS region, or optionally in the subnet mapping to the zone you select with the `availability_zone` variable. The template assigns an Elastic IP (EIP) to the instance to keep its public IP address stable across stop/start cycles.

Amazon Route 53 manages DNS. The template references a Hosted Zone for your domain (which must already exist) and adds a DNS record pointing your subdomain to the instance's Elastic IP.

The instance's security group only allows ingress on port 443 (HTTPS). There is no SSH access — all administrator operations go through AWS Systems Manager (SSM).

### Compute

The template selects the latest Amazon Linux 2023 AMI compatible with the chosen instance type:
- Standard AL2023 AMI for CPU instances (x86_64 or arm64)
- Deep Learning AMI (DLAMI) for GPU or Neuron instances (x86_64 or arm64)

You can also provide a specific AMI ID to override automatic selection.

### Storage

The instance has two volumes. The root volume inherits its size and settings from the selected AMI, with a configurable minimum size. It persists across instance restarts and instance type changes, as long as the new instance type is compatible with the existing root volume. The template attaches a separate EBS data volume and mounts it into the **JupyterLab** container at `/home/jovyan` — this volume persists user data across container restarts and instance stop/start cycles.

You can optionally attach additional EBS volumes or EFS file systems and mount them into the Jupyter home directory.

EBS volumes cannot cross availability zones, so changing `availability_zone` on a live deployment replaces them. Back them up with `jd volume backup` and restore them with `jd config --restore-volumes` first — see the `AGENT.md` in your project directory for the full sequence. EFS file systems are regional and need none of this.

### TLS

[Let's Encrypt](https://letsencrypt.org/) provides TLS certificates using the [ACME](https://datatracker.ietf.org/doc/html/rfc8555) protocol. Traefik acts as the ACME client and proves domain ownership via a [DNS-01 challenge](https://letsencrypt.org/docs/challenge-types/#dns-01-challenge): it creates a temporary TXT record in the Route 53 Hosted Zone, Let's Encrypt verifies it, and issues the certificate. Traefik stores the certificate in `acme.json` and renews it automatically. The template also backs the certificate up to AWS Secrets Manager so it persists across instance replacements.

### IAM and Secrets

The template creates an IAM role for the EC2 instance with permissions for SSM, Route 53, S3, and (optionally) EFS access.

The template creates two AWS Secrets Manager secrets:
- One to store the OAuth App client secret
- One to store TLS certificates from Let's Encrypt, ensuring they persist across instance replacements

### Deployment Configuration

An S3 bucket stores all deployment configuration files: bash scripts, Docker service definitions, and application configuration. The instance pulls these files during setup or updates via a cloud-init script.

The template creates an SSM startup document that orchestrates instance configuration using these files:

| File | Purpose |
|---|---|
| `cloudinit.sh.tftpl` | EC2 instance configuration |
| `docker-compose.yml.tftpl` | Docker service definitions |
| `docker-startup.sh.tftpl` | Docker service startup |
| `cloudinit-volumes.sh.tftpl` | Optional EBS/EFS volume mounts |
| `traefik.yml.tftpl` | Traefik reverse proxy configuration |
| `dockerfile.jupyter` | Jupyter container image |
| `jupyter-start.sh` | Jupyter container entrypoint |
| `jupyter-reset.sh` | Fallback if Jupyter fails to start |
| `pyproject.jupyter.toml` | Python dependencies for the Jupyter environment |
| `jupyter_server_config.py` | Jupyter server settings |
| `dockerfile.logrotator` | Log rotation sidecar container |
| `logrotator-start.sh.tftpl` | Logrotate configuration |
| `fluent-bit.conf` | Fluent-bit log collection configuration |
| `parsers.conf` | Fluent-bit Docker log parsers |

If you selected `pixi` as the dependency manager, the template uses `pixi.jupyter.toml` instead of `pyproject.jupyter.toml`.

An SSM association triggers the startup script on the instance whenever the configuration changes.

### Operations

The template creates SSM documents that the `jd` CLI uses to manage the deployment remotely:

| Document | Purpose |
|---|---|
| `check-status-internal.sh` | Verify services are running and TLS certificates are available |
| `get-status.sh` | Translate status checks to human-readable output |
| `update-auth.sh` | Update authorized org, teams, and/or users |
| `get-auth.sh` | Retrieve current authorization settings |
| `update-server.sh` | Update running services |
| `refresh-oauth-cookie.sh` | Rotate the OAuth cookie secret and invalidate all sessions |

### Logging

Fluent-bit collects Docker service logs and writes them to `/var/log/services` on the instance volume. A logrotate sidecar container handles automatic rotation of all log files based on configurable size and retention settings.

### Presets

The template provides two variable presets:
- **`defaults-all.tfvars`** — comprehensive preset with all recommended values
- **`defaults-base.tfvars`** — minimal preset that prompts for instance type and volume size

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
| `certs_secret` | `template/engine/modules/certs_secret` |
| `ec2_iam_role` | `template/engine/modules/ec2_iam_role` |
| `ec2_instance` | `template/engine/modules/ec2_instance` |
| `network` | `template/engine/modules/network` |
| `s3_bucket` | `template/engine/modules/s3_bucket` |
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
| [aws_s3_bucket](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket) | resource |
| [aws_s3_bucket_versioning](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_versioning) | resource |
| [aws_s3_bucket_server_side_encryption_configuration](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_server_side_encryption_configuration) | resource |
| [aws_s3_bucket_public_access_block](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block) | resource |
| [aws_s3_object](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_object) | resource |
| [aws_subnets](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/subnets) | data source |
| [aws_ec2_instance_type_offerings](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ec2_instance_type_offerings) | data source |
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
| jupyter_package_manager | `string` | `uv` | The package manager for the Jupyter environment (`uv` or `pixi`) |
| instance_type | `string` | `t3.medium` | The type of instance to start |
| key_pair_name | `string` | `null` | The name of key pair |
| ami_id | `string` | `null` | The ID of the AMI to use for the instance |
| availability_zone | `string` | `any` | The availability zone for the instance and its EBS volumes; `any` uses the first subnet of the VPC |
| min_root_volume_size_gb | `number` | `30` | The minimum size in gigabytes of the root EBS volume for the EC2 instance (will use AMI snapshot size if larger) |
| volume_size_gb | `number` | `30` | The size in GB of the EBS volume the Jupyter Server has access to |
| volume_type | `string` | `gp3` | The type of EBS volume the Jupyter Server will has access to |
| iam_role_prefix | `string` | `Jupyter-deploy-ec2-base` | The prefix for the name of the IAM role for the instance |
| oauth_app_secret_prefix | `string` | `Jupyter-deploy-ec2-base` | The prefix for the name of the AWS secret to store your OAuth app client secret |
| s3_bucket_prefix | `string` | `jupyter-deploy-ec2-base` | The prefix for the name of the S3 bucket where deployment scripts are stored (3-28 characters, lowercase alphanumeric with hyphens) |
| certs_secret_prefix | `string` | `Jupyter-deploy-ec2-base` | The prefix for the name of the AWS secret where ACME certificates are stored |
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
| ebs_snapshot_ids | `map(string)` | `{}` | Map of volume name to the EBS snapshot to create it from; written by `jd config --restore-volumes` |

## Outputs
| Name | Description |
|---|---|
| `jupyter_url` | The URL to access your notebook app |
| `auth_callback_url` | The URL for the OAuth callback - do not use directly |
| `instance_id` | The ID of the EC2 instance |
| `ami_id` | The Amazon Machine Image ID used by the EC2 instance |
| `jupyter_server_public_ip` | The public IP assigned to the EC2 instance |
| `secret_arn` | The ARN of the AWS Secret storing the OAuth client secret |
| `certs_secret_arn` | The ARN of the AWS Secret where TLS certificates are stored |
| `deployment_scripts_bucket_name` | Name of the S3 bucket where deployment scripts and service configuration files are stored |
| `deployment_scripts_bucket_arn` | ARN of the S3 bucket where deployment scripts and service configuration files are stored |
| `region` | The AWS region where the resources were created |
| `deployment_id` | Unique identifier for this deployment |
| `images_build_hash` | Hash of files affecting docker compose image builds (jupyter, log-rotator) |
| `scripts_files_hash` | Hash of all deployment script files which controls SSM association re-execution |
| `server_status_check_document` | Name of the SSM document to verify if the server is ready to serve traffic |
| `server_update_document` | Name of the SSM document to control server container operations |
| `server_logs_document` | Name of the SSM document to print server logs to terminal |
| `server_exec_document` | Name of the SSM document to execute commands inside server containers |
| `server_connect_document` | Name of the SSM document to start interactive shell sessions inside server containers (jupyter or traefik) |
| `auth_check_document` | Name of the SSM document to view authorized users, teams and organization |
| `auth_users_update_document` | Name of the SSM document to change the authorized users |
| `auth_teams_update_document` | Name of the SSM document to change the authorized teams |
| `auth_org_set_document` | Name of the SSM document to allowlist an organization |
| `auth_org_unset_document` | Name of the SSM document to remove the allowlisted organization |
| `persisting_resources` | List of identifiers of resources that should not be destroyed |
| `availability_zone` | The availability zone the instance and its EBS volumes are placed in |
| `jupyter_data_volume_id` | The ID of the EBS volume mounted on the notebook home directory |
| `additional_ebs_volumes` | JSON-encoded inventory of the configured additional EBS mounts, consumed by `jd volume` |
| `additional_efs_volumes` | JSON-encoded inventory of the configured additional EFS mounts, consumed by `jd volume` |

## License

The **AWS Base Template** is licensed under the [MIT License](https://github.com/jupyter-infra/jupyter-deploy/blob/main/libs/jupyter-deploy-tf-aws-ec2-base/LICENSE).