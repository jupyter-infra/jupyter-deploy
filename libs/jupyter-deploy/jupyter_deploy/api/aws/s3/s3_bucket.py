from __future__ import annotations

from mypy_boto3_s3.client import S3Client
from mypy_boto3_s3.type_defs import BucketTypeDef, TagTypeDef


def find_buckets_by_tag(
    s3_client: S3Client,
    tag_key: str,
    tag_value: str,
    stop_at_first_match: bool = False,
) -> list[BucketTypeDef]:
    """Return a list of buckets matching a specific tag key/value pair.

    Uses the ListBuckets paginator to handle accounts with many buckets.

    Args:
        s3_client: S3 client.
        tag_key: Tag key to match.
        tag_value: Tag value to match.
        stop_at_first_match: If True, return immediately after finding the first match.

    Raises:
        botocore.exceptions.ClientError on AWS API errors.
    """
    matched: list[BucketTypeDef] = []
    paginator = s3_client.get_paginator("list_buckets")

    for page in paginator.paginate():
        for bucket in page.get("Buckets", []):
            bucket_name = bucket.get("Name", "")
            if not bucket_name:
                continue
            try:
                tag_response = s3_client.get_bucket_tagging(Bucket=bucket_name)
                tag_set = tag_response.get("TagSet", [])
                for tag in tag_set:
                    if tag.get("Key") == tag_key and tag.get("Value") == tag_value:
                        matched.append(bucket)
                        if stop_at_first_match:
                            return matched
                        break
            except s3_client.exceptions.ClientError as e:
                # NoSuchTagSet: the bucket has no tags.
                # NoSuchBucket: the bucket was deleted after ListBuckets returned it.
                if e.response.get("Error", {}).get("Code") in ("NoSuchTagSet", "NoSuchBucket"):
                    continue
                raise

    return matched


def bucket_exists(s3_client: S3Client, bucket_name: str) -> bool:
    """Return True if the S3 bucket exists and is accessible.

    Raises:
        botocore.exceptions.ClientError on unexpected AWS API errors (not 404/403).
    """
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        return True
    except s3_client.exceptions.ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code in ("404", "NoSuchBucket"):
            return False
        if error_code == "403":
            # Bucket exists but caller lacks access; treat as not found for our purposes
            return False
        raise


def create_bucket(s3_client: S3Client, bucket_name: str, region: str, tags: dict[str, str]) -> None:
    """Calls S3:CreateBucket, and enable versioning, KMS encryption, and add tags.

    Raises:
        botocore.exceptions.ClientError on AWS API errors.
    """
    create_kwargs: dict[str, object] = {"Bucket": bucket_name}
    # us-east-1 does not accept a LocationConstraint
    if region != "us-east-1":
        create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}

    s3_client.create_bucket(**create_kwargs)  # type: ignore[arg-type]

    s3_client.put_bucket_versioning(
        Bucket=bucket_name,
        VersioningConfiguration={"Status": "Enabled"},
    )

    s3_client.put_bucket_encryption(
        Bucket=bucket_name,
        ServerSideEncryptionConfiguration={
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms"}}]
        },
    )

    tag_set: list[TagTypeDef] = [{"Key": k, "Value": v} for k, v in tags.items()]
    s3_client.put_bucket_tagging(Bucket=bucket_name, Tagging={"TagSet": tag_set})


def update_bucket_tags(s3_client: S3Client, bucket_name: str, tags: dict[str, str]) -> None:
    """Call S3:PutBucketTags on an existing S3 bucket.

    Raises:
        botocore.exceptions.ClientError on AWS API errors.
    """
    tag_set: list[TagTypeDef] = [{"Key": k, "Value": v} for k, v in tags.items()]
    s3_client.put_bucket_tagging(Bucket=bucket_name, Tagging={"TagSet": tag_set})


def list_top_level_prefixes(s3_client: S3Client, bucket_name: str) -> list[str]:
    """Paginates S3:ListObjectsV2 top-level prefixes, return the list of prefixes.

    Strips the trailing slash for each prefix.

    Raises:
        botocore.exceptions.ClientError on AWS API errors.
    """
    prefixes: list[str] = []
    paginator = s3_client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket_name, Delimiter="/"):
        for prefix_entry in page.get("CommonPrefixes", []):
            prefix = prefix_entry.get("Prefix", "")
            if prefix:
                # Strip trailing slash
                prefixes.append(prefix.rstrip("/"))

    return prefixes
