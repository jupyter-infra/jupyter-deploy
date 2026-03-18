region                       = "us-east-1"
secret_name_prefix           = "jupyter-infra-ci"
github_ci_iam_roles_prefix   = "jupyter-infra-ci"
create_oidc_provider         = true
iam_managed_policies_e2e     = ["AdministratorAccess"]
iam_managed_policies_release = ["AdministratorAccess"]
maintainer_roles             = ["Admin"]
