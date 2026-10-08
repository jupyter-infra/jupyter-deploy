# Jupyter Deploy AWS EC2 JupyterLab template

The **AWS EC2 JupyterLab Template** deploys a **single-user JupyterLab** application to a dedicated
Amazon EC2 instance, reached from your laptop through a local client proxy over a pinned
self-signed TLS connection, authorized by your AWS identity.

**AWS credentials are the only prerequisite.**

**Documentation:** [jupyter-deploy.readthedocs.io](https://jupyter-deploy.readthedocs.io)

The **AWS EC2 JupyterLab Template** is maintained and supported by AWS.

## 10k View

When you run `jd open`, `jupyter-deploy` starts a local proxy on your laptop and opens your web
browser to a loopback address (for example `http://127.0.0.1:PORT/lab`). Your browser connects to
your app via the local proxy; the proxy forwards each request to the EC2 instance over TLS. The app
authenticates and authorizes each request based on your AWS credentials.

![Overview](https://raw.githubusercontent.com/jupyter-infra/jupyter-deploy/main/docs/source/templates/aws-ec2-jupyterlab-template/diagrams/overview.svg)

## Prerequisites

### Installation

- Install the **JupyterDeploy** CLI with the `aws`, `proxy` options: `uv add "jupyter-deploy[aws,proxy]"`
- Install the **AWS EC2 JupyterLab** template: `uv add jupyter-deploy-tf-aws-ec2-jupyterlab`

If you use `pip` instead of `uv`, run `pip install "jupyter-deploy[aws,proxy]" jupyter-deploy-tf-aws-ec2-jupyterlab`.

### AWS account

The template needs to create AWS resources. Your local environment needs access to valid AWS credentials.

If you do not have an AWS account, follow the [official guide](https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-creating.html) to create one.

If you already have an AWS account, make sure your [CLI credentials are configured](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html).

> **Note:** You must deploy as an **IAM role** (assumed role) or an **IAM user**. The template rejects root and
> federated identities at plan time, because access to the application is granted by allowlisting IAM
> role and user names.

## Usage

This terraform project is meant to be used with the [jupyter-deploy](https://github.com/jupyter-infra/jupyter-deploy/tree/main/libs/jupyter-deploy) CLI.

### Installation

Recommended: create or activate a Python virtual environment.

```bash
uv add "jupyter-deploy[aws,proxy]" jupyter-deploy-tf-aws-ec2-jupyterlab
```

Or with pip:

```bash
pip install "jupyter-deploy[aws,proxy]" jupyter-deploy-tf-aws-ec2-jupyterlab
```

The `proxy` extra installs the local client proxy that `jd open` and `jd proxy` use to reach the
instance.

### Project setup

```bash
mkdir my-jupyterlab-deployment
cd my-jupyterlab-deployment

jd init . -E terraform -P aws -I ec2 -T jupyterlab
```

Consider making `my-jupyterlab-deployment` a git repository.

### Configure and create the infrastructure

```bash
jd config
jd up
```

The template has no required variables, so `jd config` does not prompt for anything and the
deployment uses the template defaults. To change a default such as the region, instance type, or
volume size, pass it as a flag (for example `jd config --instance-type t3.large`) or edit the
`overrides:` section of `variables.yaml`. Run `jd config --help` to list every variable.

### Access your JupyterLab application

```bash
# verify that your host and containers are running
jd host status
jd server status

# start the local proxy and open your application in your web browser
jd open
```

`jd open` runs in the foreground by default; press Ctrl-C to stop it. Pass -d or --detached to run
it in the background.

You can also drive the proxy directly:

```bash
# start the proxy in the background, then open a tab against it
jd proxy start
jd proxy open

# inspect it
jd proxy status
jd proxy show --json

# stop it
jd proxy stop
```

### Manage access

Access is granted by AWS IAM identity. The deploying identity is always authorized. To grant
others, allowlist their IAM role or IAM user names (matched case-insensitively by bare name,
scoped to this AWS account):

```bash
# By IAM role names
jd teams list
jd teams add ROLE-NAME1 ROLE-NAME2
jd teams remove ROLE-NAME1
jd teams set ROLE-NAME1 ROLE-NAME2

# By IAM user names
jd users list
jd users add USER-NAME1 USER-NAME2
jd users remove USER-NAME1
jd users set USER-NAME1 USER-NAME2
```

`jd teams` manages IAM **roles**; `jd users` manages IAM **users**. Pass bare names (for example
`DataScience` or `alice`), not ARNs or paths.

These commands recreate only the auth sidecar container (about 1-2 seconds) and leave
**JupyterLab** running. They also write the change back into the
`iam_role_names_allowlist` / `iam_user_names_allowlist` terraform variables, so a later `jd up`
re-applies the same list rather than reverting it.

Editing those variables and running `jd up` also reconciles the allowlist, but restarts the whole
application. Prefer the commands above for routine access changes.

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

The instance's public IP usually changes after a stop/start cycle. This is a non-event: the proxy
resolves the IP live at connection time and pins the instance's certificate, not its address.

### Manage your EC2 instance

```bash
# connect to your host
jd host connect

# disconnect
exit
```

The interactive `jd host connect` and `jd server connect` commands open an AWS SSM session and
require the [AWS Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html)
installed locally. It is not needed for `jd up`, `jd open`, `jd proxy`, or the
`jd server logs` / `jd server exec` commands.

### Take down all the infrastructure

This operation removes all the resources associated with this project in your AWS account.

```bash
jd down
```

## Architecture

### Infrastructure

The template keeps the AWS footprint minimal to keep costs low: there is no load balancer, no
Elastic IP, and no Route 53 hosted zone or DNS record. It provisions the following:

- **VPC**: The default VPC of the selected region, reached from the internet through the VPC's
  internet gateway.
- **Subnet and availability zone**: The EC2 instance and its EBS volumes are placed in one
  availability zone, in one subnet. EBS volumes cannot cross zones, so they always live in the
  instance's zone.
- **EC2 instance**: Runs the containerized application. It has a public IPv4 address that may
  change across stop/start cycles; its security group allows inbound traffic on port 443 only.
- **EBS volumes**: A root volume and a data volume mounted at `/home/jovyan` that persists user
  data and the TLS private key.
- **Regional services**: AWS STS validates the AWS-identity tokens, AWS Systems Manager (SSM) runs
  administrator commands and stores the pinned certificate, and an S3 bucket holds the deployment
  configuration files.

![Infrastructure](https://raw.githubusercontent.com/jupyter-infra/jupyter-deploy/main/docs/source/templates/aws-ec2-jupyterlab-template/diagrams/infrastructure.svg)

### Containers

The application runs as a set of containerized services orchestrated by Docker Compose.
[Traefik](https://doc.traefik.io/traefik/) terminates TLS on port 443 with the self-signed
certificate and delegates authentication decisions to the auth sidecar via the
[ForwardAuth](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/forwardauth/)
middleware. The auth sidecar is a small Go service that validates the AWS-identity token. Traefik
forwards authenticated requests to the **JupyterLab** container and compresses the responses
(except server-sent event streams, which **JupyterLab** uses for live updates). A **Fluent Bit**
sidecar collects service logs, and a log-rotator container manages log retention on disk.

![Containers](https://raw.githubusercontent.com/jupyter-infra/jupyter-deploy/main/docs/source/templates/aws-ec2-jupyterlab-template/diagrams/containers.svg)

### Data path

The browser never talks to the instance directly. It talks plain HTTP to a local client proxy
bound to a loopback address on your laptop. The proxy forwards each request to the instance's
Traefik on port 443 over TLS, verifying the connection against the instance's pinned self-signed
certificate, and injects a short-lived AWS-identity (STS) token as a request header. Because the
pin is on the certificate rather than the address, a new public IP after an instance stop/start
does not break the connection.

### Certificate pinning

The instance generates a long-lived self-signed TLS certificate at first boot and persists the
private key on the EBS data volume, so the certificate survives instance stop/start cycles. The
instance publishes only the public certificate PEM to an AWS SSM parameter. `jd proxy connect-info`
reads that parameter live and hands the PEM to the client proxy as the pin target. The private key
never leaves the instance, and the certificate value never lands in the terraform state.

### Authentication flow

`jd proxy connect-info` mints a `k8s-aws-v1` token: a presigned `sts:GetCallerIdentity` URL bound
to this deployment's identifier. The proxy attaches the token to every request. On the instance, a
ForwardAuth sidecar behind Traefik validates each token by replaying the presigned call against
AWS STS, checking the deployment binding (the `x-k8s-aws-id` header), verifying the AWS account,
and matching the returned IAM identity against the allowlist of role and user names. Requests with
a valid token from an allowlisted identity reach **JupyterLab**; everything else is rejected. No
shared secret is stored anywhere.

### Network boundary

The instance's security group allows inbound traffic on port 443 only, open to `0.0.0.0/0`.
The access boundary is the pinned self-signed TLS connection plus the short-lived AWS-identity
token, not the network layer. There is no SSH access; all administrator operations go through
AWS Systems Manager (SSM). SSM handles host and server administration only, never the
**JupyterLab** data path.

### Request flow in detail

For a step-by-step view of a single request from the browser to **JupyterLab**, including token
minting and validation, see the sequence below.

![Proxy and authentication flow](https://raw.githubusercontent.com/jupyter-infra/jupyter-deploy/main/docs/source/templates/aws-ec2-jupyterlab-template/diagrams/proxy-flow.svg)

## Details

### Networking

The template places the EC2 instance in the default VPC of the selected AWS region. Set the
`availability_zone` variable to place the instance in a specific zone, for example when the chosen
instance type has no capacity in the default zone.

> **Warning:** Changing `availability_zone` on an existing deployment replaces every EBS volume and destroys
> their data: EBS volumes cannot cross zones, so terraform must recreate them. There is no
> plan-time guard. To relocate an existing deployment safely, back up the volumes first with
> `jd volume backup --all`, then run `jd config --restore-volumes --availability-zone <zone>`
> so each volume is recreated from its backup.

There is no Elastic IP and no DNS record: the client proxy resolves the instance's current public
IP live at connection time and pins the instance's certificate, not its address.

The instance's security group only allows ingress on port 443 (HTTPS). There is no SSH access — all
administrator operations go through AWS Systems Manager (SSM).

### Compute

The template selects the latest Amazon Linux 2023 AMI compatible with the chosen instance type:
- Standard AL2023 AMI for CPU instances (x86_64 or arm64)
- Deep Learning AMI (DLAMI) for GPU or Neuron instances

You can also provide a specific AMI ID to override automatic selection.

### Storage

The instance has two volumes. The root volume inherits its size and settings from the selected AMI,
with a configurable minimum size. The template attaches a separate EBS data volume and mounts it
into the **JupyterLab** container at `/home/jovyan` — this volume persists user data (and the TLS
private key) across container restarts and instance stop/start cycles.

You can optionally attach additional EBS volumes or EFS file systems and mount them into the
Jupyter home directory.

### TLS

The instance generates a long-lived self-signed certificate at first boot and persists the key
material on the EBS data volume, so it survives instance stop/start cycles. The instance publishes
only the public certificate PEM to an AWS SSM parameter, which `jd proxy connect-info` reads to pin
the connection. No certificate authority, domain validation, or renewal is involved.

### IAM

The template creates an IAM role for the EC2 instance with permissions for SSM, read access to the
deployment S3 bucket, write access to the certificate-pin SSM parameter, and (optionally) EFS
access.

The template creates no secrets: authentication relies on short-lived AWS-identity tokens minted
locally, so there is no OAuth client secret or certificate secret to store.

### Deployment Configuration

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

### Operations

The template creates SSM documents that the `jd` CLI uses to manage the deployment remotely:

| Document | Purpose |
|---|---|
| `check-status-internal.sh` | Verify services are running and the certificate is available |
| `get-status.sh` | Translate status checks to human-readable output |
| `update-server.sh` | Update running services (start/stop/restart) |
| `update-allowlist.sh` | Update the allowlisted IAM role and user names |
| `get-allowlist.sh` | Retrieve the current allowlist |

### Logging

Fluent Bit collects Docker service logs and writes them to `/var/log/services` on the instance
volume. A logrotate sidecar container handles automatic rotation of all log files based on
configurable size and retention settings.

### Presets

The template provides one variable preset:
- **`defaults-all.tfvars`**: comprehensive preset with all recommended values

### Terraform Modules

| Name | Location |
|---|---|
| `ami_al2023` | `template/engine/modules/ami_al2023` |
| `ec2_iam_role` | `template/engine/modules/ec2_iam_role` |
| `ec2_instance` | `template/engine/modules/ec2_instance` |
| `network` | `template/engine/modules/network` |
| `s3_bucket` | `template/engine/modules/s3_bucket` |
| `volumes` | `template/engine/modules/volumes` |

### Inputs

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

### Outputs

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

## License

The **AWS EC2 JupyterLab Template** is licensed under the [MIT License](https://github.com/jupyter-infra/jupyter-deploy/blob/main/libs/jupyter-deploy-tf-aws-ec2-jupyterlab/LICENSE).
