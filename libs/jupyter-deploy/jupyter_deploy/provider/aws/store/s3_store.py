from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from mypy_boto3_s3.client import S3Client

from jupyter_deploy.api.aws.s3 import s3_bucket, s3_object, s3_sync
from jupyter_deploy.api.aws.sts import sts_identity
from jupyter_deploy.constants import MANIFEST_FILENAME, VARIABLES_FILENAME
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.enum import StoreType
from jupyter_deploy.exceptions import ProjectNotFoundInStoreError, ProjectStoreNotFoundError
from jupyter_deploy.provider.aws.aws_error_handler import aws_error_context_manager
from jupyter_deploy.provider.aws.store.constants import (
    STORE_BUCKET_NAME_PREFIX,
    STORE_TAG_SOURCE_KEY,
    STORE_TAG_SOURCE_VALUE,
    STORE_TAG_VERSION_KEY,
)
from jupyter_deploy.provider.store.store_manager import (
    ProjectDetails,
    ProjectSummary,
    StoreInfo,
    StoreManager,
    SyncResult,
)


class S3StoreManager(StoreManager):
    """StoreManager implementation backed by S3 only (no state locking)."""

    _store_type = StoreType.S3_ONLY

    def __init__(self, region: str, bucket_name: str | None = None) -> None:
        self._region = region
        self._bucket_name = bucket_name
        self._cached_store_info: StoreInfo | None = None
        self._s3_client: S3Client = boto3.client("s3", region_name=region)

    @staticmethod
    def resolve_lead_region() -> str:
        """Resolve the partition lead region from the caller's AWS credentials."""
        sts_client = boto3.client("sts")
        return sts_identity.get_partition_lead_region(sts_client)

    def find_store(self) -> StoreInfo:
        with aws_error_context_manager():
            bucket_name = self._bucket_name
            if bucket_name:
                # Verify the pinned bucket actually exists
                if not s3_bucket.bucket_exists(self._s3_client, bucket_name):
                    raise ProjectStoreNotFoundError(
                        f"S3 bucket not found: {bucket_name}",
                        hint="try 'jd config --reset-store-id' to rediscover the store.",
                    )
            else:
                matched = s3_bucket.find_buckets_by_tag(
                    self._s3_client, STORE_TAG_SOURCE_KEY, STORE_TAG_SOURCE_VALUE, stop_at_first_match=True
                )
                bucket_name = matched[0].get("Name") if matched else None

            if not bucket_name:
                raise ProjectStoreNotFoundError("No S3 bucket project store found in your AWS account.")

            self._bucket_name = bucket_name
            return StoreInfo(store_type=self._store_type, store_id=bucket_name, location=self._region)

    def ensure_store(self, display_manager: DisplayManager) -> StoreInfo:
        with aws_error_context_manager():
            if not self._bucket_name:
                display_manager.info("Looking for existing projects store in your AWS account...")
                matched = s3_bucket.find_buckets_by_tag(
                    self._s3_client, STORE_TAG_SOURCE_KEY, STORE_TAG_SOURCE_VALUE, stop_at_first_match=True
                )
                bucket_name = matched[0].get("Name") if matched else None

                if bucket_name:
                    display_manager.info(f"Found existing S3 bucket projects store: {bucket_name}")
                    created = False
                else:
                    # Random suffix prevents bucket name sniping attacks. 20 hex chars = 80 bits
                    # of entropy from os.urandom (CSPRNG); birthday collision at ~2^40 (~1 trillion).
                    # Total name length: 24 (prefix) + 1 (dash) + 20 (suffix) = 45 chars (S3 max: 63).
                    bucket_name = f"{STORE_BUCKET_NAME_PREFIX}-{uuid.uuid4().hex[:20]}"
                    display_manager.info(f"Creating S3 bucket projects store: {bucket_name}")
                    tags = {
                        STORE_TAG_SOURCE_KEY: STORE_TAG_SOURCE_VALUE,
                        STORE_TAG_VERSION_KEY: "1",
                    }
                    s3_bucket.create_bucket(self._s3_client, bucket_name, self._region, tags)
                    created = True

                self._bucket_name = bucket_name
                if created:
                    display_manager.success(f"S3 project store created: {self._bucket_name}")
                else:
                    display_manager.info(f"S3 project store ready: {self._bucket_name}")
                display_manager.line()

            return StoreInfo(store_type=self._store_type, store_id=self._bucket_name, location=self._region)

    def push(self, project_path: Path, project_id: str, display_manager: DisplayManager) -> SyncResult:
        bucket = self.resolve_store().store_id

        with aws_error_context_manager():
            # Scope the project snapshot under a "project/" subdirectory so it doesn't overlap
            # with engine state (e.g. terraform.tfstate) stored under the root prefix.
            # The sync deletes stale remote objects, so without this separation it would delete
            # the engine state files, which are gitignored and therefore absent from the local
            # file walk.
            prefix = f"{project_id}/project/"
            gitignore_path = project_path / ".gitignore"

            display_manager.info(f"Updating remote store: {bucket}, prefix: {prefix}")
            result = s3_sync.sync_to_remote(
                self._s3_client,
                bucket,
                prefix,
                project_path,
                gitignore_path if gitignore_path.exists() else None,
            )

            display_manager.success(
                f"Updated project store: {result.uploaded} uploaded, "
                f"{result.deleted} deleted, {result.unchanged} unchanged"
            )
            return SyncResult(uploaded=result.uploaded, deleted=result.deleted, unchanged=result.unchanged)

    def pull(self, project_id: str, dest_path: Path, display_manager: DisplayManager) -> SyncResult:
        bucket = self.resolve_store().store_id

        with aws_error_context_manager():
            prefix = f"{project_id}/project/"

            display_manager.info(f"Pulling project from s3://{bucket}/{prefix} to {dest_path.absolute()}")
            result = s3_sync.sync_from_remote(self._s3_client, bucket, prefix, dest_path)

            display_manager.success(f"Pull complete: {result.uploaded} files downloaded")
            return SyncResult(uploaded=result.uploaded, deleted=result.deleted, unchanged=result.unchanged)

    def get_project(self, project_id: str, display_manager: DisplayManager) -> ProjectDetails:
        bucket = self.resolve_store().store_id

        with aws_error_context_manager():
            objects = s3_object.list_objects(self._s3_client, bucket, f"{project_id}/")
            if not objects:
                raise ProjectNotFoundInStoreError(project_id, store_type=self._store_type.value, store_id=bucket)

            last_modified = max(obj["LastModified"] for obj in objects)

            # Try to read template metadata from the remote manifest
            manifest = None
            try:
                content = s3_object.get_object_content(
                    self._s3_client, bucket, f"{project_id}/project/{MANIFEST_FILENAME}"
                )
                manifest = self._safe_parse_manifest(content)
            except self._s3_client.exceptions.NoSuchKey:
                pass

            # Try to read variables from the remote variables.yaml
            variables: dict[str, Any] | None = None
            try:
                variables_content = s3_object.get_object_content(
                    self._s3_client, bucket, f"{project_id}/project/{VARIABLES_FILENAME}"
                )
                variables = self._safe_parse_variables(variables_content)
            except self._s3_client.exceptions.NoSuchKey:
                pass

            return ProjectDetails(
                project_id=project_id,
                last_modified=last_modified,
                file_count=len(objects),
                template_name=manifest.template.name if manifest else None,
                template_version=manifest.template.version if manifest else None,
                engine=manifest.template.engine if manifest else None,
                variables=variables,
            )

    def list_projects(self, display_manager: DisplayManager) -> list[ProjectSummary]:
        bucket = self.resolve_store().store_id

        with aws_error_context_manager():
            display_manager.info(f"Listing projects in projects store: {bucket}")
            prefixes = s3_bucket.list_top_level_prefixes(self._s3_client, bucket)
            summaries: list[ProjectSummary] = []

            for prefix_name in prefixes:
                objects = s3_object.list_objects(self._s3_client, bucket, f"{prefix_name}/")
                last_modified = (
                    max(obj["LastModified"] for obj in objects) if objects else datetime.min.replace(tzinfo=UTC)
                )
                summaries.append(
                    ProjectSummary(
                        project_id=prefix_name,
                        last_modified=last_modified,
                        file_count=len(objects),
                    )
                )

            return summaries

    def delete_project(self, project_id: str, display_manager: DisplayManager) -> None:
        bucket = self.resolve_store().store_id

        with aws_error_context_manager():
            display_manager.info(f"Deleting project '{project_id}' from projects store: {bucket}")
            objects = s3_object.list_objects(self._s3_client, bucket, f"{project_id}/")
            if objects:
                display_manager.info(f"Found {len(objects)} for the project in projects store: {bucket}")
                keys = [obj["Key"] for obj in objects]
                s3_object.delete_objects(self._s3_client, bucket, keys)
            display_manager.success(f"Deleted {len(objects)} for project '{project_id}' in projects store: {bucket}")

    def get_user_identity(self) -> str:
        with aws_error_context_manager():
            sts_client = boto3.client("sts")
            return sts_identity.get_caller_arn(sts_client)
