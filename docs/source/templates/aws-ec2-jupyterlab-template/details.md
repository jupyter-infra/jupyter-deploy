# Details

## Networking

The template places the EC2 instance in the default VPC of the selected AWS region. Set the
`availability_zone` variable to place the instance in a specific zone, for example when the chosen
instance type has no capacity in the default zone.

```{warning}
Changing `availability_zone` on an existing deployment replaces every EBS volume and destroys
their data: EBS volumes cannot cross zones, so terraform must recreate them. There is no
plan-time guard. To relocate an existing deployment safely, back up the volumes first with
`jd volume backup --all`, then run `jd config --restore-volumes --availability-zone <zone>`
so each volume is recreated from its backup.
```

There is no Elastic IP and no DNS record: the client proxy resolves the instance's current public
IP live at connection time and pins the instance's certificate, not its address.

The instance's security group only allows ingress on port 443 (HTTPS). There is no SSH access — all
administrator operations go through AWS Systems Manager (SSM).

## Compute

The template selects the latest Amazon Linux 2023 AMI compatible with the chosen instance type:
- Standard AL2023 AMI for CPU instances (x86_64 or arm64)
- Deep Learning AMI (DLAMI) for GPU or Neuron instances

You can also provide a specific AMI ID to override automatic selection.

## Storage

The instance has two volumes. The root volume inherits its size and settings from the selected AMI,
with a configurable minimum size. The template attaches a separate EBS data volume and mounts it
into the **JupyterLab** container at `/home/jovyan` — this volume persists user data (and the TLS
private key) across container restarts and instance stop/start cycles.

You can optionally attach additional EBS volumes or EFS file systems and mount them into the
Jupyter home directory.

## TLS

The instance generates a long-lived self-signed certificate at first boot and persists the key
material on the EBS data volume, so it survives instance stop/start cycles. The instance publishes
only the public certificate PEM to an AWS SSM parameter, which `jd proxy connect-info` reads to pin
the connection. No certificate authority, domain validation, or renewal is involved.

## IAM

The template creates an IAM role for the EC2 instance with permissions for SSM, read access to the
deployment S3 bucket, write access to the certificate-pin SSM parameter, and (optionally) EFS
access.

Beyond the permissions terraform needs to create the resources at deploy time, the local
credentials you use day-to-day need:

- `ec2:DescribeInstances`: resolve the instance's current public IP (there is no Elastic IP)
- `ssm:GetParameter`: read the published self-signed certificate (the TLS pin) from SSM Parameter Store
- `ec2:StartInstances` / `ec2:StopInstances`: only for `jd host start` and `jd host stop`

Minting the AWS-identity token is a local presign that makes no API call, so it needs no extra IAM
permission.

The template creates no secrets: authentication relies on short-lived AWS-identity tokens minted
locally, so there is no OAuth client secret or certificate secret to store.

## Deployment Configuration

An S3 bucket stores the deployment configuration files: bash scripts, Docker service definitions,
and application configuration. The instance pulls these files during setup or updates via an SSM
startup document. The EC2 instance configuration scripts `cloudinit.sh.tftpl` and
`cloudinit-volumes.sh.tftpl` (optional EBS/EFS volume mounts) stay embedded in the SSM document.

| File | Purpose |
|---|---|
| `docker-compose.yml.tftpl` | Docker service definitions |
| `docker-startup.sh` | Docker service startup |
| `generate-cert.sh.tftpl` | Self-signed certificate generation and cert-pin publication |
| `traefik.yml` | Traefik static configuration |
| `traefik-dynamic.yml` | Traefik dynamic configuration (routers, ForwardAuth and compression middleware, TLS) |
| `dockerfile.jupyter` | Jupyter container image |
| `jupyter-start.sh` | Jupyter container entrypoint |
| `jupyter-reset.sh` | Fallback if Jupyter fails to start |
| `pyproject.jupyter.toml` | Python dependencies for the Jupyter environment |
| `pyproject.kernel.toml` | Python dependencies for an additional Jupyter kernel |
| `jupyter_server_config.py` | Jupyter server settings |
| `auth-sidecar/` | Go sources and Dockerfile for the AWS-identity token validator |
| `dockerfile.logrotator` | Log rotation sidecar container |
| `logrotator-start.sh.tftpl` | Logrotate configuration |
| `fluent-bit.conf` | Fluent Bit log collection configuration |
| `parsers.conf` | Fluent Bit Docker log parsers |

If you selected `pixi` as the package manager, the template uses `pixi.jupyter.toml` and the
pixi variants of the Jupyter container files instead.

An SSM association triggers the startup script on the instance whenever the configuration changes.

## Operations

The template creates SSM documents that the `jd` CLI uses to manage the deployment remotely:

| Document | Purpose |
|---|---|
| `check-status-internal.sh` | Verify services are running and the certificate is available |
| `get-status.sh` | Translate status checks to human-readable output |
| `update-server.sh` | Update running services (start/stop/restart) |
| `update-allowlist.sh` | Update the allowlisted IAM role and user names |
| `get-allowlist.sh` | Retrieve the current allowlist |

## Logging

