# Docker Compose

Run the full stack — MongoDB, the FastAPI backend, and the React dashboard — locally against
your own Atlassian Cloud.

## Prerequisites

- Docker with Compose v2
- Read-only Atlassian API tokens (see [Configuration](../configuration.md))

## 1. Configure

Copy the example environment file and fill in your Atlassian credentials and secrets:

```bash
cp .env.example .env
$EDITOR .env
```

At minimum set `ATLASLENS_ATLASSIAN_CLOUD_ID`, `ATLASLENS_ATLASSIAN_EMAIL`, the per-product API
tokens, `ATLASLENS_JWT_SECRET`, and `ATLASLENS_ENCRYPTION_KEY`. See
[Configuration](../configuration.md) for the full list.

## 2. Start

```bash
docker compose up --build
```

This starts three services:

| Service | Purpose | Port |
|---------|---------|------|
| `mongo` | Event store | 27017 |
| `atlaslens-backend` | FastAPI API + scheduler | 8000 |
| `frontend` | React dashboard (nginx) | 80 |

!!! note "Service name matters"
    The frontend image's nginx proxies the API to `http://atlaslens-backend:8000`, so the
    backend service is named `atlaslens-backend`. Keep that name if you customise the compose
    file.

## 3. Seed an admin

There is no signup page by design — provision an admin from the CLI:

```bash
docker compose exec atlaslens-backend \
  python -m atlaslens.cli.seed_admin --username admin
```

## 4. Open the dashboard

Browse to **<http://localhost>** and log in with the admin you just created.

The backend runs an initial sync on startup and then on a schedule (default every 15 minutes).
You can also trigger one on demand from the **Connector Health** page — see
[Operations](../operations.md).
