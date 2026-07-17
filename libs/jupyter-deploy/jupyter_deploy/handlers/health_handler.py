from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.enum import StatusCategory
from jupyter_deploy.exceptions import CommandNotImplementedError
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.handlers.payloads import ConnectionResult, HealthLayer, HealthLayerResult, ImageVulnerability
from jupyter_deploy.handlers.project.open_handler import OpenHandler
from jupyter_deploy.handlers.resource.cluster_handler import ClusterHandler
from jupyter_deploy.handlers.resource.component_handler import ComponentHandler
from jupyter_deploy.handlers.resource.image_handler import ImageHandler

# A CRITICAL/HIGH CVE counts toward the health badge when its EPSS probability meets this
# threshold, or when EPSS is unavailable (e.g. basic registry scanning, which cannot filter).
HEALTH_EPSS_THRESHOLD = 0.10


class HealthHandler(BaseProjectHandler):
    """Handler class to orchestrate full-stack health checks."""

    _cluster_handler: ClusterHandler | None
    _component_handler: ComponentHandler | None
    _image_handler: ImageHandler | None
    _open_handler: OpenHandler | None

    def __init__(self, display_manager: DisplayManager) -> None:
        super().__init__(display_manager=display_manager)

        health_config = self.project_manifest.health
        if not health_config or not health_config.active:
            raise CommandNotImplementedError("health command is not enabled for this template")

        if self.project_manifest.has_command("cluster.status"):
            self._cluster_handler = ClusterHandler(display_manager=display_manager)
        else:
            self._cluster_handler = None

        try:
            self.project_manifest.get_components()
            self._component_handler = ComponentHandler(display_manager=display_manager)
        except CommandNotImplementedError:
            self._component_handler = None

        # Require both an images declaration and the image.status command: deployments created
        # from an older template revision may declare images without supporting status checks.
        if self.project_manifest.has_command("image.status"):
            try:
                self.project_manifest.get_images()
                self._image_handler = ImageHandler(display_manager=display_manager)
            except CommandNotImplementedError:
                self._image_handler = None
        else:
            self._image_handler = None

        if any(v.name == "open_url" for v in (self.project_manifest.values or [])):
            self._open_handler = OpenHandler()
        else:
            self._open_handler = None

    def check_all(self) -> tuple[list[HealthLayerResult], ConnectionResult]:
        """Run all health layers and return layer results + connection result."""
        results: list[HealthLayerResult] = []
        results.append(self._check_cluster())
        results.append(self._check_load_balancer())
        results.extend(self._check_components())
        results.extend(self._check_images())
        connection = self._check_connection()
        return results, connection

    def check_layer(self, layer: HealthLayer | str) -> list[HealthLayerResult]:
        """Run a single health layer by name."""
        if layer == HealthLayer.CLUSTER:
            return [self._check_cluster()]
        elif layer == HealthLayer.LOAD_BALANCER:
            return [self._check_load_balancer()]
        elif layer == HealthLayer.COMPONENTS:
            return self._check_components()
        elif layer == HealthLayer.IMAGES:
            return self._check_images()
        valid = ", ".join(h.value for h in HealthLayer)
        raise ValueError(f"Unknown health layer: '{layer}'. Valid layers: {valid}")

    def check_connection(self) -> ConnectionResult:
        """Run just the connection check."""
        return self._check_connection()

    def _check_cluster(self) -> HealthLayerResult:
        if not self._cluster_handler:
            return HealthLayerResult(
                layer=HealthLayer.CLUSTER,
                name="",
                status_category=StatusCategory.HEALTHY,
                status_text="",
                detail="",
                skipped=True,
            )
        return self._cluster_handler.health()

    def _check_components(self) -> list[HealthLayerResult]:
        if not self._component_handler:
            return [
                HealthLayerResult(
                    layer=HealthLayer.COMPONENTS,
                    name="",
                    status_category=StatusCategory.HEALTHY,
                    status_text="",
                    detail="",
                    skipped=True,
                )
            ]

        statuses = self._component_handler.get_all_status()
        results: list[HealthLayerResult] = []

        for comp in statuses:
            category = comp.status_category
            if category == StatusCategory.DEGRADED:
                status_category = StatusCategory.DEGRADED
            elif category == StatusCategory.IN_PROGRESS:
                status_category = StatusCategory.IN_PROGRESS
            else:
                status_category = StatusCategory.HEALTHY

            results.append(
                HealthLayerResult(
                    layer=HealthLayer.COMPONENTS,
                    name=comp.name,
                    status_category=status_category,
                    status_text=comp.status,
                    detail=comp.details,
                    sub_component=comp.sub_component,
                )
            )

        return results

    @staticmethod
    def _qualifies(vuln: ImageVulnerability) -> bool:
        """Return True when a CVE should count toward the health badge.

        EPSS missing (e.g. basic scanning can't filter) is treated as qualifying.
        """
        return vuln.epss_score is None or vuln.epss_score >= HEALTH_EPSS_THRESHOLD

    def _check_images(self) -> list[HealthLayerResult]:
        if not self._image_handler:
            return [
                HealthLayerResult(
                    layer=HealthLayer.IMAGES,
                    name="",
                    status_category=StatusCategory.HEALTHY,
                    status_text="",
                    detail="",
                    skipped=True,
                )
            ]

        results: list[HealthLayerResult] = []
        for name in self.project_manifest.get_images():
            try:
                status = self._image_handler.get_status(name)
            except Exception as exc:  # noqa: BLE001 - one bad image must not fail the whole check
                results.append(
                    HealthLayerResult(
                        layer=HealthLayer.IMAGES,
                        name=name,
                        status_category=StatusCategory.DEGRADED,
                        status_text="error",
                        detail=str(exc),
                    )
                )
                continue

            # Health category comes from ECR presence only; CVE counts are informational.
            category = (
                StatusCategory.HEALTHY if status.status_category == StatusCategory.HEALTHY else StatusCategory.DEGRADED
            )
            sub_component = ""
            if status.status == "Available":
                sub_component = self._summarize_vulnerabilities(name, status.latest_tag)

            results.append(
                HealthLayerResult(
                    layer=HealthLayer.IMAGES,
                    name=name,
                    status_category=category,
                    status_text=status.status,
                    detail=status.latest_tag,
                    sub_component=sub_component,
                )
            )

        return results

    def _summarize_vulnerabilities(self, name: str, tag: str) -> str:
        """Return an informational CVE-count string for the image's sub-component cell."""
        if self._image_handler is None:  # unreachable: _check_images guards this
            return ""
        try:
            vulns = self._image_handler.get_vulnerabilities(name, tag)
        except Exception as exc:  # noqa: BLE001 - fetch is best-effort; surface, but never fail the row
            return f"scan error: {exc}"

        if not vulns.last_scanned and not vulns.vulnerabilities:
            return "scan n/a"

        critical = sum(1 for v in vulns.vulnerabilities if v.severity == "CRITICAL" and self._qualifies(v))
        high = sum(1 for v in vulns.vulnerabilities if v.severity == "HIGH" and self._qualifies(v))
        if not critical and not high:
            return ""
        return f"{critical} critical, {high} high"

    def _check_load_balancer(self) -> HealthLayerResult:
        if not self._cluster_handler or not self.project_manifest.has_command("cluster.loadbalancer.health"):
            return HealthLayerResult(
                layer=HealthLayer.LOAD_BALANCER,
                name="",
                status_category=StatusCategory.HEALTHY,
                status_text="",
                detail="",
                skipped=True,
            )
        return self._cluster_handler.get_load_balancer_health()

    def _check_connection(self) -> ConnectionResult:
        if not self._open_handler:
            return ConnectionResult(
                status_category=StatusCategory.HEALTHY,
                detail="",
                skipped=True,
            )

        health_config = self.project_manifest.health
        expected_status_code = health_config.expected_status_code if health_config else 200
        port = health_config.load_balancer_port if health_config else 443

        result = self._open_handler.health(expected_status_code=expected_status_code, port=port)

        if result.healthy:
            return ConnectionResult(
                status_category=StatusCategory.HEALTHY,
                detail=result.detail,
            )
        return ConnectionResult(
            status_category=StatusCategory.DEGRADED,
            detail=result.detail,
        )
