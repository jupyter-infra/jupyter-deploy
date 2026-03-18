"""CI infrastructure template for jupyter-deploy.

Manages AWS resources needed by CI: IAM OIDC provider, CI role,
and Secrets Manager secrets for auth state, OAuth app, and GitHub account.
"""

__version__ = "0.1.0"
