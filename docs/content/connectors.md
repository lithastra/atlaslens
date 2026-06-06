# Connectors & data sources

AtlasLens ships one connector per Atlassian Cloud product. Each can contribute to the **audit**
pipeline, the **activity** pipeline, or both.

## Coverage

| Product | Audit (security) | Activity (productivity) |
|---------|------------------|--------------------------|
| **Jira** | ✅ audit records | ✅ issues + changelog, comments, worklogs |
| **Confluence** | ✅ audit | ✅ page/blogpost version history |
| **JSM** | ✅ audit (shares the Jira audit API) | ✅ requests, queues |
| **Bitbucket** | ⛔ unavailable (Guard) | ✅ commits, pull requests |

## Known gaps (surfaced, not faked)

AtlasLens shows missing sources explicitly in the UI rather than fabricating data.

!!! warning "Requires Atlassian Guard (Access)"
    - **Bitbucket Cloud audit logs** — the workspace audit-log API is a Guard/Access feature.
      Bitbucket therefore contributes *activity data only* (commits, pull requests).
    - **Cloud sign-in events** — authentication/login events are only available with Guard. The
      Security view surfaces this gap rather than hiding it.

!!! note "Out of scope"
    - **Data Center connectors** — this build targets Atlassian Cloud. The adapter layer leaves
      room to add Data Center later without touching anything above it.
    - **Org-events audit stream** — requires an Atlassian Organization API key (Bearer), which
      is not provisioned in this build.

## Authentication

Connectors authenticate with **read-only API tokens** scoped to the minimum needed to read
audit and activity data. AtlasLens never writes back to Atlassian. Provide credentials via the
variables in [Configuration](configuration.md).

## How a connector runs

Each connector implements a common interface with `fetch_audit()` and `fetch_activity()`
methods that yield raw events newer than the supplied cursor. The runner normalises each raw
event, resolves identity and groups, and upserts it — see [Architecture](architecture.md). Per
-connector health (last sync, cursor, errors) is visible on the **Connector Health** page and
described in [Operations](operations.md).

![Connector Health](assets/connector-health.png)
