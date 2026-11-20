#!/usr/bin/env python3
"""Resolve and verify the image digests a template pins.

A tag is a moving pointer: whoever can push to a repository can make
`app/backend:1.2.3` mean something else tomorrow, and the next deployment of
that template would run it. A digest names the content itself, so a template
pins both: the tag stays for people to read, the digest decides what runs.

Usage:
  python3 scripts/resolve_digests.py            # verify (CI): digests present and current
  python3 scripts/resolve_digests.py --write    # fill in / refresh the digests
  python3 scripts/resolve_digests.py --write templates/n8n.json

Verify mode fails when a digest is missing, malformed, or no longer what the
tag resolves to. A failure is not automatically an attack - an upstream may
have rebuilt the same tag - but it is always a change nobody reviewed, so it
stops CI until a maintainer looks and refreshes the file on purpose.

Only the registries scripts/validate.py allows are resolvable here; anything
else is reported so a reviewer notices rather than silently skipped.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

# The media types a manifest request accepts. The index types come first: a
# multi-architecture tag must pin the index digest, not one platform's manifest,
# or arm64 hosts would be pinned to the amd64 image.
ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)

DEFAULT_REGISTRY = "registry-1.docker.io"


def split_ref(ref: str) -> tuple[str, str, str]:
    """"registry/name:tag" -> (registry host, repository, tag). Digests are dropped."""
    ref = ref.split("@", 1)[0]
    first, slash, remainder = ref.partition("/")
    # A registry host only looks like one when something follows it: in
    # "wordpress:7.1.5-php8.4-apache" the colon belongs to the tag.
    if slash and ("." in first or ":" in first or first == "localhost"):
        registry, rest = first, remainder
    else:
        registry, rest = DEFAULT_REGISTRY, ref
    name, _, tag = rest.partition(":")
    if registry == DEFAULT_REGISTRY and "/" not in name:
        name = "library/" + name  # bare "postgres" lives in the library namespace
    return registry, name, tag or "latest"


def _get(url: str, headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
    """GET with the response headers keyed in lower case - registries differ."""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e.read() or b""


def _bearer(challenge: str, registry: str, name: str) -> str | None:
    """Token for the realm a 401 points at (Docker Hub, ghcr.io, quay.io, …)."""
    realm = re.search(r'realm="([^"]+)"', challenge)
    if not realm:
        return None
    service = re.search(r'service="([^"]+)"', challenge)
    url = f"{realm.group(1)}?scope=repository:{name}:pull"
    if service:
        url += f"&service={service.group(1)}"
    status, _, body = _get(url, {})
    if status != 200:
        return None
    data = json.loads(body or b"{}")
    return data.get("token") or data.get("access_token")


def resolve(ref: str) -> tuple[str | None, str | None]:
    """The digest a reference's tag resolves to right now, or (None, reason)."""
    registry, name, tag = split_ref(ref)
    url = f"https://{registry}/v2/{name}/manifests/{tag}"
    headers = {"Accept": ACCEPT, "User-Agent": "panelica-docker-templates"}

    status, resp, _ = _get(url, headers)
    if status == 401:
        token = _bearer(resp.get("www-authenticate", ""), registry, name)
        if not token:
            return None, f"{ref}: the registry asked for a token this script could not get"
        headers["Authorization"] = f"Bearer {token}"
        status, resp, _ = _get(url, headers)

    if status != 200:
        return None, f"{ref}: the registry answered HTTP {status} for tag '{tag}'"

    digest = resp.get("docker-content-digest")
    if not digest or not DIGEST_RE.match(digest):
        return None, f"{ref}: the registry returned no usable digest ({digest!r})"
    return digest, None


def refs_of(data: dict) -> list[tuple[str, str, object, str]]:
    """Every image a template runs: (reference, digest field, holder, label)."""
    out: list[tuple[str, str, object, str]] = [
        (f"{data['image']}:{data['default_tag']}", "image_digest", data, "image")
    ]
    for svc in data.get("linked_services") or []:
        out.append((svc.get("image", ""), "digest", svc, f"linked_services[{svc.get('name_suffix')}]"))
    return out


def main() -> int:
    args = [a for a in sys.argv[1:]]
    write = "--write" in args
    files = [Path(a) for a in args if not a.startswith("--")] or sorted(TEMPLATES.glob("*.json"))

    problems: list[str] = []
    changed: list[str] = []

    for path in files:
        data = json.loads(path.read_text())
        dirty = False
        for ref, field, holder, label in refs_of(data):
            stored = holder.get(field)
            if not write and stored and not DIGEST_RE.match(str(stored)):
                problems.append(f"{path.name}: {label}: {field} is not a sha256 digest: {stored!r}")
                continue
            digest, err = resolve(ref)
            if err:
                problems.append(f"{path.name}: {label}: {err}")
                continue
            if stored == digest:
                continue
            if write:
                holder[field] = digest
                dirty = True
                changed.append(f"{path.name}: {label}: {ref} -> {digest}")
            elif not stored:
                problems.append(f"{path.name}: {label}: no {field}; {ref} is {digest}")
            else:
                problems.append(
                    f"{path.name}: {label}: {ref} now resolves to {digest}, the template pins {stored} "
                    "— review the change, then refresh with --write"
                )
        if dirty:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    for line in changed:
        print("  updated " + line)
    if problems:
        print("\n".join("  " + p for p in problems))
        print(f"FAIL — {len(problems)} digest problem(s)")
        return 1
    print(f"OK — digests current for {len(files)} template(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
