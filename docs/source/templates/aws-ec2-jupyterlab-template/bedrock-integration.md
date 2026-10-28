# Bedrock Integration

The Jupyter image ships the **Claude Code** (`claude`) and **Codex** (`codex`) coding agents, pinned
to the versions in `claude_code_version` and `codex_version`. Their system configuration points
them at Amazon Bedrock, and `bedrock_enabled` is `true` by default, so both work in a **JupyterLab**
terminal with no setup: run `claude` or `codex`.

## How it works

The deployment creates two IAM roles. The instance role runs the host: SSM, the deployment S3
bucket, the certificate-pin parameter. The `bedrock-app` role has a single policy attached, which
allows Bedrock inference on the models matching `bedrock_model_patterns` through the inference
profiles that `bedrock_inference_scope` selects. Its trust policy names the instance role as the
only principal that may assume it.

A `bedrock-sidecar` container (the AWS CLI image and a shell loop) assumes the `bedrock-app` role
from the instance role every 15 minutes and writes the credentials atomically to a docker volume.
Role chaining caps each session at one hour, so a sidecar that stops refreshing turns unhealthy
long before the credentials expire. The `jupyter` container mounts the volume read-only at
`/run/bedrock-creds/credentials.json` and reads it through `credential_process` in `/etc/aws/config`.

The `jupyter` container runs on its own docker network. A `DOCKER-USER` firewall rule on the host,
re-applied on every docker start, drops its traffic to the instance metadata service, and
`AWS_EC2_METADATA_DISABLED` makes the AWS SDKs fail fast rather than probe it. Code in the
container therefore holds the `bedrock-app` credentials and never the instance role's. The instance
keeps IMDSv2 with a hop limit of 2 so that the sidecar, one docker-bridge hop away, can still read
the instance role credentials. A container holding `/var/run/docker.sock` can bypass the firewall
rule; that is tracked separately.

### AWS credentials in notebooks

`boto3` and the AWS CLI inside the Jupyter container default to the `bedrock-app` role, which can
only invoke Bedrock models. A notebook that relied on the instance role's permissions, for example
to read the deployment S3 bucket, no longer has them.

## Enable the models in your account

Bedrock enables a third-party model (Anthropic Claude, OpenAI GPT) on its first invocation in an
AWS account, by subscribing the account through AWS Marketplace. This is a one-time operation
in your AWS account.

```{warning}
The `bedrock-app` role holds no AWS Marketplace permissions, so an admin must make that first call for each model.
A call from the agents fails with `AccessDeniedException` until then.
```

Invoking a third-party model accepts the provider's EULA: review the terms first. Then, with a
principal allowed to subscribe through AWS Marketplace, in the deployment's region:

1. **Anthropic only**: submit the first-time-use form. Open any Anthropic model in the
   Bedrock console model catalog and submit your use case details. You submit it once per
   AWS Organization.
2. **Each model**: open the model in the Bedrock console playground and send one prompt.
3. **Wait**: the agreement can take up to 15 minutes to become available.

## Choose the inference scope

The agents call Bedrock in the deployment region through cross-region inference profiles.
`bedrock_inference_scope` selects which ones:

| Scope | Profiles | Where Bedrock serves requests |
|---|---|---|
| `geo` (default) | the region's geography, e.g. `us.` in `us-west-2` | within that geography |
| `global` | `global.` | any commercial region |

The `geo` prefix follows the deployment region:

| Region | Prefix |
|---|---|
| `us-*`, `ca-central-1` | `us.` |
| `eu-*` | `eu.` |
| `ap-northeast-1`, `ap-northeast-3` | `jp.` |
| `ap-southeast-2` | `au.` |
| `us-gov-*` | `us-gov.` |
| other regions | none: use `global` |

Bedrock offers the OpenAI models through `us.` and `global.` profiles only. Outside the US,
**Codex** needs `global`.

## Choose the models

`bedrock_model_patterns` lists the Bedrock model IDs the `bedrock-app` role may invoke, as IAM
wildcards without the inference profile prefix. The default allows both agents:

```yaml
overrides:
  bedrock_model_patterns:
    - anthropic.claude-*
    - openai.gpt-*
```

Each agent picks its default model per release: **Claude Code**'s default must stay within the
patterns, and **Codex** uses the best model its release offers among the allowed ones. **Codex**
needs an `openai.*` pattern and a `us.` or `global.` prefix; otherwise the image build leaves its
model unset and `codex` reports why.

## Pin the agent versions

`claude_code_version` and `codex_version` pin the agents installed in the Jupyter image. Changing
either one rebuilds the image on the next `jd up`.

## Turn it off

Set `bedrock_enabled` to `false` in the `overrides:` section of `variables.yaml`, then run
`jd config` and `jd up`:

```yaml
overrides:
  bedrock_enabled: false
```

The deployment then has no `bedrock-app` role, no `bedrock-sidecar` and no credentials file. The
agents stay installed but fail: `claude` with a credentials error, `codex` reporting the model
`unset: bedrock_enabled is false ...`. Set the variable back to `true` and apply again to restore them.

## Troubleshooting

- **`jd server status` reports `OUT_OF_SERVICE`**: the `bedrock-sidecar` container is down or
  unhealthy. Read its logs with `jd server logs -s bedrock-sidecar`.
- **`Unable to locate credentials`, or no `/run/bedrock-creds/credentials.json`**: the sidecar has
  not published credentials yet, or `bedrock_enabled` is `false`.
- **`AccessDeniedException` naming a model or inference profile**: the model is outside
  `bedrock_model_patterns`, or its inference profile is outside `bedrock_inference_scope`
  (**Codex** outside the US needs `global`).
- **`AccessDeniedException` on a model the patterns allow**: the model was never enabled in the
  account and region; see [Enable the models in your account](#enable-the-models-in-your-account).
