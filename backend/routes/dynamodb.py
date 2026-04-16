import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.aws_client import get_client
from backend.cache import cache

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_table_item_count(table_name: str) -> int:
    """Return item count for a table. Cached 30s."""
    cache_key = f"dynamodb:item_count:{table_name}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    dynamodb = get_client("dynamodb")
    try:
        resp = dynamodb.describe_table(TableName=table_name)
        item_count = resp["Table"].get("ItemCount", 0)
        cache.set(cache_key, item_count, ttl=30)
        return item_count
    except Exception:
        logger.debug("Failed to get item count for %s", table_name, exc_info=True)
        return 0


@router.get("/tables")
def list_tables():
    dynamodb = get_client("dynamodb")
    paginator = dynamodb.get_paginator("list_tables")
    table_names = []

    for page in paginator.paginate():
        table_names.extend(page.get("TableNames", []))

    tables = []
    for name in table_names:
        try:
            resp = dynamodb.describe_table(TableName=name)
            table = resp["Table"]
            item_count = table.get("ItemCount", 0)
            table_size = table.get("TableSizeBytes", 0)

            key_schema = table.get("KeySchema", [])
            partition_key = next((k["AttributeName"] for k in key_schema if k["KeyType"] == "HASH"), None)
            sort_key = next((k["AttributeName"] for k in key_schema if k["KeyType"] == "RANGE"), None)

            tables.append(
                {
                    "name": name,
                    "status": table.get("TableStatus", "UNKNOWN"),
                    "item_count": item_count,
                    "size_bytes": table_size,
                    "partition_key": partition_key,
                    "sort_key": sort_key,
                    "billing_mode": table.get("BillingModeSummary", {}).get("BillingMode", "PROVISIONED"),
                    "created": table.get("CreationDateTime").isoformat() if table.get("CreationDateTime") else None,
                }
            )
        except Exception:
            logger.debug("Failed to describe table %s", name, exc_info=True)
            continue

    return {"tables": tables}


@router.get("/tables/{name}")
def get_table_detail(name: str):
    dynamodb = get_client("dynamodb")

    try:
        resp = dynamodb.describe_table(TableName=name)
        table = resp["Table"]

        key_schema = table.get("KeySchema", [])
        attribute_defs = {attr["AttributeName"]: attr["AttributeType"] for attr in table.get("AttributeDefinitions", [])}

        partition_key = next((k["AttributeName"] for k in key_schema if k["KeyType"] == "HASH"), None)
        sort_key = next((k["AttributeName"] for k in key_schema if k["KeyType"] == "RANGE"), None)

        return {
            "name": name,
            "status": table.get("TableStatus", "UNKNOWN"),
            "item_count": table.get("ItemCount", 0),
            "size_bytes": table.get("TableSizeBytes", 0),
            "partition_key": partition_key,
            "partition_key_type": attribute_defs.get(partition_key) if partition_key else None,
            "sort_key": sort_key,
            "sort_key_type": attribute_defs.get(sort_key) if sort_key else None,
            "billing_mode": table.get("BillingModeSummary", {}).get("BillingMode", "PROVISIONED"),
            "created": table.get("CreationDateTime").isoformat() if table.get("CreationDateTime") else None,
            "attribute_definitions": attribute_defs,
            "key_schema": key_schema,
            "global_secondary_indexes": table.get("GlobalSecondaryIndexes", []),
            "local_secondary_indexes": table.get("LocalSecondaryIndexes", []),
        }
    except Exception as e:
        logger.error("Failed to get table detail for %s: %s", name, e, exc_info=True)
        return {"error": str(e)}


@router.get("/tables/{name}/items")
def scan_table(
    name: str,
    limit: int = Query(default=25, ge=1, le=100, description="Max items per page"),
    exclusive_start_key: str = Query(default=None, description="Base64 encoded last evaluated key for pagination"),
):
    dynamodb = get_client("dynamodb")

    scan_params: dict[str, Any] = {
        "TableName": name,
        "Limit": limit,
    }

    if exclusive_start_key:
        import base64
        import json

        try:
            decoded = base64.b64decode(exclusive_start_key).decode("utf-8")
            scan_params["ExclusiveStartKey"] = json.loads(decoded)
        except Exception:
            logger.debug("Invalid exclusive_start_key", exc_info=True)

    try:
        resp = dynamodb.scan(**scan_params)
        items = resp.get("Items", [])

        last_evaluated_key = resp.get("LastEvaluatedKey")
        next_token = None
        if last_evaluated_key:
            import base64
            import json

            next_token = base64.b64encode(json.dumps(last_evaluated_key).encode("utf-8")).decode("utf-8")

        return {
            "table": name,
            "items": items,
            "count": len(items),
            "scanned_count": resp.get("ScannedCount", len(items)),
            "next_token": next_token,
        }
    except Exception as e:
        logger.error("Failed to scan table %s: %s", name, e, exc_info=True)
        return {"error": str(e), "items": [], "count": 0}


