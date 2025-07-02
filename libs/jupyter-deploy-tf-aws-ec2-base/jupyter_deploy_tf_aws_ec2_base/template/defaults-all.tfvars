# defaults.tfvars
region                   = "us-west-2"
instance_type            = "t3.medium"
key_pair_name            = null
ami_id                   = null
volume_size_gb           = 30
volume_type              = "gp3"
iam_role_prefix          = "Jupyter-deploy-ec2-base"
oauth_provider           = "github"
oauth_app_secret_prefix  = "Jupyter-deploy-ec2-base"
logs_rotation_size_mb    = 50
max_log_files_count      = 180
log_files_retention_days = 180
custom_tags              = {}
