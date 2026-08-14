# Contributing

Thank you for helping grow the Panelica app catalog!

## Adding a template

1. Fork → copy the closest example from `templates/` → rename to `templates/<slug>.json`.
2. Deploy it once yourself and confirm the app reaches a working first-run screen.
3. `pip install jsonschema && python3 scripts/validate.py` until it prints `OK`.
4. Open a PR using the template. One app per PR.

## Review

Every PR is validated by CI (schema + security lint + image existence) and then
reviewed by a Panelica maintainer. We look at: image trustworthiness, honest memory
requirements, secret handling, and first-boot experience. Only maintainers merge;
merged templates ship with the next panel release.

## Updating a template

PRs against existing files are welcome (new version tags, fixed env vars, better
post-install notes). Explain what you tested in the PR description.

## Ground rules

- Security rules in the README are non-negotiable; CI enforces most of them.
- Don't bundle multiple apps in one PR.
- Upstream apps must be publicly available and legally redistributable.
- Be excellent to each other in reviews.
