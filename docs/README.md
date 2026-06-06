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

## Deployment — Cloudflare Pages

The site is deployed via **Cloudflare Pages (Git integration)** — Cloudflare builds the MkDocs
site directly from this repo on every push to `main` and serves the output. There is no GitHub
Pages; the GitHub Action here only runs a strict build check.

### One-time setup (Cloudflare dashboard → Workers & Pages → Create → Pages → connect Git)

| Setting | Value |
|---------|-------|
| Repository | `lithastra/atlaslens` |
| Production branch | `main` |
| Root directory *(Build → advanced)* | `docs` |
| Build command | `pip install -r requirements.txt && mkdocs build` |
| Build output directory | `site` |
| Build variable | `PYTHON_VERSION` = `3.12` |

### Custom domain

In the Pages project → **Custom domains** → add `docs.atlaslens.lithastra.com`. Because
`lithastra.com` is already on Cloudflare, the DNS record and TLS certificate are created
automatically — no manual DNS entry needed.

> Each push to `main` that touches `docs/**` triggers a Cloudflare build.
