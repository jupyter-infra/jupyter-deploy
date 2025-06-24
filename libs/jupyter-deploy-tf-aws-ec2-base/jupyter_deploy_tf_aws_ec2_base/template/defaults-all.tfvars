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
custom_tags             = {}