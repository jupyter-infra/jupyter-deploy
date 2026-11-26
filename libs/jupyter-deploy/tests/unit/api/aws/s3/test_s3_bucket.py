import unittest
from unittest.mock import Mock

from jupyter_deploy.api.aws.s3.s3_bucket import (
    bucket_exists,
    create_bucket,
    find_buckets_by_tag,
    list_top_level_prefixes,
    update_bucket_tags,
)


class TestFindBucketsByTag(unittest.TestCase):
    def test_returns_matching_bucket(self) -> None:
        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Buckets": [{"Name": "my-bucket", "CreationDate": None}]}]
        mock_s3.get_paginator.return_value = mock_paginator
        mock_s3.get_bucket_tagging.return_value = {"TagSet": [{"Key": "Source", "Value": "jupyter-deploy-cli"}]}
        mock_s3.exceptions.ClientError = type("ClientError", (Exception,), {})

        result = find_buckets_by_tag(mock_s3, "Source", "jupyter-deploy-cli")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["Name"], "my-bucket")

    def test_returns_empty_when_no_match(self) -> None:
        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Buckets": [{"Name": "other-bucket"}]}]
        mock_s3.get_paginator.return_value = mock_paginator
        mock_s3.get_bucket_tagging.return_value = {"TagSet": [{"Key": "Owner", "Value": "someone-else"}]}
        mock_s3.exceptions.ClientError = type("ClientError", (Exception,), {})

        result = find_buckets_by_tag(mock_s3, "Source", "jupyter-deploy-cli")

        self.assertEqual(result, [])

    def test_returns_empty_when_no_buckets(self) -> None:
        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Buckets": []}]
        mock_s3.get_paginator.return_value = mock_paginator

        result = find_buckets_by_tag(mock_s3, "Source", "jupyter-deploy-cli")

        self.assertEqual(result, [])

    def test_skips_bucket_with_no_tags(self) -> None:
        client_error = type("ClientError", (Exception,), {})
        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Buckets": [{"Name": "no-tags-bucket"}, {"Name": "tagged-bucket"}]}]
        mock_s3.get_paginator.return_value = mock_paginator
        no_tag_error = client_error()
        no_tag_error.response = {"Error": {"Code": "NoSuchTagSet"}}
        mock_s3.get_bucket_tagging.side_effect = [
            no_tag_error,
            {"TagSet": [{"Key": "Source", "Value": "jupyter-deploy-cli"}]},
        ]
        mock_s3.exceptions.ClientError = client_error

        result = find_buckets_by_tag(mock_s3, "Source", "jupyter-deploy-cli")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["Name"], "tagged-bucket")

    def test_skips_bucket_deleted_after_listing(self) -> None:
        client_error = type("ClientError", (Exception,), {})
        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Buckets": [{"Name": "deleted-bucket"}, {"Name": "tagged-bucket"}]}]
        mock_s3.get_paginator.return_value = mock_paginator
        gone_error = client_error()
        gone_error.response = {"Error": {"Code": "NoSuchBucket"}}
        mock_s3.get_bucket_tagging.side_effect = [
            gone_error,
            {"TagSet": [{"Key": "Source", "Value": "jupyter-deploy-cli"}]},
        ]
        mock_s3.exceptions.ClientError = client_error

        result = find_buckets_by_tag(mock_s3, "Source", "jupyter-deploy-cli")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["Name"], "tagged-bucket")

    def test_returns_all_matching_buckets(self) -> None:
        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Buckets": [{"Name": "bucket-a"}, {"Name": "bucket-b"}]}]
        mock_s3.get_paginator.return_value = mock_paginator
        mock_s3.get_bucket_tagging.side_effect = [
            {"TagSet": [{"Key": "Source", "Value": "jupyter-deploy-cli"}]},
            {"TagSet": [{"Key": "Source", "Value": "jupyter-deploy-cli"}]},
        ]
        mock_s3.exceptions.ClientError = type("ClientError", (Exception,), {})

        result = find_buckets_by_tag(mock_s3, "Source", "jupyter-deploy-cli")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["Name"], "bucket-a")
        self.assertEqual(result[1]["Name"], "bucket-b")

    def test_paginates_across_multiple_pages(self) -> None:
        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {"Buckets": [{"Name": "page1-bucket"}]},
            {"Buckets": [{"Name": "page2-bucket"}]},
        ]
        mock_s3.get_paginator.return_value = mock_paginator
        mock_s3.get_bucket_tagging.side_effect = [
            {"TagSet": [{"Key": "Source", "Value": "jupyter-deploy-cli"}]},
            {"TagSet": [{"Key": "Source", "Value": "jupyter-deploy-cli"}]},
        ]
        mock_s3.exceptions.ClientError = type("ClientError", (Exception,), {})

        result = find_buckets_by_tag(mock_s3, "Source", "jupyter-deploy-cli")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["Name"], "page1-bucket")
        self.assertEqual(result[1]["Name"], "page2-bucket")
        mock_s3.get_paginator.assert_called_once_with("list_buckets")

    def test_stop_at_first_match_returns_single_result(self) -> None:
        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Buckets": [{"Name": "bucket-a"}, {"Name": "bucket-b"}]}]
        mock_s3.get_paginator.return_value = mock_paginator
        mock_s3.get_bucket_tagging.side_effect = [
            {"TagSet": [{"Key": "Source", "Value": "jupyter-deploy-cli"}]},
            {"TagSet": [{"Key": "Source", "Value": "jupyter-deploy-cli"}]},
        ]
        mock_s3.exceptions.ClientError = type("ClientError", (Exception,), {})

        result = find_buckets_by_tag(mock_s3, "Source", "jupyter-deploy-cli", stop_at_first_match=True)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["Name"], "bucket-a")
        # Should not have checked tags on bucket-b
        self.assertEqual(mock_s3.get_bucket_tagging.call_count, 1)

    def test_stop_at_first_match_across_pages(self) -> None:
        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {"Buckets": [{"Name": "no-match"}]},
            {"Buckets": [{"Name": "match"}, {"Name": "also-match"}]},
        ]
        mock_s3.get_paginator.return_value = mock_paginator
        mock_s3.get_bucket_tagging.side_effect = [
            {"TagSet": [{"Key": "Owner", "Value": "someone-else"}]},
            {"TagSet": [{"Key": "Source", "Value": "jupyter-deploy-cli"}]},
            {"TagSet": [{"Key": "Source", "Value": "jupyter-deploy-cli"}]},
        ]
        mock_s3.exceptions.ClientError = type("ClientError", (Exception,), {})

        result = find_buckets_by_tag(mock_s3, "Source", "jupyter-deploy-cli", stop_at_first_match=True)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["Name"], "match")
        # Checked no-match and match, but not also-match
        self.assertEqual(mock_s3.get_bucket_tagging.call_count, 2)

    def test_stop_at_first_match_returns_empty_when_none_found(self) -> None:
        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Buckets": [{"Name": "bucket-a"}]}]
        mock_s3.get_paginator.return_value = mock_paginator
        mock_s3.get_bucket_tagging.return_value = {"TagSet": [{"Key": "Owner", "Value": "other"}]}
        mock_s3.exceptions.ClientError = type("ClientError", (Exception,), {})

        result = find_buckets_by_tag(mock_s3, "Source", "jupyter-deploy-cli", stop_at_first_match=True)

        self.assertEqual(result, [])

    def test_raises_on_non_tag_error(self) -> None:
        client_error = type("ClientError", (Exception,), {})
        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Buckets": [{"Name": "bucket"}]}]
        mock_s3.get_paginator.return_value = mock_paginator
        error = client_error()
        error.response = {"Error": {"Code": "AccessDenied"}}
        mock_s3.get_bucket_tagging.side_effect = error
        mock_s3.exceptions.ClientError = client_error

        with self.assertRaises(client_error):
            find_buckets_by_tag(mock_s3, "Source", "jupyter-deploy-cli")


