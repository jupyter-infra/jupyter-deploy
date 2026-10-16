from dataclasses import asdict, dataclass, field
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


@dataclass
class ResolvedVolume:
    """One volume, resolved from its manifest declaration plus the values that declaration points at."""

    name: str
    volume_id: str
    mount_point: str
    description: str
    backups_map: str
    # The class of storage the manifest declares (`ebs`, `efs`). Not `volume_type`: the providers use that
    # for something else entirely -- the tier WITHIN a class (`gp3`, `generalPurpose`) -- and the two sat
    # under the same name in two payloads before this.
    volume_class: str = ""

    @property
    def backup_eligible(self) -> bool:
        """True when this volume both has an identity and declares where its backups are recorded.

        Two independent reasons a volume may not be: it is only *referenced* by the template (no
        identity, never recreated, so nothing to restore into), or its kind has no backup mechanism
        (no backups-map declared).
        """
        return bool(self.name) and bool(self.backups_map)


@dataclass
class VolumeInfo:
    """Entry in the volume list, shaped like `ComponentInfo`.

    `volume_class` is the class of storage the manifest declares (`ebs`, `efs`). It earns a column because
    it is not cosmetic: it is what decides whether the volume can be backed up at all, so a list of bare
    names would hide the single most consequential difference between two entries.

    Named `volume_class` rather than `type` as in `ComponentInfo`: a volume also carries a provider-assigned
    volume TYPE (`gp3`), so `type` here would collide with that on the very next command. Rendered under the
    shorter header `Class`, which is unambiguous in a table of volumes.
    """

    name: str
    volume_class: str
    description: str


@dataclass
class VolumeDetail:
    """Result of jd volume show.

    Declared fields (name, mount_point, description) come from the template's manifest; the rest is live
    provider state, so they are empty when a volume is configured but the project is not applied yet.
    """

    name: str
    volume_id: str
    mount_point: str
    description: str
    zone: str
    capacity: str | None
    # Two fields, two facts, deliberately not merged into one label. `volume_class` is what the manifest
    # declares (`ebs`, `efs`) -- the same value `jd volume list` prints, and the one that decides whether the
    # volume can be backed up. `volume_type` is the provider's own tier WITHIN that class (`gp3`,
    # `generalPurpose`), which means nothing without knowing the class; AWS calls gp3 a "volume type", so
    # that name is theirs, not ours. Reporting "Elastic Block Store (gp3)" in one field instead would read
    # well and compare badly: `show` has no rendering other than its JSON, so a caller filtering on either
    # fact would have to parse a sentence to get it.
    volume_class: str
    volume_type: str
    encrypted: bool
    backup_id: str
    backup_state: str | None
    backup_timestamp: str | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize, dropping every field that has nothing to report.

        Three fields are `None`-able rather than "", and the distinction is the same in all three: "" is
        a value the provider gave, `None` means there is no such value to give. `capacity` absent means
        no size was reported -- which is not a size of zero, and not the same as a kind that has no fixed
        size and says so in words (`elastic`). `backup_state` and `backup_timestamp` are absent when there
        is no backup to describe, because a state of "" reads as a backup in an unknown condition.
        """
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass
class VolumeBackupResult:
    """Result of backing up one volume."""

    name: str
    volume_id: str
    backup_id: str
    state: str
    superseded_backup_ids: list[str]