class QueryRequest(BaseModel):
    partition_key_value: str
    sort_key_value: str | None = None
    sort_key_operator: str = "="  # =, <, <=, >, >=, BETWEEN, BEGINS_WITH
    limit: int = 25


@router.post("/tables/{name}/query")
def query_table(name: str, request: QueryRequest):
    dynamodb = get_client("dynamodb")

    try:
        # Get table key schema
        table_resp = dynamodb.describe_table(TableName=name)
        table = table_resp["Table"]
        key_schema = table.get("KeySchema", [])
        attribute_defs = {attr["AttributeName"]: attr["AttributeType"] for attr in table.get("AttributeDefinitions", [])}

        partition_key = next((k["AttributeName"] for k in key_schema if k["KeyType"] == "HASH"), None)
        sort_key = next((k["AttributeName"] for k in key_schema if k["KeyType"] == "RANGE"), None)

        if not partition_key:
            return {"error": "No partition key found in table schema", "items": [], "count": 0}

        partition_key_type = attribute_defs.get(partition_key, "S")

        # Build key condition expression
        key_condition = f"#{partition_key} = :pk"
        expression_attr_names = {f"#{partition_key}": partition_key}
        expression_attr_values = {":pk": {partition_key_type: request.partition_key_value}}

        if sort_key and request.sort_key_value:
            sort_key_type = attribute_defs.get(sort_key, "S")
            if request.sort_key_operator == "=":
                key_condition += f" AND #{sort_key} = :sk"
                expression_attr_values[":sk"] = {sort_key_type: request.sort_key_value}
            elif request.sort_key_operator in ("<", "<=", ">", ">="):
                key_condition += f" AND #{sort_key} {request.sort_key_operator} :sk"
                expression_attr_values[":sk"] = {sort_key_type: request.sort_key_value}
            elif request.sort_key_operator == "BEGINS_WITH":
                key_condition += f" AND begins_with(#{sort_key}, :sk)"
                expression_attr_values[":sk"] = {sort_key_type: request.sort_key_value}
            expression_attr_names[f"#{sort_key}"] = sort_key

        query_params = {
            "TableName": name,
            "KeyConditionExpression": key_condition,
            "ExpressionAttributeNames": expression_attr_names,
            "ExpressionAttributeValues": expression_attr_values,
            "Limit": request.limit,
        }

        resp = dynamodb.query(**query_params)
        items = resp.get("Items", [])

        return {
            "table": name,
            "items": items,
            "count": len(items),
            "scanned_count": resp.get("ScannedCount", len(items)),
        }
    except Exception as e:
        logger.error("Failed to query table %s: %s", name, e, exc_info=True)
        return {"error": str(e), "items": [], "count": 0}


class PutItemRequest(BaseModel):
    item: dict[str, Any]
    condition_expression: str | None = None


class DeleteItemRequest(BaseModel):
    key: dict[str, Any]


def _extract_key(table_schema: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    """Pull the primary key (partition + optional sort) out of a full item."""
    key_schema = table_schema.get("KeySchema", [])
    key_names = [k["AttributeName"] for k in key_schema]
    missing = [n for n in key_names if n not in item]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Item is missing required key attribute(s): {', '.join(missing)}",
        )
    return {n: item[n] for n in key_names}


@router.put("/tables/{name}/items")
def put_item(name: str, request: PutItemRequest):
    """Create or overwrite an item.

    Body: `{"item": {"attr": {"S|N|BOOL|...": value}}}` using DynamoDB attribute
    value format. Replaces any existing item with the same primary key.
    """
    dynamodb = get_client("dynamodb")

    if not request.item:
        raise HTTPException(status_code=400, detail="item is required")

    try:
        table_resp = dynamodb.describe_table(TableName=name)
        _extract_key(table_resp["Table"], request.item)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to describe table %s: %s", name, e, exc_info=True)
        raise HTTPException(status_code=404, detail=f"Table {name} not found")

    put_kwargs: dict[str, Any] = {"TableName": name, "Item": request.item}
    if request.condition_expression:
        put_kwargs["ConditionExpression"] = request.condition_expression

    try:
        dynamodb.put_item(**put_kwargs)
        cache.delete(f"dynamodb:item_count:{name}")
        return {"success": True, "message": "Item saved"}
    except dynamodb.exceptions.ConditionalCheckFailedException as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error("Failed to put item in %s: %s", name, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tables/{name}/items")
def delete_item(name: str, request: DeleteItemRequest):
    """Delete an item by its primary key.

    Body: `{"key": {"pk": {"S": "..."}, "sk": {"S": "..."}}}` — must contain all
    primary key attributes in DynamoDB attribute value format.
    """
    dynamodb = get_client("dynamodb")

    if not request.key:
        raise HTTPException(status_code=400, detail="key is required")

    try:
        dynamodb.delete_item(TableName=name, Key=request.key)
        cache.delete(f"dynamodb:item_count:{name}")
        return {"success": True, "message": "Item deleted"}
    except Exception as e:
        logger.error("Failed to delete item from %s: %s", name, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
