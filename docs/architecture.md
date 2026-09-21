# Architecture

A description of the deployed system, written so it can be pasted into a diagramming
tool (or an LLM) to produce a diagram. Kept in sync by hand.

**Title:** RAG chatbot on AWS — document ingestion and question answering

**Region:** ap-southeast-2 (Sydney). Everything sits in one VPC, `10.0.0.0/16`, spanning
two Availability Zones.

## Containers / groupings

1. **Outside AWS:** a user's browser, and an external LLM API (OpenRouter).
2. **VPC → Public subnets** (`10.0.0.0/20` in AZ-a, `10.0.16.0/20` in AZ-b):
   - Application Load Balancer `rag-alb`, with an ACM certificate for `rag.aicruit.in`.
   - NAT instance (EC2 t4g.micro with a public IP), providing outbound internet for the
     private subnets.
3. **VPC → Private subnets** (`10.0.128.0/20`, `10.0.144.0/20`):
   - EC2 instance `rag-app` (c7i-flex.large) running **three Docker containers**: nginx
     serving a React SPA on port 3000, a FastAPI + LangGraph API on 8000, and Hugging
     Face TEI serving Qwen3-Embedding-0.6B on 8080.
   - RDS PostgreSQL 16 with pgvector, not publicly accessible. Two schemas: `rag`
     (table `chunks`, `vector(1024)` column, HNSW index) and `agent_state` (LangGraph
     conversation checkpoints).
   - Lambda function `rag-ingest`, deployed as a container image, attached to the VPC.
4. **AWS services outside the VPC:** S3 bucket `rag-docs-s3`, SQS queue `rag-ingest`
   with a dead-letter queue, Secrets Manager, Cognito user pool, ECR, CloudWatch Logs.
   Plus an S3 **gateway VPC endpoint** attached to the private route tables.

## Question path (solid lines)

1. Browser → ALB, HTTPS 443 (HTTP 80 redirects to 443).
2. ALB → nginx container, port 3000, for all paths except `/chat`, `/health`, `/ui*`.
3. ALB → API container, port 8000, for those three paths (path-based routing rule).
4. Browser → Cognito, directly, to sign in and receive a JWT.
5. API → Cognito JWKS endpoint, once, to cache public keys for verifying tokens.
6. API → TEI container, to embed the question.
7. API → RDS, port 5432 over TLS, for vector search and conversation state.
8. API → NAT instance → Internet Gateway → OpenRouter, to generate the answer.

## Ingestion path (dashed lines)

1. User/CLI uploads a PDF to the S3 bucket.
2. S3 event notification → SQS queue.
3. Lambda event source mapping polls the queue and invokes the function (batch size 2,
   max concurrency 2).
4. Lambda → S3 gateway endpoint → S3, to download the file.
5. Lambda → TEI on the EC2 instance, port 8080, to embed chunks.
6. Lambda → RDS, to upsert chunks.
7. After 3 failures, SQS moves the message to the dead-letter queue.

## Supporting edges (dotted)

- EC2 instance role `rag-ec2-role` → Secrets Manager (database password and LLM key)
  and ECR (image pulls).
- Lambda role `rag-lambda-role` → SQS, S3 and Secrets Manager.
- Both → CloudWatch Logs.

## Security groups (label them on the connections)

| Group | Inbound |
|---|---|
| `rag-alb-sg` | 443 and 80 from the internet |
| `rag-app-sg` | 8000 and 3000 from `rag-alb-sg`; 8080 from `rag-lambda-sg` |
| `rag-db-sg` | 5432 from `rag-app-sg` and `rag-lambda-sg` |
| `rag-lambda-sg` | none |

Outbound is the default (all traffic) everywhere.

## Points the diagram should make visually

- The ALB is the only internet-facing entry point.
- EC2, RDS and Lambda have no public IPs.
- Outbound traffic from private subnets goes only through the NAT instance.
- S3 traffic bypasses the NAT via the gateway endpoint.

## Known gaps (deliberate, deferred)

- The API connects to RDS as `postgres` with a password from Secrets Manager. The
  `rag_api` / `rag_ingest` roles exist with `rds_iam` granted but aren't used yet.
- No CloudWatch alarm on the dead-letter queue.
- Ingestion depends on the EC2 instance being up, since TEI runs there.
- Infrastructure was created by hand in the console, not with IaC.
