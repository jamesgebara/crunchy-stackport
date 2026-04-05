from fastapi import APIRouter, HTTPException

from backend.aws_client import get_client
from backend.cache import cache
from backend.routes.stats import SERVICE_REGISTRY

router = APIRouter()

# Maps (service, resource_type) -> (boto3_service, method, id_param, response_key)
# response_key=None means return the full response (minus ResponseMetadata)
DESCRIBE_REGISTRY: dict[tuple[str, str], tuple[str, str, str, str | None]] = {
    ("s3", "buckets"): ("s3", "list_objects_v2", "Bucket", "Contents"),
    ("dynamodb", "tables"): ("dynamodb", "describe_table", "TableName", "Table"),
    ("lambda", "functions"): ("lambda", "get_function", "FunctionName", None),
    ("sqs", "queues"): ("sqs", "get_queue_attributes", "QueueUrl", "Attributes"),
    ("secretsmanager", "secrets"): ("secretsmanager", "describe_secret", "SecretId", None),
    ("rds", "instances"): ("rds", "describe_db_instances", "DBInstanceIdentifier", "DBInstances"),
}

# Known ID field names for extracting a resource identifier from list results
_ID_FIELDS = [
    "BucketName",
    "FunctionName",
    "TableName",
    "TopicArn",
    "QueueUrl",
    "RoleName",
    "UserName",
    "PolicyName",
    "Arn",
    "PolicyArn",
    "logGroupName",
    "Name",
    "SecretName",
    "StreamName",
    "RuleName",
    "InstanceId",
    "VpcId",
    "HostedZoneId",
    "Id",
    "KeyId",
    "StackName",
    "stateMachineArn",
    "DBInstanceIdentifier",
    "clusterArn",
]


def _extract_id(item) -> str:
    """Extract a usable ID from a list API result item."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for field in _ID_FIELDS:
            if field in item:
                return str(item[field])
        # Fallback: first string value
        for v in item.values():
            if isinstance(v, str):
                return v
    return str(item)


def _summarize_item(item) -> dict:
    """Create a summary dict from a list API result item."""
    if isinstance(item, str):
        return {"id": item}
    if isinstance(item, dict):
        summary = {"id": _extract_id(item)}
        for key, value in item.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                summary[key] = value
            elif hasattr(value, "isoformat"):
                summary[key] = value.isoformat()
        return summary
    return {"id": str(item)}


@router.get("/resources/{service}")
def list_resources(service: str):
    cache_key = f"resources:{service}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    registry_entries = SERVICE_REGISTRY.get(service)
    if not registry_entries:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service}")

    resources: dict[str, list[dict]] = {}
    for resource_type, boto3_service, method_name, response_key in registry_entries:
        try:
            client = get_client(boto3_service)
            method = getattr(client, method_name)
            resp = method()
            items = resp.get(response_key, [])
            resources[resource_type] = [_summarize_item(item) for item in items]
        except Exception:
            resources[resource_type] = []

    result = {"service": service, "resources": resources}
    cache.set(cache_key, result, ttl=5)
    return result


@router.get("/resources/{service}/{res_type}/{res_id:path}")
def get_resource_detail(service: str, res_type: str, res_id: str):
    cache_key = f"detail:{service}:{res_type}:{res_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    lookup = DESCRIBE_REGISTRY.get((service, res_type))
    if not lookup:
        raise HTTPException(
            status_code=404,
            detail=f"No detail lookup registered for {service}/{res_type}",
        )

    boto3_service, method_name, id_param, response_key = lookup

    try:
        client = get_client(boto3_service)
        method = getattr(client, method_name)
        resp = method(**{id_param: res_id})

        # Remove boto3 metadata
        resp.pop("ResponseMetadata", None)

        if response_key is not None:
            detail = resp.get(response_key, resp)
        else:
            detail = resp

        # Convert datetime objects for JSON serialization
        detail = _serialize(detail)

        result = {
            "service": service,
            "type": res_type,
            "id": res_id,
            "detail": detail,
        }
        cache.set(cache_key, result, ttl=5)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _serialize(obj):
    """Recursively convert non-JSON-serializable types."""
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return obj
