from typing import Any

from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.exceptions import ImageTagNotFoundError, ResourceNameRequiredError
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.handlers.payloads import (
    ImageDetail,
    ImageInfo,
    ImageStatusResult,
    ImageTag,
    ImageVulnerabilitiesResult,
    ImageVulnerability,
)
from jupyter_deploy.handlers.resource.resource_utils import collect_results
from jupyter_deploy.manifest import JupyterDeployImageDefinitionV1
from jupyter_deploy.provider import manifest_command_runner as cmd_runner
from jupyter_deploy.provider.resolved_clidefs import ResolvedCliParameter, StrResolvedCliParameter


class ImageHandler(BaseProjectHandler):
    """Handler class to interact with application images."""

    _output_handler: EngineOutputsHandler

    def __init__(self, display_manager: DisplayManager) -> None:
        super().__init__(display_manager=display_manager)

        if self.engine == EngineType.TERRAFORM:
            self._output_handler = tf_outputs.TerraformOutputsHandler(
                project_path=self.project_path, project_manifest=self.project_manifest
            )
            self._variable_handler = tf_variables.TerraformVariablesHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
                display_manager=self.display_manager,
            )
        else:
            raise NotImplementedError(f"OutputsHandler implementation not found for engine: {self.engine}")

    def _resolve_output(self, output_key: str) -> str:
        output_defs = self._output_handler.get_full_project_outputs()
        if output_key not in output_defs:
            raise KeyError(f"Output '{output_key}' not found for image resolution")
        output_def = output_defs[output_key]
        if isinstance(output_def, StrTemplateOutputDefinition) and output_def.value:
            return output_def.value
        raise ValueError(f"Output '{output_key}' is not resolved")

    def _resolve_image_outputs(self, image_def: JupyterDeployImageDefinitionV1) -> tuple[str, str]:
        repository_name = self._resolve_output(image_def.repository_output)
        tag = self._resolve_output(image_def.tag_output)
        return repository_name, tag

    def _build_cli_paramdefs(
        self,
        repository_name: str,
        image_tag: str,
    ) -> dict[str, ResolvedCliParameter[Any]]:
        return {
            "repository_name": StrResolvedCliParameter(parameter_name="repository_name", value=repository_name),
            "image_tag": StrResolvedCliParameter(parameter_name="image_tag", value=image_tag),
        }

    def resolve_name(self, name: str | None) -> str:
        """Resolve the image name, defaulting to the only image if there's just one."""
        images = self.project_manifest.get_images()
        if name:
            return name
        if len(images) == 1:
            return next(iter(images))
        raise ResourceNameRequiredError("image", "jd image list")

    def list_images(self) -> list[ImageInfo]:
        """Return the list of images with name and description."""
        images = self.project_manifest.get_images()
        return [ImageInfo(name=name, description=img.description) for name, img in images.items()]

    def show_image(self, name: str | None = None) -> ImageDetail:
        """Return detailed information about an image."""
        resolved_name = self.resolve_name(name)
        image_def = self.project_manifest.get_image(resolved_name)
        repository_name, tag = self._resolve_image_outputs(image_def)
        cli_paramdefs = self._build_cli_paramdefs(repository_name, tag)

        command = self.project_manifest.get_command("image.show")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
        results = collect_results(runner, command)

        return ImageDetail(
            name=resolved_name,
            tag=tag,
            repository_uri=results.get("repository_uri", ""),
            scanner_type=results.get("scanner_type", ""),
            last_scanned=results.get("last_scanned", ""),
            scan_status=results.get("scan_status", ""),
        )

    def list_tags(self, name: str | None = None) -> list[ImageTag]:
        """Return tags for an image."""
        resolved_name = self.resolve_name(name)
        image_def = self.project_manifest.get_image(resolved_name)
        repository_name, tag = self._resolve_image_outputs(image_def)
        cli_paramdefs = self._build_cli_paramdefs(repository_name, tag)

        command = self.project_manifest.get_command("image.tags")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
        results = collect_results(runner, command)

        raw_tags = results.get("tags", [])
        return [ImageTag(tag=t["tag"], pushed_at=t.get("pushed_at", ""), digest=t.get("digest", "")) for t in raw_tags]

    @staticmethod
    def _select_latest_tag(tags: list[ImageTag]) -> str:
        """Return the most-recently-pushed tag name, excluding the floating 'latest' tag."""
        real_tags = [t for t in tags if t.tag != "latest"]
        if not real_tags:
            return ""
        # list_tags returns tags sorted by push time (most recent first).
        return real_tags[0].tag

    def get_status(self, name: str | None = None) -> ImageStatusResult:
        """Return whether the image is present in ECR, plus its latest non-'latest' tag."""
        resolved_name = self.resolve_name(name)
        image_def = self.project_manifest.get_image(resolved_name)
        repository_name, default_tag = self._resolve_image_outputs(image_def)

        latest_tag = self._select_latest_tag(self.list_tags(resolved_name))
        probe_tag = latest_tag or default_tag

        cli_paramdefs = self._build_cli_paramdefs(repository_name, probe_tag)
        command = self.project_manifest.get_command("image.status")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        try:
            runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
        except ImageTagNotFoundError:
            return ImageStatusResult(
                name=resolved_name,
                status="Missing",
                status_category="degraded",
                latest_tag=latest_tag,
            )
        results = collect_results(runner, command)

        return ImageStatusResult(
            name=resolved_name,
            status=results.get("status", "Available"),
            status_category=results.get("status_category", "healthy"),
            latest_tag=latest_tag,
        )

    def get_vulnerabilities(self, name: str | None = None, tag: str | None = None) -> ImageVulnerabilitiesResult:
        """Return vulnerabilities for an image."""
        resolved_name = self.resolve_name(name)
        image_def = self.project_manifest.get_image(resolved_name)
        repository_name, default_tag = self._resolve_image_outputs(image_def)
        resolved_tag = tag or default_tag
        cli_paramdefs = self._build_cli_paramdefs(repository_name, resolved_tag)

        command = self.project_manifest.get_command("image.vulnerabilities")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        try:
            runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
        except ImageTagNotFoundError:
            raise ImageTagNotFoundError(resolved_name, resolved_tag) from None
        results = collect_results(runner, command)

        raw_vulns = results.get("vulnerabilities", [])
        vulnerabilities = [
            ImageVulnerability(
                cve=v.get("cve", ""),
                type=v.get("type", ""),
                package=v.get("package", ""),
                severity=v.get("severity", ""),
                installed_version=v.get("installed_version", ""),
                fixed_version=v.get("fixed_version", ""),
                score=v.get("score", 0.0),
                epss_score=v.get("epss_score"),
            )
            for v in raw_vulns
        ]

        return ImageVulnerabilitiesResult(
            name=resolved_name,
            tag=resolved_tag,
            last_scanned=results.get("last_scanned", ""),
            scanner_type=results.get("scanner_type", ""),
            critical_count=int(results.get("critical_count") or 0),
            high_count=int(results.get("high_count") or 0),
            vulnerabilities=vulnerabilities,
        )
