"""Template path provider for the AWS EC2 ngrok template."""

from pathlib import Path

# Path to the template files
TEMPLATE_PATH = Path(__file__).resolve().parent / "template"
