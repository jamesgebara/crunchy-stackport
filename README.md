# StackPort

Universal AWS resource browser for local emulators. Works with MiniStack, LocalStack, Moto, or any AWS-compatible endpoint.

- Browse and inspect resources across **35 AWS services**
- S3 file browser with folder navigation, search, pagination, and download
- Dashboard with service health, resource counts, and auto-refresh
- Single Docker image, zero AWS dependencies

## Quick Start

### Docker (recommended)

```bash
docker compose up -d
# Open http://localhost:8080
```

### Python

```bash
pip install .
AWS_ENDPOINT_URL=http://localhost:4566 stackport
```

Requires a running AWS-compatible emulator (MiniStack, LocalStack, Moto, etc.).

## Configuration

| Variable | Default | Description |
|---|---|---|
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | Target AWS endpoint |
| `AWS_REGION` | `us-east-1` | AWS region |
| `AWS_ACCESS_KEY_ID` | `test` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | `test` | AWS secret key |
| `STACKPORT_PORT` | `8080` | StackPort server port |
| `STACKPORT_SERVICES` | *(35 services)* | Comma-separated services to probe |

## Supported Services (35)

ACM, API Gateway, AppSync, Athena, CloudFormation, CloudFront, Cognito (IDP + Identity), DynamoDB, EC2, ECR, ECS, ElastiCache, EFS, ELB, EMR, EventBridge, Firehose, Glue, IAM, Kinesis, KMS, Lambda, CloudWatch Logs, CloudWatch Monitoring, RDS, Route 53, S3, Secrets Manager, SES, SNS, SQS, SSM, Step Functions, WAFv2

S3 has a dedicated file browser. All other services use the generic resource table with detail view.

## Development

```bash
# Backend
pip install -e .
AWS_ENDPOINT_URL=http://localhost:4566 python -m backend.main

# Frontend
cd ui && npm install && npm run dev

# Build UI for production
cd ui && npm run build
```

## License

MIT
