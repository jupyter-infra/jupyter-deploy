import re
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock, patch

import botocore.exceptions
from mypy_boto3_s3.type_defs import ObjectTypeDef

from jupyter_deploy.api.aws.s3.s3_sync import S3SyncResult
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.enum import StoreType
from jupyter_deploy.exceptions import ProjectNotFoundInStoreError, ProjectStoreNotFoundError, ProviderPermissionError
from jupyter_deploy.provider.aws.store.s3_store import S3StoreManager

_MODULE = "jupyter_deploy.provider.aws.store.s3_store"


def _obj(key: str, size: int, last_modified: datetime) -> ObjectTypeDef:
    return {
        "Key": key,
        "Size": size,
        "LastModified": last_modified,
        "ETag": "",
        "ChecksumAlgorithm": [],
        "ChecksumType": "FULL_OBJECT",
        "StorageClass": "STANDARD",
        "Owner": {"DisplayName": "", "ID": ""},
        "RestoreStatus": {},  # type: ignore[typeddict-item]
    }


class TestResolveLeadRegion(unittest.TestCase):
    @patch(f"{_MODULE}.sts_identity")
    @patch(f"{_MODULE}.boto3")
    def test_delegates_to_sts_identity(self, mock_boto3: Mock, mock_sts_identity: Mock) -> None:
        mock_sts_client = Mock()
        mock_boto3.client.return_value = mock_sts_client
        mock_sts_identity.get_partition_lead_region.return_value = "us-east-1"

        result = S3StoreManager.resolve_lead_region()

        self.assertEqual(result, "us-east-1")
        mock_boto3.client.assert_called_once_with("sts")
        mock_sts_identity.get_partition_lead_region.assert_called_once_with(mock_sts_client)

    @patch(f"{_MODULE}.sts_identity")
    @patch(f"{_MODULE}.boto3")
    def test_raises_on_sts_failure(self, mock_boto3: Mock, mock_sts_identity: Mock) -> None:
        mock_sts_identity.get_partition_lead_region.side_effect = botocore.exceptions.ClientError(
            cast(Any, {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}), "GetCallerIdentity"
        )

        with self.assertRaises(botocore.exceptions.ClientError):
            S3StoreManager.resolve_lead_region()


