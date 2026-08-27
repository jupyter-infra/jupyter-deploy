"""AWS EC2 JupyterLab Terraform template for jupyter-deploy.

Single-user JupyterLab on a remote EC2 instance, reached from the laptop through the
local client proxy over pinned self-signed TLS with AWS-identity (STS) authentication.
AWS credentials are the only prerequisite.
"""

__version__ = "0.1.0"
