"""Template utilities for jupyter-deploy."""

import importlib.metadata
import logging
from pathlib import Path

from jupyter_deploy.engine.enum import EngineType

logger = logging.getLogger(__name__)

TEMPLATE_ENTRY_POINTS = {engine_type: f"jupyter_deploy.{engine_type.value}_templates" for engine_type in EngineType}

TEMPLATES: dict[str, dict[str, Path]] = {engine: {} for engine in TEMPLATE_ENTRY_POINTS}


def get_templates(engine: EngineType) -> dict[str, Path]:
    """Get all registered templates for a specific engine from entry points.

    Args:
        engine: The engine type (e.g., "terraform")

    Returns:
        Dict[str, Path]: A dictionary mapping template names to their paths.
    """
    templates: dict[str, Path] = {}

    if engine not in TEMPLATE_ENTRY_POINTS:
        logger.warning(f"No entry point defined for engine: {engine}")
        return templates

    entry_point_group = TEMPLATE_ENTRY_POINTS[engine]

    for entry_point in importlib.metadata.entry_points(group=entry_point_group):
        template_path = entry_point.load()
        if isinstance(template_path, Path) and template_path.exists():
            # Convert entry point name to template format, ex. aws_ec2_some-name -> aws:ec2:some_name
            template_name = entry_point.name.replace("_", ":")
            templates[template_name] = template_path
            logger.debug(f"Loaded {engine} template {template_name} from {template_path}")
        else:
            logger.warning(f"Template path for {entry_point.name} is not a valid Path or does not exist")

    return templates


for engine in TEMPLATE_ENTRY_POINTS:
    TEMPLATES[engine] = get_templates(engine)