class TestFindStore(unittest.TestCase):
    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_discovers_existing_bucket(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.find_buckets_by_tag.return_value = [{"Name": "existing-bucket"}]
        provider = S3StoreManager(region="us-east-1")

        result = provider.find_store()

        self.assertEqual(result.store_id, "existing-bucket")
        self.assertEqual(result.store_type, StoreType.S3_ONLY)
        self.assertEqual(result.location, "us-east-1")

    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_raises_when_no_bucket_found(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.find_buckets_by_tag.return_value = []
        provider = S3StoreManager(region="us-east-1")

        with self.assertRaises(ProjectStoreNotFoundError):
            provider.find_store()

    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_raises_on_permission_error(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.find_buckets_by_tag.side_effect = botocore.exceptions.ClientError(
            cast(Any, {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}), "ListBuckets"
        )
        provider = S3StoreManager(region="us-east-1")

        with self.assertRaises(ProviderPermissionError):
            provider.find_store()

    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_uses_provided_bucket_name(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.bucket_exists.return_value = True
        provider = S3StoreManager(region="us-west-2", bucket_name="my-bucket")

        result = provider.find_store()

        self.assertEqual(result.store_id, "my-bucket")
        self.assertEqual(result.location, "us-west-2")
        mock_s3_bucket.bucket_exists.assert_called_once()
        mock_s3_bucket.find_buckets_by_tag.assert_not_called()

    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_raises_when_provided_bucket_not_found(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.bucket_exists.return_value = False
        provider = S3StoreManager(region="us-west-2", bucket_name="missing-bucket")

        with self.assertRaises(ProjectStoreNotFoundError) as ctx:
            provider.find_store()

        self.assertIn("missing-bucket", str(ctx.exception))
        self.assertIsNotNone(ctx.exception.hint)
        self.assertIn("--reset-store-id", ctx.exception.hint)  # type: ignore[arg-type]


class TestEnsureStore(unittest.TestCase):
    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_discovers_existing_bucket(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.find_buckets_by_tag.return_value = [{"Name": "existing-bucket"}]
        provider = S3StoreManager(region="us-east-1")

        result = provider.ensure_store(NullDisplay())

        self.assertEqual(result.store_id, "existing-bucket")
        self.assertEqual(result.store_type, StoreType.S3_ONLY)
        self.assertEqual(result.location, "us-east-1")
        mock_s3_bucket.find_buckets_by_tag.assert_called_once_with(
            mock_boto3.client.return_value, "Source", "jupyter-deploy-cli", stop_at_first_match=True
        )
        mock_s3_bucket.create_bucket.assert_not_called()

    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_creates_bucket_when_not_found(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.find_buckets_by_tag.return_value = []
        provider = S3StoreManager(region="us-east-1")

        result = provider.ensure_store(NullDisplay())

        mock_s3_bucket.create_bucket.assert_called_once()
        self.assertTrue(result.store_id.startswith("jupyter-deploy-projects-"))

    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_generated_bucket_name_is_valid_s3_name(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.find_buckets_by_tag.return_value = []
        provider = S3StoreManager(region="us-east-1")

        result = provider.ensure_store(NullDisplay())

        s3_bucket_pattern = re.compile(r"^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$")
        self.assertRegex(result.store_id, s3_bucket_pattern)
        self.assertLessEqual(len(result.store_id), 63)

    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_raises_on_bucket_creation_failure(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.find_buckets_by_tag.return_value = []
        mock_s3_bucket.create_bucket.side_effect = RuntimeError("creation failed")
        provider = S3StoreManager(region="us-east-1")

        with self.assertRaises(RuntimeError):
            provider.ensure_store(NullDisplay())

    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_uses_provided_bucket_name(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        provider = S3StoreManager(region="us-east-1", bucket_name="my-bucket")

        result = provider.ensure_store(NullDisplay())

        self.assertEqual(result.store_id, "my-bucket")
        mock_s3_bucket.find_buckets_by_tag.assert_not_called()

    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_raises_on_s3_lookup_failure(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.find_buckets_by_tag.side_effect = botocore.exceptions.ClientError(
            cast(Any, {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}), "ListBuckets"
        )
        provider = S3StoreManager(region="us-east-1")

        with self.assertRaises(ProviderPermissionError):
            provider.ensure_store(NullDisplay())

    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_raises_on_s3_create_failure(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.find_buckets_by_tag.return_value = []
        mock_s3_bucket.create_bucket.side_effect = botocore.exceptions.ClientError(
            cast(Any, {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}), "CreateBucket"
        )
        provider = S3StoreManager(region="us-east-1")

        with self.assertRaises(ProviderPermissionError):
            provider.ensure_store(NullDisplay())


class TestPush(unittest.TestCase):
    @patch(f"{_MODULE}.s3_sync")
    @patch(f"{_MODULE}.boto3")
    def test_syncs_project_to_remote(self, mock_boto3: Mock, mock_sync: Mock) -> None:
        mock_sync.sync_to_remote.return_value = S3SyncResult(uploaded=3, deleted=1, unchanged=5)
        provider = S3StoreManager(region="us-east-1", bucket_name="bucket")

        with patch.object(Path, "exists", return_value=True):
            result = provider.push(Path("/project"), "my-project", NullDisplay())

        self.assertEqual(result.uploaded, 3)
        self.assertEqual(result.deleted, 1)
        self.assertEqual(result.unchanged, 5)

    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_raises_when_store_not_initialized(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.find_buckets_by_tag.return_value = []
        provider = S3StoreManager(region="us-east-1")

        with self.assertRaises(ProjectStoreNotFoundError):
            provider.push(Path("/project"), "my-project", NullDisplay())

    @patch(f"{_MODULE}.s3_sync")
    @patch(f"{_MODULE}.boto3")
    def test_raises_on_sync_failure(self, mock_boto3: Mock, mock_sync: Mock) -> None:
        mock_sync.sync_to_remote.side_effect = RuntimeError("upload failed")
        provider = S3StoreManager(region="us-east-1", bucket_name="bucket")

        with patch.object(Path, "exists", return_value=False), self.assertRaises(RuntimeError):
            provider.push(Path("/project"), "my-project", NullDisplay())

    @patch(f"{_MODULE}.s3_sync")
    @patch(f"{_MODULE}.boto3")
    def test_raises_on_sync_to_remote_permission_error(self, mock_boto3: Mock, mock_sync: Mock) -> None:
        mock_sync.sync_to_remote.side_effect = botocore.exceptions.ClientError(
            cast(Any, {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}), "PutObject"
        )
        provider = S3StoreManager(region="us-east-1", bucket_name="bucket")

        with patch.object(Path, "exists", return_value=False), self.assertRaises(ProviderPermissionError):
            provider.push(Path("/project"), "my-project", NullDisplay())


class TestPull(unittest.TestCase):
    @patch(f"{_MODULE}.s3_sync")
    @patch(f"{_MODULE}.boto3")
    def test_syncs_from_remote(self, mock_boto3: Mock, mock_sync: Mock) -> None:
        mock_sync.sync_from_remote.return_value = S3SyncResult(uploaded=5, deleted=0, unchanged=0)
        provider = S3StoreManager(region="us-east-1", bucket_name="bucket")

        result = provider.pull("my-project", Path("/dest"), NullDisplay())

        self.assertEqual(result.uploaded, 5)

    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_raises_when_store_not_initialized(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.find_buckets_by_tag.return_value = []
        provider = S3StoreManager(region="us-east-1")

        with self.assertRaises(ProjectStoreNotFoundError):
            provider.pull("my-project", Path("/dest"), NullDisplay())

    @patch(f"{_MODULE}.s3_sync")
    @patch(f"{_MODULE}.boto3")
    def test_raises_on_sync_from_remote_permission_error(self, mock_boto3: Mock, mock_sync: Mock) -> None:
        mock_sync.sync_from_remote.side_effect = botocore.exceptions.ClientError(
            cast(Any, {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}), "GetObject"
        )
        provider = S3StoreManager(region="us-east-1", bucket_name="bucket")

        with self.assertRaises(ProviderPermissionError):
            provider.pull("my-project", Path("/dest"), NullDisplay())


class TestGetProject(unittest.TestCase):
    @patch(f"{_MODULE}.s3_object")
    @patch(f"{_MODULE}.boto3")
    def test_returns_project_details_with_manifest(self, mock_boto3: Mock, mock_s3_object: Mock) -> None:
        now = datetime.now(tz=UTC)
        mock_s3_object.list_objects.return_value = [
            _obj("my-project/project/f1.txt", 10, now),
            _obj("my-project/project/f2.txt", 20, now),
        ]
        manifest_yaml = "schema_version: 1\ntemplate:\n  name: base-template\n  version: 1.2.0\n  engine: terraform\n"
        variables_yaml = (
            "schema_version: 1\n"
            "required:\n  project_name: my-project\n"
            "required_sensitive:\n  gh_token: secret123\n"
            "overrides:\n  instance_type: t3.large\n"
            "defaults:\n  instance_type: t3.medium\n  region: us-east-1\n"
        )
        mock_s3_object.get_object_content.side_effect = [manifest_yaml, variables_yaml]
        provider = S3StoreManager(region="us-east-1", bucket_name="bucket")

        result = provider.get_project("my-project", NullDisplay())

        self.assertEqual(result.project_id, "my-project")
        self.assertEqual(result.file_count, 2)
        self.assertEqual(result.last_modified, now)
        self.assertEqual(result.template_name, "base-template")
        self.assertEqual(result.template_version, "1.2.0")
        self.assertEqual(result.engine, "terraform")
        self.assertIsNotNone(result.variables)
        assert result.variables is not None
        self.assertEqual(result.variables["project_name"], "my-project")
        self.assertEqual(result.variables["gh_token"], "****")
        self.assertEqual(result.variables["instance_type"], "t3.large")
        self.assertEqual(result.variables["region"], "us-east-1")
        mock_s3_object.list_objects.assert_called_once_with(mock_boto3.client.return_value, "bucket", "my-project/")

    @patch(f"{_MODULE}.s3_object")
    @patch(f"{_MODULE}.boto3")
    def test_returns_project_details_when_manifest_missing(self, mock_boto3: Mock, mock_s3_object: Mock) -> None:
        now = datetime.now(tz=UTC)
        mock_s3_object.list_objects.return_value = [_obj("my-project/project/f1.txt", 10, now)]
        # Simulate NoSuchKey via the S3 client exception attribute
        mock_s3_client = mock_boto3.client.return_value
        no_such_key = type("NoSuchKey", (Exception,), {})
        mock_s3_client.exceptions.NoSuchKey = no_such_key
        mock_s3_object.get_object_content.side_effect = no_such_key()
        provider = S3StoreManager(region="us-east-1", bucket_name="bucket")

        result = provider.get_project("my-project", NullDisplay())

        self.assertEqual(result.project_id, "my-project")
        self.assertIsNone(result.template_name)
        self.assertIsNone(result.template_version)
        self.assertIsNone(result.engine)
        self.assertIsNone(result.variables)

    @patch(f"{_MODULE}.s3_object")
    @patch(f"{_MODULE}.boto3")
    def test_raises_when_project_not_found(self, mock_boto3: Mock, mock_s3_object: Mock) -> None:
        mock_s3_object.list_objects.return_value = []
        provider = S3StoreManager(region="us-east-1", bucket_name="bucket")

        with self.assertRaises(ProjectNotFoundInStoreError) as ctx:
            provider.get_project("nonexistent", NullDisplay())

        self.assertEqual(ctx.exception.project_id, "nonexistent")
        self.assertEqual(ctx.exception.store_type, "s3-only")
        self.assertEqual(ctx.exception.store_id, "bucket")

    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_raises_when_store_not_initialized(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.find_buckets_by_tag.return_value = []
        provider = S3StoreManager(region="us-east-1")

        with self.assertRaises(ProjectStoreNotFoundError):
            provider.get_project("my-project", NullDisplay())


class TestListProjects(unittest.TestCase):
    @patch(f"{_MODULE}.s3_object")
    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_lists_projects(self, mock_boto3: Mock, mock_s3_bucket: Mock, mock_s3_object: Mock) -> None:
        now = datetime.now(tz=UTC)
        mock_s3_bucket.list_top_level_prefixes.return_value = ["project-a", "project-b"]
        mock_s3_object.list_objects.side_effect = [
            [_obj("project-a/f.txt", 10, now)],
            [],
        ]
        provider = S3StoreManager(region="us-east-1", bucket_name="bucket")

        result = provider.list_projects(NullDisplay())

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].project_id, "project-a")
        self.assertEqual(result[0].file_count, 1)
        self.assertEqual(result[1].project_id, "project-b")
        self.assertEqual(result[1].file_count, 0)

    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_raises_when_store_not_initialized(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.find_buckets_by_tag.return_value = []
        provider = S3StoreManager(region="us-east-1")

        with self.assertRaises(ProjectStoreNotFoundError):
            provider.list_projects(NullDisplay())

    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_raises_on_list_prefixes_permission_error(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.list_top_level_prefixes.side_effect = botocore.exceptions.ClientError(
            cast(Any, {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}), "ListObjectsV2"
        )
        provider = S3StoreManager(region="us-east-1", bucket_name="bucket")

        with self.assertRaises(ProviderPermissionError):
            provider.list_projects(NullDisplay())

    @patch(f"{_MODULE}.s3_object")
    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_raises_on_list_objects_permission_error(
        self, mock_boto3: Mock, mock_s3_bucket: Mock, mock_s3_object: Mock
    ) -> None:
        mock_s3_bucket.list_top_level_prefixes.return_value = ["project-a"]
        mock_s3_object.list_objects.side_effect = botocore.exceptions.ClientError(
            cast(Any, {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}), "ListObjectsV2"
        )
        provider = S3StoreManager(region="us-east-1", bucket_name="bucket")

        with self.assertRaises(ProviderPermissionError):
            provider.list_projects(NullDisplay())


class TestDeleteProject(unittest.TestCase):
    @patch(f"{_MODULE}.s3_object")
    @patch(f"{_MODULE}.boto3")
    def test_deletes_project_objects(self, mock_boto3: Mock, mock_s3_object: Mock) -> None:
        now = datetime.now(tz=UTC)
        mock_s3_object.list_objects.return_value = [
            _obj("proj/a.txt", 10, now),
            _obj("proj/b.txt", 20, now),
        ]
        provider = S3StoreManager(region="us-east-1", bucket_name="bucket")

        provider.delete_project("proj", NullDisplay())

        mock_s3_object.delete_objects.assert_called_once()
        call_args = mock_s3_object.delete_objects.call_args
        keys = call_args[1]["keys"] if "keys" in call_args[1] else call_args[0][2]
        self.assertEqual(keys, ["proj/a.txt", "proj/b.txt"])

    @patch(f"{_MODULE}.s3_object")
    @patch(f"{_MODULE}.boto3")
    def test_handles_empty_project(self, mock_boto3: Mock, mock_s3_object: Mock) -> None:
        mock_s3_object.list_objects.return_value = []
        provider = S3StoreManager(region="us-east-1", bucket_name="bucket")

        provider.delete_project("proj", NullDisplay())

        mock_s3_object.delete_objects.assert_not_called()

    @patch(f"{_MODULE}.s3_bucket")
    @patch(f"{_MODULE}.boto3")
    def test_raises_when_store_not_initialized(self, mock_boto3: Mock, mock_s3_bucket: Mock) -> None:
        mock_s3_bucket.find_buckets_by_tag.return_value = []
        provider = S3StoreManager(region="us-east-1")

        with self.assertRaises(ProjectStoreNotFoundError):
            provider.delete_project("proj", NullDisplay())

    @patch(f"{_MODULE}.s3_object")
    @patch(f"{_MODULE}.boto3")
    def test_raises_on_list_objects_permission_error(self, mock_boto3: Mock, mock_s3_object: Mock) -> None:
        mock_s3_object.list_objects.side_effect = botocore.exceptions.ClientError(
            cast(Any, {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}), "ListObjectsV2"
        )
        provider = S3StoreManager(region="us-east-1", bucket_name="bucket")

        with self.assertRaises(ProviderPermissionError):
            provider.delete_project("proj", NullDisplay())

    @patch(f"{_MODULE}.s3_object")
    @patch(f"{_MODULE}.boto3")
    def test_raises_on_delete_objects_permission_error(self, mock_boto3: Mock, mock_s3_object: Mock) -> None:
        now = datetime.now(tz=UTC)
        mock_s3_object.list_objects.return_value = [_obj("proj/a.txt", 10, now)]
        mock_s3_object.delete_objects.side_effect = botocore.exceptions.ClientError(
            cast(Any, {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}), "DeleteObjects"
        )
        provider = S3StoreManager(region="us-east-1", bucket_name="bucket")

        with self.assertRaises(ProviderPermissionError):
            provider.delete_project("proj", NullDisplay())


class TestGetUserIdentity(unittest.TestCase):
    @patch(f"{_MODULE}.sts_identity")
    @patch(f"{_MODULE}.boto3")
    def test_returns_caller_arn(self, mock_boto3: Mock, mock_sts_identity: Mock) -> None:
        mock_sts_identity.get_caller_arn.return_value = "arn:aws:iam::123456789012:user/jeff"
        provider = S3StoreManager(region="us-east-1", bucket_name="bucket")

        result = provider.get_user_identity()

        self.assertEqual(result, "arn:aws:iam::123456789012:user/jeff")
