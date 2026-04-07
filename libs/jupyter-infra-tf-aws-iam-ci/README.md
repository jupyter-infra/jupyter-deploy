# Jupyter Deploy AWS IAM CI template

The Jupyter Deploy AWS IAM CI template is an open-source infrastructure template that manages
AWS resources needed by the E2E CI pipeline for [jupyter-deploy](https://github.com/jupyter-infra/jupyter-deploy).
It uses Terraform as the infrastructure-as-code engine and creates IAM roles for GitHub Actions OIDC federation,
Secrets Manager secrets for sensitive CI data, and SSM parameters for non-secret configuration.

This template creates two IAM roles (E2E and release), each scoped to a specific GitHub Actions environment
via OIDC trust policies. The roles are hardened with deny statements that prevent self-modification
and secret policy editing. Secrets are protected with resource-based policies that restrict write access
to maintainer roles.

## Prerequisites
- an AWS account with permissions to create IAM and Secrets Manager resources
- a GitHub repository with Actions environments (`e2e` and `release`)
- one or more GitHub OAuth apps for E2E testing (up to 5)
- a GitHub bot account for automated testing

## Usage
This terraform project is meant to be used with the [jupyter-deploy](https://github.com/jupyter-infra/jupyter-deploy/tree/main/libs/jupyter-deploy) CLI.

### Installation (with pip):
Recommended: create or activate a python virtual environment.

```bash
pip install jupyter-deploy[aws]
pip install jupyter-infra-tf-aws-iam-ci
```

### Project setup
```bash
mkdir my-ci-infra
cd my-ci-infra

jd init . -P aws -I iam -T ci
```

### Configure and create the infrastructure
```bash
jd config
jd up
```

### Inspect outputs
```bash
# View all outputs
jd show --outputs --list

# Get specific values
jd show -o e2e_iam_role_arn --text
jd show -o auth_state_secret_arn --text
```

### Take down all the infrastructure
This operation removes all the resources associated with this project in your AWS account.

```bash
jd down
```

## Details
This project:
- creates an IAM OIDC provider for GitHub Actions (`token.actions.githubusercontent.com`)
- creates two IAM roles with OIDC trust policies scoped to specific GitHub Actions environments:
    - `<prefix>-e2e-<deployment_id>` for E2E test workflows (environment: `e2e`)
    - `<prefix>-release-<deployment_id>` for release workflows (environment: `release`)
- attaches managed policies (default: `AdministratorAccess`) to each role
- hardens each role with deny statements preventing self-modification (attach/detach/put/delete policies, update trust)
- hardens each role with deny statements preventing secret resource policy editing
- creates a Secrets Manager secret for Playwright auth state (read/write by CI roles, no initial value)
- creates Secrets Manager secrets for the GitHub bot account password and recovery codes (maintainer-only access)
- creates an SSM parameter for the GitHub bot account email (read-only by CI roles)
- creates 5 SSM parameters for OAuth app client IDs (read-only by CI roles)
- creates 5 Secrets Manager secrets for OAuth app client secrets (read-only by CI roles)
- seeds secret values via `local-exec` provisioner to keep them out of Terraform state
- applies resource-based deny policies on OAuth client secrets (deny write except maintainers)
- applies resource-based deny policies on bot account secrets (deny all except maintainers)
- tags all resources with `Source`, `Template`, `Version`, and `DeploymentId`

## Requirements
| Name | Version |
|---|---|
| terraform | >= 1.0 |
| aws | ~> 5.0 |

## Providers
| Name | Version |
|---|---|
| aws | ~> 5.0 |

## Modules
| Name | Location |
|---|---|
| `iam_role` | `template/engine/modules/iam_role` |
| `secret` | `template/engine/modules/secret` |
| `ssm_parameter` | `template/engine/modules/ssm_parameter` |

## Resources
| Name | Type |
|---|---|
| [aws_iam_openid_connect_provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_openid_connect_provider) | resource |
| [aws_iam_role](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role_policy](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy_attachment](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_secretsmanager_secret](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/secretsmanager_secret) | resource |
| [aws_secretsmanager_secret_policy](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/secretsmanager_secret_policy) | resource |
| [aws_ssm_parameter](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ssm_parameter) | resource |
| [null_resource](https://registry.terraform.io/providers/hashicorp/null/latest/docs/resources/resource) | resource |
| [aws_caller_identity](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/caller_identity) | data source |
| [aws_partition](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/partition) | data source |
| [aws_region](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/region) | data source |

## Inputs
| Name | Type | Default | Description |
|---|---|---|---|
| region | `string` | `us-east-1` | The AWS region where CI resources are deployed |
| github_org | `string` | Required | GitHub organization name for the OIDC trust policy |
| github_repo | `string` | Required | GitHub repository name for the OIDC trust policy |
| secret_name_prefix | `string` | `jupyter-infra-ci` | Naming prefix for all secrets and SSM parameters |
| github_ci_iam_roles_prefix | `string` | `jupyter-infra-ci` | Prefix for the GitHub Actions CI IAM role names |
| iam_managed_policies_e2e | `list(string)` | `["AdministratorAccess"]` | AWS managed policy names to attach to the E2E role |
| iam_managed_policies_release | `list(string)` | `["AdministratorAccess"]` | AWS managed policy names to attach to the release role |
| maintainer_roles | `list(string)` | `["Admin"]` | IAM role names that may manage all secrets |
| github_bot_account_email | `string` | Required | Email address of the GitHub bot account (stored in SSM Parameter Store) |
| github_bot_account_password | `string` | Required (sensitive) | Password for the GitHub bot account |
| github_bot_account_recovery_codes | `string` | Required (sensitive) | Recovery codes for the GitHub bot account |
| github_bot_account_totp_secret | `string` | Required (sensitive) | TOTP seed (base32) for the GitHub bot account 2FA |
| github_oauth_app_1..5 | `map(string)` | Required | OAuth app metadata: client_id, app_id, app_url, callback_url |
| github_oauth_app_client_secret_1..5 | `string` | Required (sensitive) | GitHub OAuth app client secrets |

## Outputs
| Name | Description |
|---|---|
| `deployment_id` | Unique identifier for this deployment |
| `region` | Name of the AWS region where the resources are deployed |
| `e2e_iam_role_arn` | ARN of the IAM role for E2E test workflows |
| `release_iam_role_arn` | ARN of the IAM role for release workflows |
| `auth_state_secret_arn` | ARN of the Secrets Manager secret for Playwright auth state |
| `github_bot_account_password_secret_arn` | ARN of the secret for GitHub bot account password |
| `github_bot_account_recovery_codes_secret_arn` | ARN of the secret for GitHub bot account recovery codes |
| `github_bot_account_totp_secret_secret_arn` | ARN of the secret for GitHub bot account TOTP seed |
| `github_bot_account_email_arn` | ARN of the SSM parameter for GitHub bot account email |
| `github_oauth_app_client_id_1..5_arn` | ARNs of the SSM parameters for OAuth app client IDs |
| `github_oauth_app_client_secret_1..5_arn` | ARNs of the secrets for OAuth app client secrets |

## License

The Jupyter Deploy AWS IAM CI template is licensed under the [MIT License](LICENSE).
