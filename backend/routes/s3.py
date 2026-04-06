import logging

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from backend.aws_client import get_client
from backend.cache import cache
from backend.config import AWS_REGION

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_bucket_stats(bucket_name: str) -> tuple[int, int]:
    """Return (object_count, total_size_bytes) for a bucket. Cached 30s."""
    cache_key = f"s3:bucket_stats:{bucket_name}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    s3 = get_client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    obj_count = 0
    total_size = 0

    try:
        for page in paginator.paginate(Bucket=bucket_name):
            for obj in page.get("Contents", []):
                obj_count += 1
                total_size += obj.get("Size", 0)
    except Exception:
        logger.debug("Failed to get bucket stats for %s", bucket_name, exc_info=True)

    result = (obj_count, total_size)
    cache.set(cache_key, result, ttl=30)
    return result


@router.get("/buckets")
def list_buckets():
    s3 = get_client("s3")
    response = s3.list_buckets()
    buckets = []

    for b in response.get("Buckets", []):
        name = b["Name"]
        obj_count, total_size = _get_bucket_stats(name)

        versioning = "Disabled"
        try:
            ver = s3.get_bucket_versioning(Bucket=name)
            versioning = ver.get("Status", "Disabled")
        except Exception:
            logger.debug("Failed to get versioning for %s", name, exc_info=True)

        encryption = "Disabled"
        try:
            s3.get_bucket_encryption(Bucket=name)
            encryption = "Enabled"
        except Exception:
            logger.debug("Failed to get encryption for %s", name, exc_info=True)

        tags: dict[str, str] = {}
        try:
            tag_resp = s3.get_bucket_tagging(Bucket=name)
            tags = {t["Key"]: t["Value"] for t in tag_resp.get("TagSet", [])}
        except Exception:
            logger.debug("Failed to get tags for %s", name, exc_info=True)

        buckets.append(
            {
                "name": name,
                "created": b["CreationDate"].isoformat(),
                "region": AWS_REGION,
                "object_count": obj_count,
                "total_size": total_size,
                "versioning": versioning,
                "encryption": encryption,
                "tags": tags,
            }
        )

    return {"buckets": buckets}


@router.get("/buckets/{name}/objects")
def list_objects(
    name: str,
    prefix: str = Query(default="", description="Key prefix filter"),
    delimiter: str = Query(default="/", description="Hierarchy delimiter"),
):
    s3 = get_client("s3")
    paginator = s3.get_paginator("list_objects_v2")

    folders: list[str] = []
    files: list[dict] = []

    paginate_params: dict = {"Bucket": name, "Prefix": prefix}
    if delimiter:
        paginate_params["Delimiter"] = delimiter

    for page in paginator.paginate(**paginate_params):
        for cp in page.get("CommonPrefixes", []):
            folders.append(cp["Prefix"])
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key == prefix:
                continue
            file_name = key[len(prefix) :] if prefix else key
            files.append(
                {
                    "key": key,
                    "name": file_name,
                    "size": obj["Size"],
                    "content_type": "application/octet-stream",
                    "etag": obj["ETag"].strip('"'),
                    "last_modified": obj["LastModified"].isoformat(),
                }
            )

    return {
        "bucket": name,
        "prefix": prefix,
        "delimiter": delimiter,
        "folders": folders,
        "files": files,
    }


@router.get("/buckets/{name}/objects/{key:path}")
def get_object_detail(
    name: str,
    key: str,
    download: int = Query(default=0, description="Set to 1 to download the object"),
):
    s3 = get_client("s3")

    if download == 1:
        resp = s3.get_object(Bucket=name, Key=key)
        filename = key.rsplit("/", 1)[-1] or key
        return StreamingResponse(
            resp["Body"],
            media_type=resp.get("ContentType", "application/octet-stream"),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    resp = s3.head_object(Bucket=name, Key=key)

    tags: dict[str, str] = {}
    try:
        tag_resp = s3.get_object_tagging(Bucket=name, Key=key)
        tags = {t["Key"]: t["Value"] for t in tag_resp.get("TagSet", [])}
    except Exception:
        logger.debug("Failed to get object tags for %s/%s", name, key, exc_info=True)

    return {
        "bucket": name,
        "key": key,
        "size": resp["ContentLength"],
        "content_type": resp.get("ContentType", "application/octet-stream"),
        "content_encoding": resp.get("ContentEncoding"),
        "etag": resp["ETag"].strip('"'),
        "last_modified": resp["LastModified"].isoformat(),
        "version_id": resp.get("VersionId"),
        "metadata": resp.get("Metadata", {}),
        "preserved_headers": {},
        "tags": tags,
    }