Fluent Bit collects Docker service logs and writes them to `/var/log/services` on the instance
volume. A logrotate sidecar container handles automatic rotation of all log files based on
configurable size and retention settings.

## Presets

The template provides one variable preset:
- **`defaults-all.tfvars`**: comprehensive preset with all recommended values

## Terraform Modules

| Name | Location |
|---|---|
| `ami_al2023` | `template/engine/modules/ami_al2023` |
| `ec2_iam_role` | `template/engine/modules/ec2_iam_role` |
| `ec2_instance` | `template/engine/modules/ec2_instance` |
| `network` | `template/engine/modules/network` |
| `s3_bucket` | `template/engine/modules/s3_bucket` |
| `volumes` | `template/engine/modules/volumes` |

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| region | `string` | `us-west-2` | The AWS region where to create the resources |
| jupyter_package_manager | `string` | `uv` | The package manager for Jupyter: `uv` (faster, native Python) or `pixi` (conda-forge, supports non-Python dependencies) |
| instance_type | `string` | `t3.medium` | The type of instance to start |
| availability_zone | `string` | `any` | The availability zone for the instance and its EBS volumes; `any` accepts the first subnet of the default VPC. Changing this on an existing deployment replaces the EBS volumes (see the Networking warning) |
| ami_id | `string` | `null` | The ID of the AMI to use for the instance; leave empty for the latest AL2023 |
| min_root_volume_size_gb | `number` | `30` | The minimum size in gigabytes of the root EBS volume for the EC2 instance (will use the AMI snapshot size plus a buffer of 33% or 10 GB, whichever is greater, if that is larger) |
| volume_size_gb | `number` | `30` | The size in GB of the EBS volume the Jupyter Server has access to |
| volume_type | `string` | `gp3` | The type of EBS volume the Jupyter Server has access to |
| iam_role_prefix | `string` | `Jupyter-deploy-jupyterlab` | The prefix for the name of the IAM role for the instance |
| s3_bucket_prefix | `string` | `jupyter-deploy-jupyterlab` | The prefix for the name of the S3 bucket where deployment scripts are stored |
| iam_role_names_allowlist | `list(string)` | `[]` | Bare IAM role names authorized to reach the app (the deploying identity is always authorized) |
| iam_user_names_allowlist | `list(string)` | `[]` | Bare IAM user names authorized to reach the app (the deploying identity is always authorized) |
| log_files_rotation_size_mb | `number` | `50` | The size in megabytes at which to rotate log files |
| log_files_retention_count | `number` | `10` | The maximum number of rotated log files to retain for a log group |
| log_files_retention_days | `number` | `180` | The maximum number of days to retain any log files |
| custom_tags | `map(string)` | `{}` | The custom tags to add to all the resources |
| additional_ebs_mounts | `list(map(string))` | `[]` | Elastic block stores to mount on the notebook home directory |
| additional_efs_mounts | `list(map(string))` | `[]` | Elastic file systems to mount on the notebook home directory |
| ebs_snapshot_ids | `map(string)` | `{}` | Map of volume name to the EBS snapshot id to create that volume from |

## Outputs

| Name | Description |
|---|---|
| `instance_id` | The ID of the EC2 instance |
| `ami_id` | The Amazon Machine Image ID used by the EC2 instance |
| `cert_pin_ssm_parameter_name` | Name of the SSM parameter holding the instance self-signed certificate PEM |
| `iam_role_names_allowlist` | IAM role names authorized to reach the app (includes the deployer's role, if any) |
| `iam_user_names_allowlist` | IAM user names authorized to reach the app (includes the deployer's user, if any) |
| `deployment_scripts_bucket_name` | Name of the S3 bucket where deployment scripts and service configuration files are stored |
| `deployment_scripts_bucket_arn` | ARN of the S3 bucket where deployment scripts and service configuration files are stored |
| `region` | The AWS region where the resources were created |
| `deployment_id` | Unique identifier for this deployment |
| `images_build_hash` | Hash of files affecting docker compose image builds (jupyter, auth-sidecar, log-rotator) |
| `scripts_files_hash` | Hash of all deployment script files which controls SSM association re-execution |
| `server_status_check_document` | Name of the SSM document to check the server status |
| `server_update_document` | Name of the SSM document to control server container operations (start/stop/restart) |
| `server_logs_document` | Name of the SSM document to retrieve server container logs |
| `server_exec_document` | Name of the SSM document to execute commands inside server containers |
| `server_connect_document` | Name of the SSM document to start interactive shell sessions inside server containers |
| `auth_users_update_document` | Name of the SSM document to update the allowlisted IAM user names |
| `auth_teams_update_document` | Name of the SSM document to update the allowlisted IAM role names |
| `auth_check_document` | Name of the SSM document to read the allowlisted IAM principal names |
| `persisting_resources` | List of identifiers of resources that should not be destroyed |
| `availability_zone` | Availability zone the instance and its EBS volumes are placed in |
| `jupyter_data_volume_id` | ID of the EBS volume mounted on the notebook home directory |
| `additional_ebs_volumes` | JSON-encoded inventory of the configured additional EBS mounts, consumed by `jd volume` |
| `additional_efs_volumes` | JSON-encoded inventory of the configured additional EFS mounts, consumed by `jd volume` |
