-- One-time database bootstrap, run as the admin user.
-- Locally: docker compose exec -T postgres psql -U postgres -d rag < db/init.sql
-- On RDS: run the same file from the EC2 instance with psql.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS rag;          -- document chunks + embeddings
CREATE SCHEMA IF NOT EXISTS agent_state;  -- LangGraph checkpoints
