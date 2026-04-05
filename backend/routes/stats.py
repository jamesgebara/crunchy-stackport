import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter

from backend.aws_client import get_client
from backend.cache import cache
from backend.config import STACKPORT_SERVICES

router = APIRouter()

SERVICE_REGISTRY: dict[str, list[tuple[str, str, str, str]]] = {
    "s3": [("buckets", "s3", "list_buckets", "Buckets")],
    "sqs": [("queues", "sqs", "list_queues", "QueueUrls")],
    "sns": [("topics", "sns", "list_topics", "Topics")],
    "dynamodb": [("tables", "dynamodb", "list_tables", "TableNames")],
    "lambda": [("functions", "lambda", "list_functions", "Functions")],
    "iam": [
        ("roles", "iam", "list_roles", "Roles"),
        ("users", "iam", "list_users", "Users"),
        ("policies", "iam", "list_policies", "Policies"),
    ],
    "logs": [("log_groups", "logs", "describe_log_groups", "logGroups")],
    "ssm": [("parameters", "ssm", "describe_parameters", "Parameters")],
    "secretsmanager": [("secrets", "secretsmanager", "list_secrets", "SecretList")],
    "kinesis": [("streams", "kinesis", "list_streams", "StreamNames")],
    "events": [("rules", "events", "list_rules", "Rules")],
    "ec2": [
        ("instances", "ec2", "describe_instances", "Reservations"),
        ("vpcs", "ec2", "describe_vpcs", "Vpcs"),
    ],
    "route53": [("hosted_zones", "route53", "list_hosted_zones", "HostedZones")],
    "kms": [("keys", "kms", "list_keys", "Keys")],
    "cloudformation": [("stacks", "cloudformation", "list_stacks", "StackSummaries")],
    "stepfunctions": [("state_machines", "stepfunctions", "list_state_machines", "stateMachines")],
    "rds": [("instances", "rds", "describe_db_instances", "DBInstances")],
    "ecs": [("clusters", "ecs", "list_clusters", "clusterArns")],
}

_start_time = time.time()


def _probe_service(service: str) -> tuple[str, dict]:
    """Probe a single service and return (service_name, result_dict)."""
    registry_entries = SERVICE_REGISTRY.get(service)
    if not registry_entries:
        return service, {"status": "unavailable", "resources": {}}

    resources: dict[str, int] = {}
    try:
        for resource_type, boto3_service, method_name, response_key in registry_entries:
            client = get_client(boto3_service)
            method = getattr(client, method_name)
            resp = method()
            items = resp.get(response_key, [])
            resources[resource_type] = len(items)
        return service, {"status": "available", "resources": resources}
    except Exception:
        return service, {"status": "unavailable", "resources": {}}


@router.get("/stats")
def get_stats():
    cached = cache.get("stats")
    if cached is not None:
        return cached

    enabled_services = [s.strip() for s in STACKPORT_SERVICES.split(",") if s.strip()]
    services: dict = {}
    total_resources = 0

    with ThreadPoolExecutor(max_workers=min(len(enabled_services), 10)) as executor:
        futures = {executor.submit(_probe_service, svc): svc for svc in enabled_services}
        for future in as_completed(futures):
            svc_name, result = future.result()
            services[svc_name] = result
            total_resources += sum(result["resources"].values())

    response = {
        "services": services,
        "total_resources": total_resources,
        "uptime_seconds": round(time.time() - _start_time, 1),
    }
    cache.set("stats", response, ttl=5)
    return response
