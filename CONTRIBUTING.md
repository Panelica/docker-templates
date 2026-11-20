# Contributing

Thank you for helping grow the Panelica app catalog!

## Adding a template

1. Fork → copy the closest example from `templates/` → rename to `templates/<slug>.json`.
2. Deploy it once yourself and confirm the app reaches a working first-run screen.
3. `pip install jsonschema && python3 scripts/validate.py` until it prints `OK`.
4. Open a PR using the template. One app per PR.

## Review

Every PR is validated by CI (schema + security lint + digests still current) and then
reviewed by a Panelica maintainer. We look at: image trustworthiness, honest memory
requirements, secret handling, and first-boot experience. Only maintainers merge;
merged templates ship with the next panel release.

## Acceptance threshold

Templates are welcome for any publicly available app, including your own project.
Before a maintainer merges, the template must clear this bar:

- **Open-source license** — the upstream repository carries a recognised license
  file (MIT, Apache-2.0, GPL, AGPL, …). "Free to use" without a license is not enough.
- **Public, versioned image** — hosted on Docker Hub or one of the allowed
  registries, with release tags (`1.2.3`) and `default_tag` pinned to one of them.
  `latest` is not accepted: it moves, and a template is a promise about what
  runs on someone else's server.
- **Pinned by digest as well as by tag.** A tag is a pointer its publisher can
  move at any time, so every image in a template also carries the digest that
  tag resolved to when we reviewed it: `image_digest` for the main image, and
  `digest` on each linked service. Fill them in with

  ```bash
  python3 scripts/resolve_digests.py --write
  ```

  and commit the result. The panel deploys `repository:tag@digest`, so a
  deployment either runs exactly the reviewed content or fails — it never
  silently runs something else. CI re-resolves every tag on each pull request
  and push: if a tag has moved, the build stops until a maintainer looks at the
  change and refreshes the digest on purpose. When you submit a new version of
  a template, bump the tag and the digest together.
- **`linux/amd64` required, `linux/arm64` recommended** — Panelica runs on both.
- **English source text** — `description`, env descriptions and
  `post_install_notes` are written in English; the panel translates them into 31
  languages from that text.
- **Real deploy test** — a maintainer deploys the template on a clean VM exactly as
  the panel does (private network, named volumes, generated secrets) and confirms
  the first-run screen, a restart with data intact, and the measured memory
  against `min_memory_mb`. Crash loops in the image block the merge until the
  image is fixed upstream.

Merged templates are marked `tier: community` by the maintainer and appear in the
panel with a **Community** badge and your `contributed_by` credit, so users can
tell them from Panelica-maintained (`official`) templates. Maintainers may adjust
`is_popular` and `sort_order`.

## Updating a template

PRs against existing files are welcome (new version tags, fixed env vars, better
post-install notes). Explain what you tested in the PR description.

## Ground rules

- Security rules in the README are non-negotiable; CI enforces most of them.
- Don't bundle multiple apps in one PR.
- Upstream apps must be publicly available and legally redistributable.
- Be excellent to each other in reviews.
