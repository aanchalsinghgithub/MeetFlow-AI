# Deployment Guide

1. Provision PostgreSQL, Redis, ChromaDB, SMTP, and object storage.
2. Configure `.env` from `.env.example`.
3. Run migrations with `uv run alembic upgrade head`.
4. Build and deploy backend, worker, and frontend containers.
5. Configure Google and Microsoft OAuth callback URLs.
6. Use dedicated bot accounts for meeting attendance and recording consent flows.

## Local Docker

```powershell
copy .env.example .env
docker compose up --build
```

## Security Checklist

- Replace `JWT_SECRET_KEY`.
- Store API keys in a secret manager.
- Restrict CORS to production domains.
- Enforce organization-level meeting consent.
- Enable audit log retention.
- Add rate limiting at the gateway or ingress layer.
