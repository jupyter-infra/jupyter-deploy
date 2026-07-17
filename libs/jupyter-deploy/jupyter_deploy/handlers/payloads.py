from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from jupyter_deploy.enum import StatusCategory


class HealthLayer(str, Enum):
    """Layers checked by the health command."""

    CLUSTER = "cluster"
    LOAD_BALANCER = "load-balancer"
    COMPONENTS = "components"
    IMAGES = "images"


@dataclass
class HealthLayerResult:
    """Single row in the health check output table."""

    layer: HealthLayer
    name: str
    status_category: StatusCategory
    status_text: str
    detail: str
    sub_component: str = ""
    skipped: bool = False


@dataclass
class ConnectionResult:
    """Result of the end-to-end connection check."""

    status_category: StatusCategory
    detail: str
    skipped: bool = False


@dataclass
class ImageInfo:
    """Entry in the image list."""

    name: str
    description: str


@dataclass
class ImageDetail:
    """Result of jd image show."""

    name: str
    tag: str
    repository_uri: str
    scanner_type: str
    last_scanned: str
    scan_status: str


@dataclass
class ImageTag:
    """Single tag entry for an image."""

    tag: str
    pushed_at: str
    digest: str


@dataclass
class ImageStatusResult:
    """Result of jd image status: whether the image is present in ECR."""

    name: str
    status: str
    status_category: str
    latest_tag: str


@dataclass
class ImageVulnerability:
    """Single vulnerability entry."""

    cve: str
    type: str
    package: str
    severity: str
    installed_version: str
    fixed_version: str
    score: float
    epss_score: float | None = None


@dataclass
class ImageVulnerabilitiesResult:
    """Result of jd image vulnerabilities."""

    name: str
    tag: str
    last_scanned: str
    scanner_type: str
    critical_count: int
    high_count: int
    vulnerabilities: list[ImageVulnerability]


@dataclass
class ClusterDetail:
    """Result of jd cluster show."""

    name: str = ""
    label: str = ""
    status: str = ""
    endpoint: str = ""
    version: str = ""


@dataclass
class ComponentInfo:
    """Entry in the component list.

    `type` is the display type (type-display when set, else the internal type).
    """

    name: str
    type: str
    description: str


@dataclass
class ComponentStatus:
    """Status of a single component for dashboard display."""

    name: str
    type: str
    status: str
    status_category: str
    details: str
    sub_component: str


@dataclass
class ComponentDetail:
    """Result of jd component show."""

    name: str = ""
    resource: dict[str, Any] = field(default_factory=dict)


@dataclass
class HostDetail:
    """Result of jd host show."""

    name: str = ""
    status: str = ""
    resource: dict[str, Any] = field(default_factory=dict)


@dataclass
class ServerDetail:
    """Result of jd server show."""

    name: str = ""
    resource: dict[str, Any] = field(default_factory=dict)
