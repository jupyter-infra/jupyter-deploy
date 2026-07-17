from dataclasses import dataclass, field
from typing import Any

from kubernetes.client import ApiextensionsV1Api, V1CustomResourceDefinition


@dataclass(frozen=True)
class CrdInfo:
    """Typed detail for a CustomResourceDefinition.

    `resource` is the full serialized object, kept so manifest display fields
    that reference arbitrary paths (e.g. .spec.versions[0].name) keep working.
    The typed fields expose the introspection that the generic custom-object
    path could only reach stringly (established condition, served versions).
    """

    name: str
    group: str
    established: bool
    served_versions: list[str] = field(default_factory=list)
    stored_version: str = ""
    resource: dict[str, Any] = field(default_factory=dict)


def _is_established(crd: V1CustomResourceDefinition) -> bool:
    status = crd.status
    conditions = status.conditions if status else None
    if not conditions:
        return False
    for condition in conditions:
        if getattr(condition, "type", "") == "Established":
            return getattr(condition, "status", "") == "True"
    return False


def get_crd(api: ApiextensionsV1Api, name: str) -> CrdInfo:
    """Read a CustomResourceDefinition by name, return typed detail plus the full resource."""
    crd = api.read_custom_resource_definition(name=name)
    crd_name = crd.metadata.name if crd.metadata else ""
    spec = crd.spec
    group = spec.group if spec else ""
    versions = spec.versions if spec and spec.versions else []
    served_versions = [v.name for v in versions if getattr(v, "served", False)]
    stored_version = next((v.name for v in versions if getattr(v, "storage", False)), "")
    resource: dict[str, Any] = api.api_client.sanitize_for_serialization(crd)
    return CrdInfo(
        name=crd_name,
        group=group,
        established=_is_established(crd),
        served_versions=served_versions,
        stored_version=stored_version,
        resource=resource,
    )
