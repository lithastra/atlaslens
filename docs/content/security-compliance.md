# Security & compliance

AtlasLens is designed for **SOC 2**, **ISO 27001**, and **APPI (Japan)** contexts. This page
summarises the data-protection controls in the product and one documented deviation.

## Access model

- **Admin-only.** A login protects every data route (JWT-gated). There are no roles — any
  authenticated user is a full administrator.
- **No self-service registration.** Accounts are provisioned only via the `seed_admin` CLI,
  which stores a bcrypt salted hash (never plaintext).
- **The audited users are the subjects of the data, not AtlasLens users.** Only operators log
  in.

## Controls in place

| Control | Implementation |
|---------|----------------|
| 1-year retention | MongoDB TTL index on `events.occurred_at` (`expireAfterSeconds = 31_536_000`) |
| Data minimisation | TTL doubles as minimisation; only audit/activity fields are stored |
| Encryption key handling | `ATLASLENS_ENCRYPTION_KEY` injected from a secret; never committed |
| Email encryption at rest | Fernet `encrypt_field` applied to identity emails on ingest |
| Append-only events | Ingest is upsert-only; the only removal path is TTL expiry |
| Password storage | bcrypt salted hashes; no plaintext |
| Least-privilege credentials | Read-only Atlassian API tokens; never writes back to Atlassian |

## Documented deviation — display names in plaintext

The locked requirement is to encrypt personal identifiers (names, emails) at field level.
Identity **emails are field-encrypted**, but **`display_name` is stored in plaintext**.

**Why:** display names are on the hot path for analytics — the user pickers sort on them, event
rows resolve names, and `/aggregations/top` resolves names via a Mongo `$lookup` that cannot
decrypt mid-pipeline. Encrypting them would force name resolution and sorting out of the
database into application code.

**Compensating controls:**

- Deployment is **admin-only** and **local/self-hosted** (no public exposure).
- Data is kept on a **Japan-based host** per APPI residency.
- **Emails are not collected** in the current Cloud pipelines, so the highest-sensitivity
  identifier is absent rather than merely encrypted.
- Access requires authentication; events are append-only with enforced 1-year expiry.

**Revisit if** the deployment becomes multi-tenant or network-exposed, email ingestion is
added, or a stricter APPI interpretation applies — at which point encrypt `display_name` and
move name resolution/sorting into the application layer.

## Deployment-level responsibilities

Some controls are enforced by how you deploy, not by code:

- **APPI residency** — run MongoDB and backups on a Japan-based host.
- **Network exposure** — keep the dashboard on a trusted network; it is admin-only by design.
- **Atlassian Guard gaps** — Bitbucket audit logs and Cloud sign-in events require Guard and
  are surfaced as unavailable rather than fabricated. See [Connectors](connectors.md).
