# AtlasLens documentation site

Source for the documentation at **https://docs.atlaslens.lithastra.com**, built with
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/). Content lives in
[`content/`](content/); navigation and theme are configured in [`mkdocs.yml`](mkdocs.yml).

## Local development

```bash
pip install -r requirements.txt
mkdocs serve            # live-reload preview at http://localhost:8000
mkdocs build --strict   # production build into ./site (CI runs this)
```

## Deployment — Cloudflare Workers Builds

The site is deployed to Cloudflare directly from this repo (Git integration). Cloudflare builds
the MkDocs site and `npx wrangler deploy` serves `./site` as a static-assets Worker, configured
by [`wrangler.jsonc`](wrangler.jsonc). There is no GitHub Pages; the GitHub Action here only
runs a strict build check.

### One-time setup (Cloudflare dashboard → Workers & Pages → Create → connect Git)

| Setting | Value |
|---------|-------|
| Repository | `lithastra/atlaslens` |
| Root directory | `docs` |
| Build command | `pip install -r requirements.txt && mkdocs build` |
| Deploy command | `npx wrangler deploy` |
| Build variable | `PYTHON_VERSION` = `3.12` |

The build/deploy API token needs the **Workers Scripts: Edit** permission. The static output
directory (`./site`) comes from `wrangler.jsonc`, not a dashboard field.

### Custom domain

In the Worker → **Settings → Domains & Routes** → add `docs.atlaslens.lithastra.com`. Because
`lithastra.com` is already on Cloudflare, the DNS record and TLS certificate are created
automatically — no manual DNS entry needed.

> Each push to `main` that touches `docs/**` triggers a Cloudflare build.
