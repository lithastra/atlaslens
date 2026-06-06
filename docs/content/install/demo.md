# Try the demo

Explore a fully populated AtlasLens dashboard with synthetic data — no Atlassian instance or
credentials required.

## Prerequisites

- Docker with Compose v2

## Run it

```bash
git clone https://github.com/lithastra/atlaslens.git
cd atlaslens
docker compose -f docker-compose.demo.yml up --build
```

Then open **<http://localhost:8080>** and log in:

| Username | Password |
|----------|----------------|
| `admin`  | `atlaslens-demo` |

## What gets seeded

The demo stack brings up MongoDB, the API, and the dashboard, then runs a one-shot job that
loads:

- **~4,000 synthetic events** across Jira, Confluence, Bitbucket, and JSM
- **12 people** and **4 teams** (with memberships)
- A mix of **audit** (security) and **activity** (productivity) events spread over ~90 days

This populates every view — Overview, Productivity, Security, User Timeline, Work Items, and
Connector Health.

!!! tip "Re-seed or reset"
    The seed job runs with `--drop`, so bringing the stack up again refreshes the demo data.
    To wipe everything (including the database volume):

    ```bash
    docker compose -f docker-compose.demo.yml down -v
    ```

## Seed demo data into an existing install

If you already run AtlasLens (without Docker Compose), you can load the same synthetic data
with the CLI:

```bash
python -m atlaslens.cli.seed_demo            # ~4000 events over 90 days
python -m atlaslens.cli.seed_demo --events 8000 --days 120
python -m atlaslens.cli.seed_demo --drop     # clear demo data first
```

Every demo document id is prefixed (`demo-…`), so `--drop` removes only demo data.
