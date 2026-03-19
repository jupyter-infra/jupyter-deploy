from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError
from yaml.parser import ParserError
from yaml.scanner import ScannerError

from jupyter_deploy.constants import MASKED_SECRET_VALUE
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.enum import StoreType
from jupyter_deploy.manifest import JupyterDeployManifest
from jupyter_deploy.variables_config import JupyterDeployVariablesConfigV1


class StoreInfo(BaseModel):
    """Information about a project store."""

    store_type: StoreType
    store_id: str
    location: str


class ProjectSummary(BaseModel):
    """Summary of a project in the project store."""

    project_id: str
    last_modified: datetime
    file_count: int


class ProjectDetails(ProjectSummary):
    """Detailed information about a project in the project store."""

    template_name: str | None = None
    template_version: str | None = None
    engine: str | None = None
    variables: dict[str, Any] | None = None


class SyncResult(BaseModel):
    """Result of a sync operation."""

    uploaded: int
    deleted: int
    unchanged: int


class StoreManager(ABC):
    """Abstract interface for a remote project store manager."""

    _cached_store_info: StoreInfo | None

    def resolve_store(self) -> StoreInfo:
        """Return the resolved StoreInfo, discovering the store if not yet resolved."""
        if self._cached_store_info is None:
            self._cached_store_info = self.find_store()
        return self._cached_store_info

    @abstractmethod
    def find_store(self) -> StoreInfo:
        """Find an existing project store.

        Returns:
            StoreInfo with details about the store.

        Raises:
            ProjectStoreNotFoundError: If no project store is found.
        """

    @abstractmethod
    def ensure_store(self, display_manager: DisplayManager) -> StoreInfo:
        """Ensure all components of the project store exist, creating them if necessary.

        Returns:
            StoreInfo with details about the store.
        """

    @abstractmethod
    def push(self, project_path: Path, project_id: str, display_manager: DisplayManager) -> SyncResult:
        """Upload local project files to the remote project store.

        Returns:
            SyncResult with counts of uploaded, deleted, and unchanged files.
        """

    @abstractmethod
    def pull(self, project_id: str, dest_path: Path, display_manager: DisplayManager) -> SyncResult:
        """Download project files from the remote project store to a local path.

        Returns:
            SyncResult with counts of downloaded files.
        """

    @abstractmethod
    def get_project(self, project_id: str, display_manager: DisplayManager) -> ProjectDetails:
        """Return ProjectDetails for a specific project.

        Template metadata fields (template_name, template_version, engine) may be None
        if the remote manifest cannot be read or parsed.

        Raises:
            ProjectNotFoundInStoreError: If the project is not found in the store.
        """

    @abstractmethod
    def list_projects(self, display_manager: DisplayManager) -> list[ProjectSummary]:
        """Return a list of ProjectSummaries for all projects in the project store."""

    @abstractmethod
    def delete_project(self, project_id: str, display_manager: DisplayManager) -> None:
        """Delete all content of a project from the project store."""

    @abstractmethod
    def get_user_identity(self) -> str:
        """Return an identifier for the current user (e.g. an IAM ARN)."""

    @staticmethod
    def _safe_parse_manifest(content: str) -> JupyterDeployManifest | None:
        """Parse manifest YAML content and return a validated manifest.

        Returns None if the content cannot be parsed or validated.
        """
        try:
            data = yaml.safe_load(content)
        except (ParserError, ScannerError):
            return None

        if not isinstance(data, dict):
            return None

        try:
            return JupyterDeployManifest(**data)
        except ValidationError:
            return None

    @staticmethod
    def _safe_parse_variables(content: str) -> dict[str, Any] | None:
        """Parse variables YAML and return a flat dict of variable names to values.

        Sensitive values are masked. Returns None if the content cannot be parsed.
        """
        try:
            data = yaml.safe_load(content)
        except (ParserError, ScannerError):
            return None

        if not isinstance(data, dict):
            return None

        try:
            config = JupyterDeployVariablesConfigV1(**data)
        except ValidationError:
            return None

        variables: dict[str, Any] = {}
        variables.update(config.required)
        for key in config.required_sensitive:
            variables[key] = MASKED_SECRET_VALUE
        # Overrides take precedence over defaults
        for key, value in config.defaults.items():
            variables[key] = config.overrides.get(key, value)
        return variables
