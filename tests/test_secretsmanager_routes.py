"""Integration tests for Secrets Manager API routes."""

import os

os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4566")

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

CREATED = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
CHANGED = datetime(2025, 3, 20, 14, 0, 0, tzinfo=timezone.utc)


class TestListSecrets:
    @patch("backend.routes.secretsmanager.get_client")
    def test_list_secrets_empty(self, mock_get_client):
        mock_sm = MagicMock()
        mock_get_client.return_value = mock_sm
        paginator = MagicMock()
        mock_sm.get_paginator.return_value = paginator
        paginator.paginate.return_value = [{"SecretList": []}]

        resp = client.get("/api/secretsmanager/secrets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["secrets"] == []

    @patch("backend.routes.secretsmanager.get_client")
    def test_list_secrets_with_data(self, mock_get_client):
        mock_sm = MagicMock()
        mock_get_client.return_value = mock_sm
        paginator = MagicMock()
        mock_sm.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "SecretList": [
                    {
                        "Name": "prod/db-password",
                        "ARN": "arn:aws:secretsmanager:us-east-1:000:secret:prod/db-password-abc",
                        "Description": "Production database password",
                        "CreatedDate": CREATED,
                        "LastChangedDate": CHANGED,
                        "LastAccessedDate": None,
                        "RotationEnabled": False,
                        "Tags": [
                            {"Key": "env", "Value": "prod"},
                            {"Key": "team", "Value": "backend"},
                        ],
                    }
                ]
            }
        ]

        resp = client.get("/api/secretsmanager/secrets")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["secrets"]) == 1
        s = data["secrets"][0]
        assert s["name"] == "prod/db-password"
        assert s["arn"] == "arn:aws:secretsmanager:us-east-1:000:secret:prod/db-password-abc"
        assert s["description"] == "Production database password"
        assert s["createdDate"] == CREATED.isoformat()
        assert s["lastChangedDate"] == CHANGED.isoformat()
        assert s["lastAccessedDate"] is None
        assert s["rotationEnabled"] is False
        assert s["tags"] == {"env": "prod", "team": "backend"}

    @patch("backend.routes.secretsmanager.get_client")
    def test_list_secrets_no_tags(self, mock_get_client):
        mock_sm = MagicMock()
        mock_get_client.return_value = mock_sm
        paginator = MagicMock()
        mock_sm.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "SecretList": [
                    {
                        "Name": "my-secret",
                        "ARN": "arn:aws:secretsmanager:us-east-1:000:secret:my-secret-xyz",
                    }
                ]
            }
        ]

        resp = client.get("/api/secretsmanager/secrets")
        assert resp.status_code == 200
        s = resp.json()["secrets"][0]
        assert s["tags"] == {}
        assert s["description"] == ""
        assert s["rotationEnabled"] is False

    @patch("backend.routes.secretsmanager.get_client")
    def test_list_secrets_multiple_pages(self, mock_get_client):
        mock_sm = MagicMock()
        mock_get_client.return_value = mock_sm
        paginator = MagicMock()
        mock_sm.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {"SecretList": [{"Name": "secret-1", "ARN": "arn:1"}]},
            {"SecretList": [{"Name": "secret-2", "ARN": "arn:2"}]},
        ]

        resp = client.get("/api/secretsmanager/secrets")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["secrets"]) == 2
        assert data["secrets"][0]["name"] == "secret-1"
        assert data["secrets"][1]["name"] == "secret-2"

    @patch("backend.routes.secretsmanager.get_client")
    def test_list_secrets_rotation_enabled(self, mock_get_client):
        mock_sm = MagicMock()
        mock_get_client.return_value = mock_sm
        paginator = MagicMock()
        mock_sm.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "SecretList": [
                    {
                        "Name": "rotated-secret",
                        "ARN": "arn:rotated",
                        "RotationEnabled": True,
                    }
                ]
            }
        ]

        resp = client.get("/api/secretsmanager/secrets")
        assert resp.status_code == 200
        assert resp.json()["secrets"][0]["rotationEnabled"] is True


