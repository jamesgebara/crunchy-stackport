import functools

import boto3

from backend.config import (
    AWS_ACCESS_KEY_ID,
    AWS_ENDPOINT_URL,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
)


@functools.lru_cache(maxsize=64)
def get_client(service_name: str):
    """Return a boto3 client configured for the target AWS-compatible endpoint."""
    return boto3.client(
        service_name,
        endpoint_url=AWS_ENDPOINT_URL,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