class TestCreateBucket(unittest.TestCase):
    def test_creates_bucket_with_versioning_encryption_tags(self) -> None:
        mock_s3 = Mock()
        tags = {"Source": "jupyter-deploy-cli", "Version": "1"}

        create_bucket(mock_s3, "test-bucket", "us-west-2", tags)

        mock_s3.create_bucket.assert_called_once_with(
            Bucket="test-bucket",
            CreateBucketConfiguration={"LocationConstraint": "us-west-2"},
        )
        mock_s3.put_bucket_versioning.assert_called_once_with(
            Bucket="test-bucket",
            VersioningConfiguration={"Status": "Enabled"},
        )
        mock_s3.put_bucket_encryption.assert_called_once()
        mock_s3.put_bucket_tagging.assert_called_once()

    def test_us_east_1_omits_location_constraint(self) -> None:
        mock_s3 = Mock()

        create_bucket(mock_s3, "test-bucket", "us-east-1", {})

        mock_s3.create_bucket.assert_called_once_with(Bucket="test-bucket")

    def test_tags_are_formatted_correctly(self) -> None:
        mock_s3 = Mock()
        tags = {"Key1": "Val1", "Key2": "Val2"}

        create_bucket(mock_s3, "test-bucket", "eu-west-1", tags)

        call_args = mock_s3.put_bucket_tagging.call_args
        tag_set = call_args[1]["Tagging"]["TagSet"]
        tag_dict = {t["Key"]: t["Value"] for t in tag_set}
        self.assertEqual(tag_dict, {"Key1": "Val1", "Key2": "Val2"})