class TestGetSecretDetail:
    @patch("backend.routes.secretsmanager.get_client")
    def test_get_secret_with_string_value(self, mock_get_client):
        mock_sm = MagicMock()
        mock_get_client.return_value = mock_sm
        mock_sm.describe_secret.return_value = {
            "Name": "prod/db-password",
            "ARN": "arn:aws:secretsmanager:us-east-1:000:secret:prod/db-password-abc",
            "Description": "Production database password",
            "CreatedDate": CREATED,
            "LastChangedDate": CHANGED,
            "LastAccessedDate": None,
            "RotationEnabled": False,
            "RotationRules": None,
            "RotationLambdaARN": None,
            "DeletedDate": None,
            "Tags": [{"Key": "env", "Value": "prod"}],
        }
        mock_sm.get_secret_value.return_value = {
            "SecretString": '{"username":"admin","password":"s3cret"}',
            "VersionId": "ver-001",
            "VersionStages": ["AWSCURRENT"],
        }

        resp = client.get("/api/secretsmanager/secrets/prod%2Fdb-password")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "prod/db-password"
        assert data["description"] == "Production database password"
        assert data["secretValue"] == '{"username":"admin","password":"s3cret"}'
        assert data["secretBinary"] is None
        assert data["versionId"] == "ver-001"
        assert data["versionStages"] == ["AWSCURRENT"]
        assert data["tags"] == {"env": "prod"}
        assert data["createdDate"] == CREATED.isoformat()
        assert data["rotationEnabled"] is False

    @patch("backend.routes.secretsmanager.get_client")
    def test_get_secret_with_binary_value(self, mock_get_client):
        mock_sm = MagicMock()
        mock_get_client.return_value = mock_sm
        mock_sm.describe_secret.return_value = {
            "Name": "binary-secret",
            "ARN": "arn:binary",
            "Tags": [],
        }
        raw_bytes = b"\x00\x01\x02\x03\xff"
        mock_sm.get_secret_value.return_value = {
            "SecretBinary": raw_bytes,
            "VersionId": "ver-bin",
            "VersionStages": ["AWSCURRENT"],
        }

        resp = client.get("/api/secretsmanager/secrets/binary-secret")
        assert resp.status_code == 200
        data = resp.json()
        assert data["secretValue"] is None
        import base64
        assert data["secretBinary"] == base64.b64encode(raw_bytes).decode("utf-8")
        assert data["versionId"] == "ver-bin"

    @patch("backend.routes.secretsmanager.get_client")
    def test_get_secret_not_found(self, mock_get_client):
        mock_sm = MagicMock()
        mock_get_client.return_value = mock_sm
        mock_sm.exceptions.ResourceNotFoundException = type(
            "ResourceNotFoundException", (Exception,), {}
        )
        mock_sm.describe_secret.side_effect = (
            mock_sm.exceptions.ResourceNotFoundException()
        )

        resp = client.get("/api/secretsmanager/secrets/nonexistent")
        assert resp.status_code == 404

    @patch("backend.routes.secretsmanager.get_client")
    def test_get_secret_value_not_retrievable(self, mock_get_client):
        """When get_secret_value fails (e.g. pending deletion), metadata is still returned."""
        mock_sm = MagicMock()
        mock_get_client.return_value = mock_sm
        mock_sm.describe_secret.return_value = {
            "Name": "deleted-secret",
            "ARN": "arn:deleted",
            "DeletedDate": CHANGED,
            "Tags": [],
        }
        mock_sm.get_secret_value.side_effect = Exception("marked for deletion")

        resp = client.get("/api/secretsmanager/secrets/deleted-secret")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "deleted-secret"
        assert data["secretValue"] is None
        assert data["secretBinary"] is None
        assert data["versionId"] is None
        assert data["versionStages"] is None
        assert data["deletedDate"] == CHANGED.isoformat()

    @patch("backend.routes.secretsmanager.get_client")
    def test_get_secret_with_rotation(self, mock_get_client):
        mock_sm = MagicMock()
        mock_get_client.return_value = mock_sm
        mock_sm.describe_secret.return_value = {
            "Name": "rotated-secret",
            "ARN": "arn:rotated",
            "RotationEnabled": True,
            "RotationRules": {"AutomaticallyAfterDays": 30},
            "RotationLambdaARN": "arn:aws:lambda:us-east-1:000:function:rotate-fn",
            "Tags": [],
        }
        mock_sm.get_secret_value.return_value = {
            "SecretString": "rotated-value",
            "VersionId": "ver-rot",
            "VersionStages": ["AWSCURRENT"],
        }

        resp = client.get("/api/secretsmanager/secrets/rotated-secret")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rotationEnabled"] is True
        assert data["rotationRules"] == {"AutomaticallyAfterDays": 30}
        assert data["rotationLambdaARN"] == "arn:aws:lambda:us-east-1:000:function:rotate-fn"
        assert data["secretValue"] == "rotated-value"

    @patch("backend.routes.secretsmanager.get_client")
    def test_get_secret_plain_text_value(self, mock_get_client):
        mock_sm = MagicMock()
        mock_get_client.return_value = mock_sm
        mock_sm.describe_secret.return_value = {
            "Name": "api-key",
            "ARN": "arn:api-key",
            "Tags": [],
        }
        mock_sm.get_secret_value.return_value = {
            "SecretString": "sk-abc123def456",
            "VersionId": "ver-plain",
            "VersionStages": ["AWSCURRENT"],
        }

        resp = client.get("/api/secretsmanager/secrets/api-key")
        assert resp.status_code == 200
        data = resp.json()
        assert data["secretValue"] == "sk-abc123def456"
