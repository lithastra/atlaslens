# Architecture

AtlasLens is built as a layered stack with **two cooperating ingestion pipelines** feeding one
unified event store.

```
6 Presentation   React + TypeScript dashboard (filters, charts, tables, export) + login
5 API            FastAPI: auth, event search, aggregations, exports, health/sync control
4 Storage        MongoDB: events + identities + groups + sync_state + users
3 Normalise      RawEvent -> Unified Event; resolve identity; map groups; classify; UTC
2 Adapters       one connector per product (Cloud)
1 Sources        Jira / Confluence / Bitbucket / JSM
```

Everything above the adapter layer is deployment-agnostic.

## Two pipelines, one store

The key insight that shapes the design: **audit data and activity data come from different
APIs.**

- The **audit** pipeline (`pipeline: "audit"`, category `security`) pulls from each product's
  audit-log API: logins, permission changes, group membership changes, admin actions.
- The **activity** pipeline (`pipeline: "activity"`, category `content`) pulls from
  content/activity APIs: issues, pages, commits, pull requests, requests.

Both normalise into the same `events` collection, so a single query can span security and
productivity across all products.

## Incremental ingestion

Incrementality comes from **per-source watermarks + idempotent upserts**, not from the database:

- Each `(deployment, product, pipeline)` has a row in `sync_state` holding a **cursor** (last
  `occurred_at`).
- The runner pulls everything newer than the cursor, normalises it, and **upserts by `_id`**,
  so re-pulling an overlapping window never creates duplicates.
- On success it advances the cursor and records `last_success_at`; on failure it records
  `last_error` and does **not** advance — a failing connector never blocks the others.
- All timestamps are normalised to **UTC** on the way in.

See [Operations](operations.md) for the scheduler and on-demand sync.

## Data model

The heart of the system is the `events` collection. Each document carries a natural `_id`
(`<deployment>:<product>:<source_id>`) that makes ingestion idempotent, the normalised fields,
and the full original payload under `raw`.

```jsonc
{
  "_id": "cloud:jira:evt-90211",
  "occurred_at": "2026-04-12T09:14:33Z",   // UTC
  "product": "jira",                         // jira|confluence|bitbucket|jsm
  "pipeline": "audit",                        // audit|activity
  "actor_id": "person:0042",                  // resolved canonical identity
  "actor_raw": "5f8a…",                       // accountId
  "operation": "permission_changed",
  "category": "security",                     // security|content
  "severity": "high",                          // low|medium|high
  "object_type": "space",
  "object_ref": { "id": "ENG", "name": "Engineering", "container": null },
  "source_ip": "203.0.113.7",
  "raw": { /* original payload */ }
}
```

Supporting collections:

| Collection | Purpose |
|------------|---------|
| `sync_state` | Per-connector cursor, last success, last error |
| `identities` | Canonical person ↔ product accounts; encrypted emails |
| `canonical_groups` / `source_groups` / `group_map` | Group resolution |
| `group_membership` | Person ↔ team membership |
| `users` | AtlasLens admin accounts (salted password hashes) |

## Identity & group resolution

Events arrive keyed by an opaque account id (`actor_raw`). The normaliser resolves each to a
**canonical identity** (`actor_id`), so one person's activity can be followed across all
products. Groups are anchored on **Atlassian org groups** and mapped to canonical teams, which
powers the Group/team filter and team-level rankings.

## Storage & retention

A single small MongoDB instance handles the expected scale (~200 audited users → a few million
events per year). A **TTL index** on `occurred_at` enforces a one-year retention window, which
doubles as data minimisation.
