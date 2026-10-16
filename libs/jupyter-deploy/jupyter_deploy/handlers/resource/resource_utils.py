import contextlib
import json
import re
from typing import Any

from jupyter_deploy.manifest import JupyterDeployDisplayFieldV1, JupyterDeployStatusRuleV1
from jupyter_deploy.provider import manifest_command_runner as cmd_runner


def _resolve_display_field(resource: dict[str, Any], field: JupyterDeployDisplayFieldV1) -> str | None:
    """Resolve one display field to a string, or None when the value is absent and unlabeled.

    A labeled field always renders its label, falling back to '<label>: -' when the value is
    absent (missing/typo'd path), so the cell stays self-documenting rather than going blank.
    """
    if field.count is not None:
        node = resolve_node(resource, field.count)
        value: str | None = str(len(node)) if isinstance(node, list) else None
    elif field.join is not None:
        parts = [resolve_node(resource, p) for p in field.join]
        value = field.separator.join(str(p) for p in parts) if all(p is not None for p in parts) else None
    elif field.path is not None:
        node = resolve_node(resource, field.path)
        value = str(node) if node is not None else None
    else:
        value = None

    if field.label:
        return f"{field.label}: {value if value is not None else '-'}"
    return value


def render_display_field(resource_json: str, field: JupyterDeployDisplayFieldV1) -> str:
    """Render a single display field to a string from a resource's JSON.

    Returns '' when the source value is absent or the input is unparseable.
    """
    try:
        resource = json.loads(resource_json)
    except (json.JSONDecodeError, TypeError):
        return ""
    if not isinstance(resource, dict):
        return ""
    return _resolve_display_field(resource, field) or ""


_ARRAY_FILTER_RE = re.compile(r"^([^\[]+)\[([^=]+)=([^\]]+)\]$")
_INDEX_RE = re.compile(r"^([^\[]+)\[(\d+)\]$")
_MAP_KEY_RE = re.compile(r"^([^\[]+)\[([^\]]+)\]$")


def _split_segments(path: str) -> list[str]:
    """Split a dotted path on '.', but never inside [...] (label keys contain dots and slashes)."""
    segments: list[str] = []
    current = ""
    depth = 0
    for ch in path:
        if ch == "[":
            depth += 1
            current += ch
        elif ch == "]":
            depth -= 1
            current += ch
        elif ch == "." and depth == 0:
            if current:
                segments.append(current)
            current = ""
        else:
            current += ch
    if current:
        segments.append(current)
    return segments


def resolve_node(resource: dict[str, Any], path: str) -> Any:
    """Resolve a dotted path against a resource dict, returning the raw node (any type) or None.

    Supports four segment forms:
      - Simple key: .spec.desiredStatus
      - Array filter: .status.conditions[type=Degraded].status
      - List index: .spec.versions[0].name
      - Map-key lookup: .metadata.labels[workspace.jupyter.org/default-template]
        (use brackets for keys that contain dots or slashes)
    """
    segments = _split_segments(path)
    current: Any = resource
    for segment in segments:
        filter_match = _ARRAY_FILTER_RE.match(segment)
        index_match = _INDEX_RE.match(segment)
        map_key_match = _MAP_KEY_RE.match(segment)
        if filter_match:
            array_key, filter_key, filter_val = filter_match.group(1), filter_match.group(2), filter_match.group(3)
            items = current.get(array_key) if isinstance(current, dict) else None
            if not isinstance(items, list):
                return None
            current = next(
                (item for item in items if isinstance(item, dict) and item.get(filter_key) == filter_val), None
            )
        elif index_match:
            list_key, index = index_match.group(1), int(index_match.group(2))
            items = current.get(list_key) if isinstance(current, dict) else None
            if not isinstance(items, list) or index >= len(items):
                return None
            current = items[index]
        elif map_key_match:
            map_key, lookup_key = map_key_match.group(1), map_key_match.group(2)
            container = current.get(map_key) if isinstance(current, dict) else None
            if not isinstance(container, dict):
                return None
            current = container.get(lookup_key)
        else:
            current = current.get(segment) if isinstance(current, dict) else None
        if current is None:
            return None
    return current


def resolve_path(resource: dict[str, Any], path: str) -> str | None:
    """Resolve a dotted path against a resource dict, returning a string leaf or None."""
    value = resolve_node(resource, path)
    return value if isinstance(value, str) else None


def evaluate_status_rules(resource_json: str, rules: list[JupyterDeployStatusRuleV1]) -> str:
    try:
        resource = json.loads(resource_json)
    except (json.JSONDecodeError, TypeError):
        return "Unknown"

    if not isinstance(resource, dict):
        return "Unknown"

    for rule in rules:
        if all(resolve_path(resource, m.path) == m.equals for m in rule.all):
            return rule.display

    return "Unknown"


def collect_results(
    runner: cmd_runner.ManifestCommandRunner,
    command: cmd_runner.JupyterDeployCommandV1,
) -> dict[str, Any]:
    """Collect all results from a command, stripping the command prefix from keys.

    JSON string values are parsed into dicts/lists so callers get structured data.
    """
    prefix = f"{command.cmd}."
    result: dict[str, Any] = {}
    for result_def in command.results or []:
        key = result_def.result_name.removeprefix(prefix)
        value: Any = runner.get_result_value_with_fallback(command, result_def.result_name, str, "")
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            value = json.loads(value)
        result[key] = value
    return result
