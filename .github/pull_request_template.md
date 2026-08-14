## New template: <app name>

- App website: <url>
- Docker image: <image:tag> (official / project-maintained / community — which?)

### Checklist

- [ ] `python3 scripts/validate.py` prints `OK`
- [ ] I deployed this template myself and reached the app's first-run screen
- [ ] `min_memory_mb` reflects real usage (checked with `docker stats`)
- [ ] Secrets use `"secret": true` with an empty default (auto-generated)
- [ ] Data-service ports (db/cache/queue) bind `"host_ip": "127.0.0.1"`

### Test notes

<!-- What you deployed on, first boot time, anything a reviewer should know -->
