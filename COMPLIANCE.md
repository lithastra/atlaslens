# Compliance Notes

AtlasLens targets **SOC 2**, **ISO 27001**, and **APPI (Japan)**. This document
records the data-protection controls in the codebase and one documented
deviation. Verified 2026-05-30.

## Controls in place

| Control | Implementation | Status |
|---|---|---|
| 1-year retention | MongoDB TTL index on `events.occurred_at`, `expireAfterSeconds = 31_536_000` | ✅ Verified live |
| Data minimisation | TTL doubles as minimisation; only audit/activity fields are stored | ✅ |
| Encryption key handling | `ATLASLENS_ENCRYPTION_KEY` injected from a secret (env / k8s Secret); never committed to source | ✅ |
| Email encryption at rest | `normalize/crypto.py` Fernet `encrypt_field` applied to identity emails on ingest | ✅ (path ready; see note 2) |
| Append-only events | Ingest is upsert-only; there is no edit/delete route — TTL expiry is the only removal path | ✅ |
| Password storage | bcrypt salted hashes (`api/auth.py`); no plaintext, no self-service registration | ✅ |
| Least-privilege credentials | Read-only scoped Atlassian API tokens; the tool never writes back to Atlassian | ✅ |
| Admin-only access | JWT-gated routes; accounts provisioned via `seed_admin` CLI only | ✅ |

## Documented deviation — display names stored in plaintext

**Locked requirement (§12):** encrypt personal identifiers (names, emails) at
field level.

**Actual behaviour:** identity **emails** are field-encrypted, but
**`identities.display_name` is stored in plaintext.**

**Rationale (accepted):** display names are on the hot path for the analytics
UX and cannot be encrypted at rest without breaking core functionality:

- the sidebar / Timeline / Work Items user pickers list and **alphabetically
  sort** names (`/filters` sorts on `display_name`);
- `/events` resolves `actor_display_name` per row;
- `/aggregations/top` resolves actor names via a Mongo `$lookup`, which **cannot
  decrypt mid-pipeline** — encryption would force name resolution and sorting
  out of the database and into application code.

**Compensating controls / residual-risk justification:**

- Deployment is **admin-only** and **local / self-hosted** (no public exposure);
  every operator is a full administrator.
- Data is kept on a **Japan-based host** per APPI residency.
- **Emails are not collected** at all in the current Cloud pipelines
  (0 of 186 identities carry an email), so the highest-sensitivity identifier is
  absent rather than merely encrypted.
- Access requires authentication; events are append-only with enforced 1-year
  expiry.

**Revisit if:** the deployment becomes multi-tenant or network-exposed, email
ingestion is added, or a stricter APPI interpretation is required. At that point
encrypt `display_name` and move name resolution + sorting to the application
layer (out of the `$lookup` aggregation).

## Deployment-level items (outside the codebase)

- **APPI residency:** MongoDB and backups must run on a Japan-based host. Enforced
  by deployment, not code.
- **Atlassian Guard gaps:** Bitbucket Cloud audit logs and Cloud sign-in events
  require Guard and are unavailable; the Security view surfaces these gaps rather
  than fabricating data. Org-events audit additionally requires an Organization
  API key (Bearer) that is not currently provisioned.
