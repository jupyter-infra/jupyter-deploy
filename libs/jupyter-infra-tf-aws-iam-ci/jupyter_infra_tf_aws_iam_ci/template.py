"""Template path provider for the CI infrastructure template."""

from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent / "template"
