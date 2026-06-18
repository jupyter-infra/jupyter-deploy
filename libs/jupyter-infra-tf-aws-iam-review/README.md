# Jupyter Deploy AWS Review CI template

The Jupyter Deploy AWS Review CI template is an open-source infrastructure template that manages
the AWS resources needed for automated roborev PR reviews in GitHub Actions, for repositories in
the [jupyter-infra](https://github.com/jupyter-infra) organization. It uses Terraform as the
infrastructure-as-code engine and creates an IAM OIDC provider for GitHub Actions federation, an
ECR repository for the pre-built review image, and two IAM roles scoped to GitHub Actions
environments.

This template creates two roles, each scoped to the `review` GitHub Actions environment via OIDC
trust policies. The publish role (for the repository that builds the image) can push to the review
ECR repository. The run role (for consumer repositories) can pull the review image and invoke the
configured Bedrock models, and nothing else. Both roles are hardened with deny statements that
prevent self-modification.

## Prerequisites
- an AWS account with permissions to create IAM and ECR resources
- Bedrock model access enabled for the Anthropic models in the target region
- GitHub repositories with a `review` Actions environment

## Usage
This terraform project is meant to be used with the [jupyter-deploy](https://github.com/jupyter-infra/jupyter-deploy/tree/main/libs/jupyter-deploy) CLI.

### Installation (with pip):
Recommended: create or activate a python virtual environment.

```bash
pip install "jupyter-deploy[aws]"
pip install jupyter-infra-tf-aws-iam-review
```

### Project setup
```bash
mkdir review-ci
cd review-ci

jd init . -P aws -I iam -T review
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
jd show -o review_run_iam_role_arn --text
jd show -o review_image_repository_url --text
```

### Take down all the infrastructure
```bash
jd down
```

## Details
This project:
- creates an IAM OIDC provider for GitHub Actions (`token.actions.githubusercontent.com`), or
  references an existing one when `create_oidc_provider` is false
- creates an ECR repository for the review image (`<resource_name_prefix>-<deployment_id>/review`)
- creates two IAM roles with OIDC trust policies scoped to the `review` GitHub Actions environment:
    - `<iam_roles_prefix>-publish-<deployment_id>` for the publishing repo, with ECR push
    - `<iam_roles_prefix>-run-<deployment_id>` for consumer repos, with ECR pull and Bedrock invoke
- hardens each role with deny statements preventing self-modification (attach/detach/put/delete policies, update trust)
