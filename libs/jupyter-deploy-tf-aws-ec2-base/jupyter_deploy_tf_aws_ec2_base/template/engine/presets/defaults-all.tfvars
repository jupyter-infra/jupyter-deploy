# defaults.tfvars
region                     = "us-west-2"
jupyter_package_manager    = "uv"
instance_type              = "t3.medium"
key_pair_name              = null
ami_id                     = null
min_root_volume_size_gb    = 30
volume_size_gb             = 30
volume_type                = "gp3"
iam_role_prefix            = "Jupyter-deploy-ec2-base"
oauth_provider             = "github"
oauth_app_secret_prefix    = "Jupyter-deploy-ec2-base"
log_files_rotation_size_mb = 50
log_files_retention_count  = 10
log_files_retention_days   = 180
custom_tags                = {}
additional_ebs_mounts      = []
additional_efs_mounts      = []
