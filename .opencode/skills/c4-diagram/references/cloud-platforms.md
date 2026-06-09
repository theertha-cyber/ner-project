# Cloud Platform Service Mapping

When a cloud platform is confirmed, replace generic technology labels in the
DSL `technology` field and container descriptions with the actual managed
service names below. Load only the section for the confirmed platform.

## AWS

| Generic Role | AWS Managed Service | DSL Technology String |
|---|---|---|
| API Gateway | Amazon API Gateway / AWS ALB | `"Amazon API Gateway"` |
| Event Bus | Amazon EventBridge | `"Amazon EventBridge"` |
| Queue / DLQ | Amazon SQS | `"Amazon SQS"` |
| Cache | Amazon ElastiCache (Redis) | `"Amazon ElastiCache"` |
| Container Platform | Amazon EKS / ECS Fargate | `"Amazon EKS"` |
| Serverless | AWS Lambda | `"AWS Lambda"` |
| Relational DB | Amazon RDS / Aurora | `"Amazon Aurora (PostgreSQL)"` |
| NoSQL DB | Amazon DynamoDB | `"Amazon DynamoDB"` |
| Secrets | AWS Secrets Manager | `"AWS Secrets Manager"` |
| CDN | Amazon CloudFront | `"Amazon CloudFront"` |
| OTEL Collector | AWS Distro for OpenTelemetry | `"ADOT Collector"` |
| Log Store | Amazon CloudWatch Logs | `"Amazon CloudWatch Logs"` |
| Metrics Store | Amazon CloudWatch Metrics | `"Amazon CloudWatch Metrics"` |
| Trace Backend | AWS X-Ray | `"AWS X-Ray"` |
| Identity / Auth | Amazon Cognito | `"Amazon Cognito"` |
| Hub networking | AWS Transit Gateway | `"AWS Transit Gateway"` |

## Azure

| Generic Role | Azure Managed Service | DSL Technology String |
|---|---|---|
| API Gateway | Azure API Management | `"Azure API Management"` |
| Event Bus | Azure Event Grid | `"Azure Event Grid"` |
| Queue / DLQ | Azure Service Bus | `"Azure Service Bus"` |
| Cache | Azure Cache for Redis | `"Azure Cache for Redis"` |
| Container Platform | Azure Kubernetes Service | `"Azure Kubernetes Service (AKS)"` |
| Serverless | Azure Functions | `"Azure Functions"` |
| Relational DB | Azure SQL Database | `"Azure SQL Database"` |
| NoSQL DB | Azure Cosmos DB | `"Azure Cosmos DB"` |
| Secrets | Azure Key Vault | `"Azure Key Vault"` |
| CDN | Azure Front Door | `"Azure Front Door"` |
| OTEL Collector | Azure Monitor OpenTelemetry | `"Azure Monitor OTEL Exporter"` |
| Log Store | Azure Log Analytics Workspace | `"Azure Log Analytics"` |
| Metrics Store | Azure Monitor Metrics | `"Azure Monitor Metrics"` |
| Trace Backend | Azure Application Insights | `"Azure Application Insights"` |
| Identity / Auth | Microsoft Entra ID | `"Microsoft Entra ID"` |
| Hub networking | Azure Virtual WAN | `"Azure Virtual WAN"` |

## GCP

| Generic Role | GCP Managed Service | DSL Technology String |
|---|---|---|
| API Gateway | Google Cloud Apigee / API Gateway | `"Google Apigee"` |
| Event Bus | Google Cloud Eventarc | `"Google Cloud Eventarc"` |
| Queue / DLQ | Google Cloud Pub/Sub | `"Google Cloud Pub/Sub"` |
| Cache | Google Cloud Memorystore | `"Google Cloud Memorystore (Redis)"` |
| Container Platform | Google Kubernetes Engine | `"Google Kubernetes Engine (GKE)"` |
| Serverless | Google Cloud Functions / Cloud Run | `"Google Cloud Run"` |
| Relational DB | Cloud SQL / Cloud Spanner | `"Cloud SQL (PostgreSQL)"` |
| NoSQL DB | Firestore / Bigtable | `"Google Cloud Firestore"` |
| Secrets | Google Secret Manager | `"Google Secret Manager"` |
| CDN | Google Cloud CDN | `"Google Cloud CDN"` |
| OTEL Collector | Google Cloud Managed Collector | `"Google Cloud OTEL Collector"` |
| Log Store | Google Cloud Logging | `"Google Cloud Logging"` |
| Metrics Store | Google Cloud Monitoring | `"Google Cloud Monitoring"` |
| Trace Backend | Google Cloud Trace | `"Google Cloud Trace"` |
| Identity / Auth | Google Cloud Identity | `"Google Cloud Identity"` |
| Hub networking | GCP Network Connectivity Center | `"GCP Network Connectivity Center"` |

## Quick reference (all platforms)

| Pattern | AWS | Azure | GCP |
|---|---|---|---|
| API Gateway | API Gateway / ALB | API Management | Apigee / API Gateway |
| Event Bus | EventBridge | Event Grid | Eventarc |
| Queue / DLQ | SQS | Service Bus | Pub/Sub |
| Cache | ElastiCache | Azure Cache for Redis | Memorystore |
| Secrets | Secrets Manager | Key Vault | Secret Manager |
| Tracing | X-Ray | Application Insights | Cloud Trace |
| Container Platform | EKS / ECS Fargate | AKS / Container Apps | GKE / Cloud Run |
| Serverless | Lambda | Azure Functions | Cloud Functions / Cloud Run |
| Relational DB | RDS / Aurora | Azure SQL | Cloud SQL / Spanner |
| NoSQL DB | DynamoDB | Cosmos DB | Firestore |
| Hub Networking | Transit Gateway | Virtual WAN | Network Connectivity Center |
| CDN | CloudFront | Front Door | Cloud CDN |
| Identity | Cognito / SSO | Entra ID | Cloud Identity |
