# Kubernetes (Helm)

AtlasLens publishes a Helm chart **and** container images to GHCR on every release (all public
— no pull secrets needed).

| Artifact | Reference |
|----------|-----------|
| Chart | `oci://ghcr.io/lithastra/charts/atlaslens` |
| Backend image | `ghcr.io/lithastra/atlaslens-backend` |
| Frontend image | `ghcr.io/lithastra/atlaslens-frontend` |

## Prerequisites

- Kubernetes 1.23+ and Helm 3.x
- Read-only Atlassian API tokens and a Fernet encryption key (see
  [Configuration](../configuration.md))

## 1. Create a values file

Supply your config and secrets, and point the image repositories at GHCR:

```yaml title="atlaslens-values.yaml"
config:
  atlassianSite: "your-site"
  atlassianCloudId: "<cloud-id>"
  atlassianOrgId: "<org-id>"
  bitbucketWorkspace: "your-workspace"

secrets:
  atlassianEmail: "you@example.com"
  jwtSecret: "<random secret>"
  encryptionKey: "<fernet key>"
  jiraApiToken: "<token>"
  confluenceApiToken: "<token>"
  bitbucketApiToken: "<token>"

backend:
  image:
    repository: ghcr.io/lithastra/atlaslens-backend
frontend:
  image:
    repository: ghcr.io/lithastra/atlaslens-frontend
```

!!! warning "Never commit real tokens"
    Keep secrets out of version control. Either pass them at install time, use a values file
    you don't commit, or point `secrets.existingSecret` at a Secret you manage out-of-band.
    The image `tag` defaults to the chart's appVersion, so only the repositories need pointing
    at GHCR.

## 2. Install

```bash
helm upgrade --install atlaslens oci://ghcr.io/lithastra/charts/atlaslens --version 1.2.0 \
  --namespace atlaslens --create-namespace \
  -f atlaslens-values.yaml
```

## 3. Seed an admin

```bash
kubectl -n atlaslens rollout status deploy/atlaslens-backend
kubectl -n atlaslens exec deploy/atlaslens-backend -- \
  python -m atlaslens.cli.seed_admin --username admin
```

## 4. Reach the dashboard

The frontend Service defaults to **NodePort 30080**:

```bash
# via the node port
open http://<node-ip>:30080
# …or port-forward
kubectl -n atlaslens port-forward svc/atlaslens-frontend 8080:80
```

!!! note "CORS"
    `config.corsOrigins` defaults to `["http://localhost:30080"]`. If you reach the UI on a
    different host/port, set it to match or the browser will block API calls.

## Bundled MongoDB

The chart deploys a single-node MongoDB with a persistent volume by default. To use an external
or managed MongoDB instead, disable it and set the URI:

```yaml
mongodb:
  enabled: false
config:
  mongoUri: "mongodb://user:pass@mongo-host:27017"
```

See the [chart README](https://github.com/lithastra/atlaslens/tree/main/charts/atlaslens) for
the full list of values.
