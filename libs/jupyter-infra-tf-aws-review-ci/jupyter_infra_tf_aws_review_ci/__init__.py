"""Review CI infrastructure template for jupyter-deploy.

Manages AWS resources for automated roborev PR reviews: IAM OIDC provider,
an ECR repository for the review image, and two IAM roles (publish, run)
scoped to GitHub Actions environments.
"""

__version__ = "0.1.0"
