from fastapi import APIRouter, HTTPException

from backend.aws_client import get_client
from backend.cache import cache
from backend.routes.stats import SERVICE_REGISTRY, _METHOD_KWARGS, _count_items

router = APIRouter()

# Maps (service, resource_type) -> (boto3_service, method, id_param, response_key)
# response_key=None means return the full response (minus ResponseMetadata)
DESCRIBE_REGISTRY: dict[tuple[str, str], tuple[str, str, str, str | None]] = {
    ("s3", "buckets"): ("s3", "list_objects_v2", "Bucket", "Contents"),
    ("dynamodb", "tables"): ("dynamodb", "describe_table", "TableName", "Table"),
    ("lambda", "functions"): ("lambda", "get_function", "FunctionName", None),
    ("sqs", "queues"): ("sqs", "get_queue_attributes", "QueueUrl", "Attributes"),
    ("secretsmanager", "secrets"): ("secretsmanager", "describe_secret", "SecretId", None),
    ("rds", "db_instances"): ("rds", "describe_db_instances", "DBInstanceIdentifier", "DBInstances"),
    ("rds", "db_clusters"): ("rds", "describe_db_clusters", "DBClusterIdentifier", "DBClusters"),
    ("sns", "topics"): ("sns", "get_topic_attributes", "TopicArn", "Attributes"),
    ("kinesis", "streams"): ("kinesis", "describe_stream", "StreamName", "StreamDescription"),
    ("logs", "log_groups"): ("logs", "describe_log_groups", "logGroupNamePrefix", "logGroups"),
    ("stepfunctions", "state_machines"): ("stepfunctions", "describe_state_machine", "stateMachineArn", None),
    ("ecr", "repositories"): ("ecr", "describe_repositories", "repositoryNames", "repositories"),
    ("acm", "certificates"): ("acm", "describe_certificate", "CertificateArn", "Certificate"),
    ("kms", "keys"): ("kms", "describe_key", "KeyId", "KeyMetadata"),
    ("route53", "hosted_zones"): ("route53", "get_hosted_zone", "Id", "HostedZone"),
    ("cloudformation", "stacks"): ("cloudformation", "describe_stacks", "StackName", "Stacks"),
    ("ec2", "instances"): ("ec2", "describe_instances", "InstanceIds", "Reservations"),
    ("ec2", "vpcs"): ("ec2", "describe_vpcs", "VpcIds", "Vpcs"),
    ("elasticache", "cache_clusters"): ("elasticache", "describe_cache_clusters", "CacheClusterId", None),
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
    "SubnetId",
    "GroupId",
    "VolumeId",
    "HostedZoneId",
    "Id",
    "KeyId",
    "StackName",
    "stateMachineArn",
    "DBInstanceIdentifier",
    "DBClusterIdentifier",
    "clusterArn",
    "CertificateArn",
    "repositoryName",
    "CacheClusterId",
    "DeliveryStreamName",
    "WorkGroupName",
    "ApiId",
    "UserPoolId",
    "IdentityPoolId",
    "LoadBalancerArn",
    "FileSystemId",
    "AlarmName",
    "DashboardName",
    "CrawlerName",
    "DatabaseName",
    "DistributionId",
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
            kwargs = _METHOD_KWARGS.get((boto3_service, method_name), {})
            resp = method(**kwargs)
            items = resp.get(response_key, [])
            # Handle nested structures (e.g., cloudfront DistributionList.Items)
            if isinstance(items, dict) and "Items" in items:
                items = items.get("Items", []) or []
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

    # Some APIs take list parameters (e.g., InstanceIds, VpcIds)
    _LIST_PARAMS = {"InstanceIds", "VpcIds", "SubnetIds", "GroupIds", "VolumeIds", "repositoryNames"}

    try:
        client = get_client(boto3_service)
        method = getattr(client, method_name)
        if id_param in _LIST_PARAMS:
            resp = method(**{id_param: [res_id]})
        else:
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
