# StackPort

[![CI](https://github.com/DaviReisVieira/stackport/actions/workflows/ci.yml/badge.svg)](https://github.com/DaviReisVieira/stackport/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/stackport)](https://pypi.org/project/stackport/)
[![Docker](https://img.shields.io/docker/pulls/davireis/stackport)](https://hub.docker.com/r/davireis/stackport)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Universal AWS resource browser for local emulators. Works with **LocalStack**, **MiniStack**, **Moto**, or any AWS-compatible endpoint.

<!-- TODO: Add screenshot here -->
<!-- ![StackPort Dashboard](docs/screenshot.png) -->

## Features

- Browse and inspect resources across **35 AWS services**
- S3 file browser with folder navigation, search, pagination, and download
- Dashboard with service health, resource counts, and auto-refresh
- Single Docker image, zero AWS dependencies

## Quick Start

### pip

```bash
pip install stackport
AWS_ENDPOINT_URL=http://localhost:4566 stackport
# Open http://localhost:8080
```

### Docker

```bash
docker run -p 8080:8080 -e AWS_ENDPOINT_URL=http://host.docker.internal:4566 davireis/stackport
```

### Docker Compose

```bash
curl -O https://raw.githubusercontent.com/DaviReisVieira/stackport/main/docker-compose.yml
docker compose up -d
# Open http://localhost:8080
```

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
git clone https://github.com/DaviReisVieira/stackport.git
cd stackport
pip install -e .
cd ui && npm install && npm run dev
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full details.

## License

MIT
