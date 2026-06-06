# FAQ

## Do I need an Atlassian Guard / Access licence?

No. AtlasLens relies on product-level audit logs and activity APIs, which don't require Guard.
Two sources *are* Guard-gated — Bitbucket Cloud audit logs and Cloud sign-in events — and are
surfaced as unavailable rather than faked. See [Connectors](connectors.md).

## Does AtlasLens write anything back to Atlassian?

No. It only reads, using read-only API tokens. There is no write path to Atlassian.

## Where is my data stored?

In a MongoDB instance you control (bundled with the Helm chart by default, or external). For
APPI, run it on a Japan-based host. Events are retained for one year via a TTL index.

## How do I create the first user?

There is no signup page. Provision an admin with the CLI:

```bash
python -m atlaslens.cli.seed_admin --username admin
```

In Docker/Kubernetes, run it inside the backend container/pod — see the install guides.

## The dashboard loads but shows no data

The backend ingests on startup and then on a schedule. On a fresh install, either wait for the
first cycle or trigger one from **Connector Health → Sync now**. If a connector errors, check
its row on that page — a common cause is an API token missing the required read scope.

## The Group/team filter is missing

It only appears once at least one team has resolved members (`group_membership`). On a fresh
install this fills in after group sync runs and identities are resolved from ingested events —
run a sync and give it a cycle. See [Operations](operations.md).

## "Last sync" looks hours off / timestamps are wrong

AtlasLens stores UTC and renders in your local timezone. If you see a consistent offset, make
sure you're on a current build — datetimes are returned timezone-aware and event times are
normalised to UTC on ingest.

## Can I run it against Atlassian Data Center?

Not yet. This build targets Atlassian Cloud. The adapter layer is designed so Data Center
connectors can be added later without changing anything above it.

## How do I explore it without an Atlassian instance?

Use the [demo stack](install/demo.md) — it seeds synthetic data so every view is populated.
