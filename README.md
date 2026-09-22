# Panelica Docker App Templates

The official template catalog for [Panelica](https://panelica.com)'s **Docker Manager**.
Every app that appears in the panel's one-click app store is defined by a single JSON
file in [`templates/`](templates/) — and you can add your own.

**Contribute a template → it ships to every Panelica server in the next panel update, with your name on it.**

---

## How it works

```
templates/<slug>.json          you write this (one file per app)
        │
        ▼
CI validation                  schema check + security lint (automatic, on every PR)
        │
        ▼
Panelica team review + merge   humans approve every template
        │
        ▼
Release pipeline               JSON → seed → embedded into the next panelica-server release
        │
        ▼
Every Panelica server          the app appears in Docker Manager → App Store
```

Nothing is auto-deployed: a template only reaches customer servers after it has passed
CI **and** been reviewed and merged by the Panelica team, and only via a signed panel
release. Your PR can never touch anyone's server directly.

## Quick start: contribute a template in 10 minutes

1. **Fork** this repository.
2. **Copy an example** that matches your app's shape:
   - single container → [`templates/n8n.json`](templates/n8n.json)
   - app + database → [`templates/wordpress.json`](templates/wordpress.json)
   - full stack (app + db + cache + worker) → [`templates/chatwoot.json`](templates/chatwoot.json)
3. **Rename it** to `templates/<your-slug>.json` and fill in your values.
4. **Validate locally** (optional — CI runs the same check):
   ```bash
   pip install jsonschema && python3 scripts/validate.py
   ```
5. **Open a Pull Request.** CI reports any problems inline; fix and push until it's green.
6. A maintainer reviews and merges. Done — your app ships with the next panel release.

Add `"contributed_by": "your-github-username"` to get credited in the panel.

## Anatomy of a template

The minimal viable template — a single container with one port and one volume:

```json
{
  "slug": "uptime-kuma",
  "name": "Uptime Kuma",
  "description": "Self-hosted uptime monitoring with a beautiful status page",
  "image": "louislam/uptime-kuma",
  "default_tag": "1",
  "categories": ["monitoring"],
  "ports": [
    { "host": 3001, "container": 3001, "protocol": "tcp", "description": "Web UI" }
  ],
  "env_vars": [],
  "volumes": [
    { "source": "{{slug}}_data", "target": "/app/data", "description": "Monitor history" }
  ],
  "min_memory_mb": 256,
  "documentation_url": "https://github.com/louislam/uptime-kuma/wiki",
  "website_url": "https://uptime.kuma.pet"
}
```

That's genuinely all a simple app needs. The full field reference is below, and
[`schema/template.schema.json`](schema/template.schema.json) is the machine-readable
source of truth (most editors give you autocompletion if you add
`"$schema": "https://raw.githubusercontent.com/Panelica/docker-templates/main/schema/template.schema.json"`).

### Field reference

| Field | Required | What it does |
|---|---|---|
| `slug` | ✔ | Unique lowercase id. Must equal the filename. Containers are named after it. |
| `name`, `description` | ✔ | Shown on the app card in the panel. |
| `image`, `default_tag` | ✔ | Docker image (without tag) + tag. Prefer a pinned major version (`"16-alpine"`) over `latest` when the project tags releases. |
| `categories` | ✔ | 1–4 from the fixed list in the schema — powers the store's filter sidebar. |
| `ports` | ✔ | Suggested host ports. Panelica automatically remaps on conflict, so pick something sensible and don't worry about collisions. Data services must bind `"host_ip": "127.0.0.1"` (see Security rules). |
| `env_vars` | ✔ | Environment variables the user can edit before deploying. `"secret": true` + empty `default` = Panelica generates a strong random value and shows it in the credentials card. |
| `volumes` | ✔ | Named volumes only, prefixed `{{slug}}_`. Host paths are rejected. |
| `min_memory_mb` | ✔ | Honest minimum for the whole stack — the panel warns users on small servers. |
| `linked_services` | | Sidecar containers for multi-container apps — see below. |
| `entrypoint`, `command` | | Override the image's entrypoint/command (argv array). |
| `post_deploy_commands` | | One-time commands run *inside* the main container after start (init scripts). |
| `restart_policy` | | Default `unless-stopped`. |
| `cap_add`, `sysctls` | | Tightly whitelisted (see Security rules). Most apps need neither. |
| `post_install_notes` | | Text shown after deploy: "first boot takes 2 minutes", "create admin on first visit"… |
| `credential_patterns` | | The access card shown after deploy. `{{server_ip}}` and `{{env:VAR}}` placeholders resolve at runtime. |
| `documentation_url`, `docker_hub_url`, `website_url` | | Links on the app card. |
| `is_popular`, `sort_order` | | Store placement (maintainers may adjust these in review). |
| `contributed_by` | | Your GitHub username — credited in the panel. Required for community templates. |
| `tier` | | Set by maintainers in review: `community` (default — shown with a Community badge and your credit) or `official` (Panelica-maintained). Leave it out when contributing. |

### Placeholders

| Placeholder | Resolves to |
|---|---|
| `{{slug}}` | The template slug (used in volume names and container hostnames) |
| `{{server_ip}}` | The server's public IP at deploy time |
| `{{domain}}` | The domain the user links to the app (when they do) |
| `{{env:VAR}}` | The resolved value of env var `VAR` — including auto-generated secrets (only valid inside `credential_patterns`) |

## Multi-container apps (the "complex" case, demystified)

Real stacks need a database, a cache, sometimes a worker. In a template that is just
the `linked_services` array — one entry per sidecar. Each sidecar:

- is named `<slug>-<name_suffix>` and is **reachable at that hostname** from every
  container in the stack (they share a private network),
- can copy a secret from the main container with `"from_env"` — so the app and its
  database agree on a password that Panelica generated once.

Skeleton of [`templates/chatwoot.json`](templates/chatwoot.json) — a 4-container stack
(Rails web + PostgreSQL + Redis + Sidekiq worker) — reduced to its logic:

```jsonc
{
  "slug": "chatwoot",
  "image": "chatwoot/chatwoot",              // main container: the web app
  "env_vars": [
    { "key": "POSTGRES_HOST",     "default": "{{slug}}-db" },      // ← sidecar hostname
    { "key": "POSTGRES_PASSWORD", "default": "", "secret": true }, // ← auto-generated once
    { "key": "REDIS_URL",         "default": "redis://{{slug}}-cache:6379" }
  ],
  "linked_services": [
    { "name_suffix": "db",    "image": "pgvector/pgvector:pg16",
      "env_vars": [ { "key": "POSTGRES_PASSWORD", "from_env": "POSTGRES_PASSWORD" } ] },
    { "name_suffix": "cache", "image": "redis:alpine" },
    { "name_suffix": "sidekiq", "image": "chatwoot/chatwoot",
      "command": "[\"docker/entrypoints/rails.sh\", \"sh\", \"-c\", \"bundle exec sidekiq\"]" }
  ]
}
```

Read it top to bottom: the app points at `chatwoot-db` and `chatwoot-cache`; the `db`
sidecar receives **the same generated password** via `from_env`; the worker reuses the
app image with a different command. That is the entire mental model — if you can write
a `docker-compose.yml`, you can write this.

## Security rules (enforced by CI, not just documented)

These are hard rules — the linter rejects the PR, and review would too:

- **No `privileged`, no host PID/network mode, no devices.** Not accepted from
  community templates under any justification.
- **`cap_add`**: only `NET_ADMIN` and `SYS_NICE`. **`sysctls`**: only `net.*`.
- **No host path mounts.** Named volumes only, prefixed with `{{slug}}_`. Mount
  targets may not shadow sensitive paths (`/var/run/docker.sock`, `/proc`, `/etc`, …).
- **Data services bind to localhost.** Databases, caches and queues
  (5432/3306/6379/27017/9200/…) must set `"host_ip": "127.0.0.1"`. The panel asks the
  user for explicit confirmation before ever exposing such a port publicly.
- **Secrets are generated, never hardcoded.** `"secret": true` requires an empty
  `default`.
- **Images from trusted registries only**: Docker Hub, `ghcr.io`, `quay.io`,
  `lscr.io`, `public.ecr.aws`, `registry.gitlab.com`. Prefer official/project-owned
  images; review will ask about unknown publishers.

## What makes a good template (review checklist)

- You actually deployed it and it boots to a working first-run screen.
- `min_memory_mb` is honest (check `docker stats` after boot, add headroom).
- `post_install_notes` answers the first question a user will have.
- Secrets use auto-generation instead of `changeme`.
- The tag is a version the project actually maintains.

## FAQ

**Can I update an existing template?** Yes — version bumps, fixed env vars, better
notes are all welcome PRs to the existing file.

**When does my template reach users?** With the next `panelica-server` release after
merge (templates are embedded in the panel binary and delivered by the regular update
channel — typically days, not months).

**My app needs something the schema forbids.** Open an issue instead of a PR — if the
capability is safe to generalize we extend the schema and the engine together.

**Can I test my template before opening a PR?** Any Panelica server (a free Starter
license works) — Docker Manager → App Store → custom template import, or just ask in
the PR and a maintainer runs it.

## License

Templates in this repository are MIT-licensed. The applications they deploy keep their
own upstream licenses.
