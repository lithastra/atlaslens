# AtlasLens

A local, admin-only web dashboard that continuously pulls **audit** and **activity** data from your Atlassian Cloud suite — Jira, Confluence, Bitbucket, and Jira Service Management — normalises it into one store, and presents a unified view for filtering, trends, rankings, and forensic investigation.

## Features

- **Two ingestion pipelines** — security/forensics (audit logs) and productivity (content/activity) feeding one unified event store
- **Incremental sync** — cursor-based polling with idempotent upserts; no duplicates, no data loss windows
- **Cross-product investigation** — per-user timelines spanning all four Atlassian products
- **Filtering & aggregation** — by product, date, user, group, operation, category, severity
- **Work items view** — per-person list of tickets, PRs, and pages with deep links
- **Compliance exports** — CSV/PDF with integrity stamps (count, SHA-256, filter criteria, timestamp)
- **Field-level encryption** — email identifiers encrypted at rest (display names kept plaintext for query/aggregation; see [COMPLIANCE.md](COMPLIANCE.md))
- **1-year retention** — enforced by MongoDB TTL index

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, Motor (MongoDB async), Pydantic v2, httpx, APScheduler
- **Frontend:** React, TypeScript, Vite
- **Storage:** MongoDB (local/self-hosted via Docker)

## Quick Start

```bash
# Start MongoDB
docker compose up -d mongo

# Install backend
pip install -e ".[dev]"

# Provision an admin account
python -m atlaslens.cli.seed_admin --username admin

# Run the API server
uvicorn atlaslens.api.main:app --reload

# Run the frontend
cd frontend && npm install && npm run dev
```

Copy `.env.example` to `.env` and fill in your Atlassian credentials before running.

## Known Gaps (No Atlassian Guard)

This tool is designed for environments **without** an Atlassian Guard (Access) subscription. Two data sources are unavailable without Guard:

- **Bitbucket Cloud audit logs** — the audit-log API requires Guard. Bitbucket contributes *activity data only* (commits, PRs).
- **Cloud sign-in events** — authentication/login events require Guard. The Security view surfaces this gap explicitly.

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

This project uses the [Developer Certificate of Origin (DCO)](DCO). All commits must be signed off:

```bash
git commit -s -m "Your commit message"
```

## License

Licensed under the [Apache License, Version 2.0](LICENSE).

## Disclaimer

AtlasLens is **not affiliated with, endorsed by, or sponsored by Atlassian.**

Atlassian, Jira, Confluence, Bitbucket, Jira Service Management, and Atlassian Guard are trademarks or registered trademarks of Atlassian Pty Ltd. All product names, logos, and brands referenced in this project are property of their respective owners and are used solely for identification purposes.

This project does not bundle, embed, or redistribute any Atlassian software. It communicates with Atlassian products exclusively through their publicly documented REST APIs using credentials provided by the end user.
