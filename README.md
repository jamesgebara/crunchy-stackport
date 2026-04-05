# StackPort

Universal AWS resource browser for local emulators. Works with MiniStack, LocalStack, Moto, or any AWS-compatible endpoint.

- Browse S3 buckets, files, and folders with search and pagination
- Inspect resources across 18+ AWS services
- Download S3 objects directly
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

## Configuration

| Variable | Default | Description |
|---|---|---|
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | Target AWS endpoint |
| `AWS_REGION` | `us-east-1` | AWS region |
| `AWS_ACCESS_KEY_ID` | `test` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | `test` | AWS secret key |
| `STACKPORT_PORT` | `8080` | StackPort server port |
| `STACKPORT_SERVICES` | `s3,sqs,dynamodb,...` | Services to probe |

## Supported Services

S3, SQS, SNS, DynamoDB, Lambda, IAM, CloudWatch Logs, SSM, Secrets Manager, Kinesis, EventBridge, EC2, Route 53, KMS, CloudFormation, Step Functions, RDS, ECS

## Development

```bash
# Backend
pip install -e .
AWS_ENDPOINT_URL=http://localhost:4566 python -m backend.main

# Frontend
cd ui && npm install && npm run dev
```

## License

MIT
