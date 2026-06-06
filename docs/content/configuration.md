# Configuration

AtlasLens is configured entirely through environment variables (prefixed `ATLASLENS_`). In
Kubernetes these map to Helm values; in Docker/local they come from `.env`.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ATLASLENS_MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `ATLASLENS_MONGO_DB` | `atlaslens` | Database name |
| `ATLASLENS_JWT_SECRET` | `change-me-in-production` | Signing key for login sessions — **set this** |
| `ATLASLENS_JWT_EXPIRE_MINUTES` | `480` | Session lifetime |
| `ATLASLENS_ENCRYPTION_KEY` | _(empty)_ | Fernet key for field-level encryption of personal identifiers |
| `ATLASLENS_ATLASSIAN_SITE` | _(empty)_ | Atlassian site/tenant name |
| `ATLASLENS_ATLASSIAN_CLOUD_ID` | _(empty)_ | Cloud ID used to build API gateway URLs |
| `ATLASLENS_ATLASSIAN_ORG_ID` | _(empty)_ | Organisation ID |
| `ATLASLENS_ATLASSIAN_EMAIL` | _(empty)_ | Account email for API token auth |
| `ATLASLENS_JIRA_API_TOKEN` | _(empty)_ | Jira (and JSM) API token |
| `ATLASLENS_CONFLUENCE_API_TOKEN` | _(empty)_ | Confluence API token |
| `ATLASLENS_BITBUCKET_API_TOKEN` | _(empty)_ | Bitbucket API token |
| `ATLASLENS_BITBUCKET_WORKSPACE` | _(empty)_ | Bitbucket workspace slug |
| `ATLASLENS_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed browser origins (JSON array) |
| `ATLASLENS_INGEST_INTERVAL_MINUTES` | `15` | Scheduler interval for incremental pulls |
| `ATLASLENS_REPORT_OUTPUT_DIR` | `reports` | Where generated reports are written |

A connector is only enabled when its credentials are present, so a fresh install with no tokens
simply ingests nothing (no errors).

## Generating secrets

A JWT secret can be any high-entropy string:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

The encryption key must be a valid Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

!!! danger "Keep the encryption key safe"
    Personal identifiers are encrypted at rest with this key. If you lose it, encrypted fields
    cannot be recovered; if you rotate it, previously encrypted values won't decrypt. Store it
    in a secret manager, never in source control.

## Helm values mapping

In the [Helm chart](install/kubernetes.md), non-secret settings live under `config.*` and
secrets under `secrets.*`:

| Helm value | Environment variable |
|------------|----------------------|
| `config.atlassianSite` | `ATLASLENS_ATLASSIAN_SITE` |
| `config.atlassianCloudId` | `ATLASLENS_ATLASSIAN_CLOUD_ID` |
| `config.atlassianOrgId` | `ATLASLENS_ATLASSIAN_ORG_ID` |
| `config.bitbucketWorkspace` | `ATLASLENS_BITBUCKET_WORKSPACE` |
| `config.corsOrigins` | `ATLASLENS_CORS_ORIGINS` |
| `config.ingestIntervalMinutes` | `ATLASLENS_INGEST_INTERVAL_MINUTES` |
| `secrets.jwtSecret` | `ATLASLENS_JWT_SECRET` |
| `secrets.encryptionKey` | `ATLASLENS_ENCRYPTION_KEY` |
| `secrets.atlassianEmail` | `ATLASLENS_ATLASSIAN_EMAIL` |
| `secrets.jiraApiToken` | `ATLASLENS_JIRA_API_TOKEN` |
| `secrets.confluenceApiToken` | `ATLASLENS_CONFLUENCE_API_TOKEN` |
| `secrets.bitbucketApiToken` | `ATLASLENS_BITBUCKET_API_TOKEN` |

## Least-privilege credentials

Request only **read** scopes needed to pull audit and activity data. AtlasLens never writes
back to Atlassian.
