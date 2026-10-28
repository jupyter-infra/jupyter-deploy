# Details

## Networking

The template places the EC2 instance in the first subnet of the default VPC in the selected AWS region, or optionally in the subnet mapping to the zone you select with the `availability_zone` variable. The template assigns an Elastic IP (EIP) to the instance to keep its public IP address stable across stop/start cycles.

Amazon Route 53 manages DNS. The template references a Hosted Zone for your domain (which must already exist) and adds a DNS record pointing your subdomain to the instance's Elastic IP.

The instance's security group only allows ingress on port 443 (HTTPS). There is no SSH access — all administrator operations go through AWS Systems Manager (SSM).

## Compute

The template selects the latest Amazon Linux 2023 AMI compatible with the chosen instance type:
- Standard AL2023 AMI for CPU instances (x86_64 or arm64)
- Deep Learning AMI (DLAMI) for GPU or Neuron instances (x86_64 or arm64)

You can also provide a specific AMI ID to override automatic selection.

## Storage

The instance has two volumes. The root volume inherits its size and settings from the selected AMI, with a configurable minimum size. It persists across instance restarts and instance type changes, as long as the new instance type is compatible with the existing root volume. The template attaches a separate EBS data volume and mounts it into the **JupyterLab** container at `/home/jovyan` — this volume persists user data across container restarts and instance stop/start cycles.

You can optionally attach additional EBS volumes or EFS file systems and mount them into the Jupyter home directory.

EBS volumes cannot cross availability zones, so changing `availability_zone` on a live deployment replaces them. Back them up with `jd volume backup` and restore them with `jd config --restore-volumes` first — see the `AGENT.md` in your project directory for the full sequence. EFS file systems are regional and need none of this.

## TLS

[Let's Encrypt](https://letsencrypt.org/) provides TLS certificates using the [ACME](https://datatracker.ietf.org/doc/html/rfc8555) protocol. Traefik acts as the ACME client and proves domain ownership via a [DNS-01 challenge](https://letsencrypt.org/docs/challenge-types/#dns-01-challenge): it creates a temporary TXT record in the Route 53 Hosted Zone, Let's Encrypt verifies it, and issues the certificate. Traefik stores the certificate in `acme.json` and renews it automatically. The template also backs the certificate up to AWS Secrets Manager so it persists across instance replacements.

## IAM and Secrets

The template creates an IAM role for the EC2 instance with permissions for SSM, Route 53, S3, and (optionally) EFS access.

With `bedrock_enabled` set to `true` (the default), the template also creates a `bedrock-app` IAM
role carrying only the Bedrock inference policy: it may invoke the models matching
`bedrock_model_patterns` through the inference profiles that `bedrock_inference_scope` selects, and
only the instance role may assume it. A `bedrock-sidecar` container assumes it every 15 minutes and
publishes the credentials to a file that the Jupyter container mounts read-only. The Jupyter
container runs on its own docker network, which a host firewall rule cuts off from the instance
metadata service, so code in the container holds the `bedrock-app` credentials and never the
instance role's. The instance requires IMDSv2 with a hop limit of 2 so that the sidecar and Traefik
(Route 53 ACME), one docker-bridge hop away, can read the instance role credentials. A container
holding `/var/run/docker.sock` can bypass the firewall rule; that is tracked separately.

The template creates two AWS Secrets Manager secrets:
- One to store the OAuth App client secret
- One to store TLS certificates from Let's Encrypt, ensuring they persist across instance replacements

## Deployment Configuration

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
| `claude-managed-settings.json` | Claude Code system settings (Bedrock, no auto-update) |
| `codex-config.toml` | Codex system configuration (Bedrock provider and model) |
| `pick-codex-model.py` | Picks the Codex model from the Codex release's catalog at image build |
| `bedrock-sidecar/Dockerfile` | Bedrock credential sidecar image (AWS CLI) |
| `bedrock-sidecar/refresh.sh` | Assumes the `bedrock-app` role every 15 minutes and publishes its credentials |
| `aws-config` | AWS config of the Jupyter container: reads the published credentials through `credential_process` |
| `dockerfile.logrotator` | Log rotation sidecar container |
| `logrotator-start.sh.tftpl` | Logrotate configuration |
| `fluent-bit.conf` | Fluent-bit log collection configuration |
| `parsers.conf` | Fluent-bit Docker log parsers |

If you selected `pixi` as the dependency manager, the template uses `pixi.jupyter.toml` instead of `pyproject.jupyter.toml`.

An SSM association triggers the startup script on the instance whenever the configuration changes.

## Operations

The template creates SSM documents that the `jd` CLI uses to manage the deployment remotely:

| Document | Purpose |
|---|---|
| `check-status-internal.sh` | Verify services are running and TLS certificates are available |
| `get-status.sh` | Translate status checks to human-readable output |
| `update-auth.sh` | Update authorized org, teams, and/or users |
| `get-auth.sh` | Retrieve current authorization settings |
| `update-server.sh` | Update running services |
| `refresh-oauth-cookie.sh` | Rotate the OAuth cookie secret and invalidate all sessions |

## Logging

Fluent-bit collects Docker service logs and writes them to `/var/log/services` on the instance volume. A logrotate sidecar container handles automatic rotation of all log files based on configurable size and retention settings.

## Presets

The template provides two variable presets:
- **`defaults-all.tfvars`** — comprehensive preset with all recommended values
- **`defaults-base.tfvars`** — minimal preset that prompts for instance type and volume size

## Terraform Modules

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
| claude_code_version | `string` | `2.1.302` | The Claude Code version installed in the Jupyter image |
| codex_version | `string` | `0.163.0` | The Codex CLI version installed in the Jupyter image |
| bedrock_enabled | `bool` | `true` | Whether Claude Code and Codex may call Amazon Bedrock, through the `bedrock-app` role |
| bedrock_inference_scope | `string` | `geo` | The Bedrock inference profiles to use: `geo` (the region's geography) or `global` |
| bedrock_model_patterns | `list(string)` | `["anthropic.claude-*", "openai.gpt-*"]` | The Bedrock model IDs the `bedrock-app` role may invoke, as IAM wildcards without the inference profile prefix |

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
