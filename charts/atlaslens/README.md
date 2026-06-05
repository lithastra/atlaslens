# AtlasLens Helm chart

Deploys [AtlasLens](https://github.com/lithastra/atlaslens) — a local, admin-only audit &
activity dashboard for the Atlassian suite (Jira, Confluence, Bitbucket, JSM) — to Kubernetes:
the FastAPI backend, the React/nginx frontend, and an optional single-node MongoDB.

## Prerequisites

- Kubernetes 1.23+ and Helm 3.x
- Backend and frontend container images available to the cluster
  (`atlaslens-backend`, `atlaslens-frontend`). Build them from the repo root:
  ```bash
  docker build -t atlaslens-backend:1.0.0 -f backend/Dockerfile .
  docker build -t atlaslens-frontend:1.0.0 frontend/
  ```

## Install

```bash
# From GHCR (published on each v* tag by .github/workflows/release-chart.yml):
helm install atlaslens oci://ghcr.io/lithastra/charts/atlaslens \
  --version 1.0.0 \
  --namespace atlaslens --create-namespace \
  -f my-values.yaml

# Or from a checkout:
helm install atlaslens ./charts/atlaslens \
  --namespace atlaslens --create-namespace \
  -f my-values.yaml
```

> **Use the release name `atlaslens`.** The frontend image bakes its nginx upstream as
> `http://atlaslens-backend:8000` (see `frontend/nginx.conf`), which matches the backend
> Service only when the release is named `atlaslens`. A different release name produces a
> differently-prefixed Service and the dashboard cannot reach the API.

## Secrets — do not commit real tokens

The chart creates a Secret from `secrets.*` values **only as a convenience**. Never put real
Atlassian tokens in a committed values file. Either pass them at install time:

```bash
helm install atlaslens ./charts/atlaslens -n atlaslens --create-namespace \
  --set-string secrets.jwtSecret="$JWT" \
  --set-string secrets.encryptionKey="$FERNET_KEY" \
  --set-string secrets.atlassianEmail="$EMAIL" \
  --set-string secrets.jiraApiToken="$JIRA_TOKEN" \
  --set-string secrets.confluenceApiToken="$CONF_TOKEN" \
  --set-string secrets.bitbucketApiToken="$BB_TOKEN"
```

…or manage the Secret yourself and reference it:

```bash
kubectl -n atlaslens create secret generic atlaslens-secrets \
  --from-literal=jwt-secret=... --from-literal=encryption-key=... # etc.
helm install atlaslens ./charts/atlaslens -n atlaslens \
  --set secrets.existingSecret=atlaslens-secrets
```

Expected keys when using `existingSecret`: `jwt-secret`, `encryption-key`, `atlassian-email`,
`jira-api-token`, `confluence-api-token`, `bitbucket-api-token`, `atlassian-oauth-client-id`,
`atlassian-oauth-client-secret`.

## Post-install: seed an admin

There is no registration page (admin-only, DB-provisioned by design):

```bash
kubectl -n atlaslens exec deploy/atlaslens-backend -- \
  python -m atlaslens.cli.seed_admin --username admin
```

## Key values

| Key | Default | Description |
|---|---|---|
| `backend.image.repository` / `.tag` | `atlaslens-backend` / chart appVersion | Backend image |
| `frontend.image.repository` / `.tag` | `atlaslens-frontend` / chart appVersion | Frontend image |
| `frontend.service.type` | `NodePort` | `ClusterIP` \| `NodePort` \| `LoadBalancer` |
| `frontend.service.nodePort` | `30080` | NodePort when type is NodePort |
| `config.atlassianSite` / `atlassianCloudId` / `atlassianOrgId` / `bitbucketWorkspace` | `""` | Tenant identifiers (non-secret) |
| `config.corsOrigins` | `["http://localhost:30080"]` | API CORS allowlist (JSON array string) |
| `config.ingestIntervalMinutes` | `15` | Incremental ingestion interval |
| `config.mongoUri` | `""` | External Mongo URI; empty → in-chart MongoDB |
| `mongodb.enabled` | `true` | Deploy the bundled single-node MongoDB |
| `mongodb.persistence.size` | `2Gi` | PVC size for Mongo data |
| `secrets.existingSecret` | `""` | Use a pre-existing Secret instead of chart-managed |

See [`values.yaml`](./values.yaml) for the full list.

## Uninstall

```bash
helm uninstall atlaslens -n atlaslens
# PVCs from the StatefulSet are retained by default; delete them explicitly if desired:
kubectl -n atlaslens delete pvc -l app.kubernetes.io/instance=atlaslens
```
