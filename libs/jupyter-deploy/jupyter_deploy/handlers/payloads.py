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
class PoolDetail:
    """Result of jd pool show."""

    name: str = ""
    status: str = ""
    resource: dict[str, Any] = field(default_factory=dict)


@dataclass
class ServerDetail:
    """Result of jd server show."""

    name: str = ""
    resource: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProxyConnectBundle:
    """The connect-info bundle emitted to the client proxy on stdout.

    Field names and shape are the proxy's exec-credential contract
    (`jupyter_deploy_client_proxy.credentials.bundle.ConnectBundle`): the proxy dials
    `host:port`, pins `ca_cert`, injects `headers` verbatim on every request, and re-execs
    the token command on a margin before `expires_at`. `headers` is opaque here — the
    handler never interprets it.
    """

    host: str
    port: int
    ca_cert: str
    headers: dict[str, str] = field(default_factory=dict)
    expires_at: str = ""


@dataclass
class ProxyStatus:
    """Detail of a single proxy instance, as observed on disk (jd proxy show).

    `alive` is the live PID probe; `running` is `alive` AND a non-terminal published state.
    `started_at` is the launch timestamp (its runtime directory name); `log_dir` is where
    its console + rotating logs live.
    """

    state: str
    pid: int
    alive: bool
    port: int | None = None
    expires_at: str | None = None
    running: bool = False
    started_at: str = ""
    log_dir: str = ""
    # Process creation time (epoch seconds) recorded by the proxy; used to guard against
    # signaling a recycled PID. None when read from a status file that predates the field.
    process_created_at: float | None = None
