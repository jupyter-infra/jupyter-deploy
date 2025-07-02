# defaults.tfvars
region                  = "us-west-2"
instance_type           = "t3.medium"
key_pair_name           = null
ami_id                  = null
volume_size_gb          = 30
volume_type             = "gp3"
iam_role_prefix         = "Jupyter-deploy-ec2-base"
oauth_provider          = "github"
oauth_app_secret_prefix = "Jupyter-deploy-ec2-base"
traefik_logs_rotation_size = 50
traefik_logs_rotation_interval = "daily"
traefik_logs_max_count = 180
traefik_logs_max_age = 180
custom_tags             = {}