class TestUpdateBucketTags(unittest.TestCase):
    def test_puts_tags(self) -> None:
        mock_s3 = Mock()
        tags = {"Version": "2"}

        update_bucket_tags(mock_s3, "test-bucket", tags)

        call_args = mock_s3.put_bucket_tagging.call_args
        self.assertEqual(call_args[1]["Bucket"], "test-bucket")
        tag_set = call_args[1]["Tagging"]["TagSet"]
        self.assertEqual(tag_set, [{"Key": "Version", "Value": "2"}])


class TestListTopLevelPrefixes(unittest.TestCase):
    def test_returns_prefixes_without_trailing_slash(self) -> None:
        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {"CommonPrefixes": [{"Prefix": "project-a/"}, {"Prefix": "project-b/"}]}
        ]
        mock_s3.get_paginator.return_value = mock_paginator

        result = list_top_level_prefixes(mock_s3, "bucket")

        self.assertEqual(result, ["project-a", "project-b"])
        mock_paginator.paginate.assert_called_once_with(Bucket="bucket", Delimiter="/")

    def test_returns_empty_list_when_no_prefixes(self) -> None:
        mock_s3 = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{}]
        mock_s3.get_paginator.return_value = mock_paginator

        result = list_top_level_prefixes(mock_s3, "bucket")

        self.assertEqual(result, [])


class TestBucketExists(unittest.TestCase):
    def test_returns_true_when_bucket_exists(self) -> None:
        mock_s3 = Mock()
        mock_s3.head_bucket.return_value = {}

        self.assertTrue(bucket_exists(mock_s3, "my-bucket"))
        mock_s3.head_bucket.assert_called_once_with(Bucket="my-bucket")

    def test_returns_false_on_404(self) -> None:
        client_error = type("ClientError", (Exception,), {})
        mock_s3 = Mock()
        error = client_error()
        error.response = {"Error": {"Code": "404"}}
        mock_s3.head_bucket.side_effect = error
        mock_s3.exceptions.ClientError = client_error

        self.assertFalse(bucket_exists(mock_s3, "missing-bucket"))

    def test_returns_false_on_no_such_bucket(self) -> None:
        client_error = type("ClientError", (Exception,), {})
        mock_s3 = Mock()
        error = client_error()
        error.response = {"Error": {"Code": "NoSuchBucket"}}
        mock_s3.head_bucket.side_effect = error
        mock_s3.exceptions.ClientError = client_error

        self.assertFalse(bucket_exists(mock_s3, "missing-bucket"))

    def test_returns_false_on_403(self) -> None:
        client_error = type("ClientError", (Exception,), {})
        mock_s3 = Mock()
        error = client_error()
        error.response = {"Error": {"Code": "403"}}
        mock_s3.head_bucket.side_effect = error
        mock_s3.exceptions.ClientError = client_error

        self.assertFalse(bucket_exists(mock_s3, "forbidden-bucket"))

    def test_raises_on_unexpected_error(self) -> None:
        client_error = type("ClientError", (Exception,), {})
        mock_s3 = Mock()
        error = client_error()
        error.response = {"Error": {"Code": "InternalError"}}
        mock_s3.head_bucket.side_effect = error
        mock_s3.exceptions.ClientError = client_error

        with self.assertRaises(client_error):
            bucket_exists(mock_s3, "some-bucket")
