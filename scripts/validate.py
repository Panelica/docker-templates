#!/usr/bin/env python3
"""Panelica docker-templates validator.

Runs in CI on every pull request and locally via:  python3 scripts/validate.py

Two layers:
  1. JSON Schema validation (schema/template.schema.json)
  2. Security lint — rules the schema alone cannot express

Exit code 0 = all templates pass. Anything else = fail with a readable report.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schema" / "template.schema.json").read_text())

# Registries a template image may come from. Bare names ("postgres") and
# namespaced names ("chatwoot/chatwoot") resolve to Docker Hub.
ALLOWED_REGISTRY_PREFIXES = ("ghcr.io/", "quay.io/", "lscr.io/", "public.ecr.aws/", "registry.gitlab.com/")

DENIED_ENV_KEYS = {"DOCKER_HOST"}
# Mount SOURCES are already restricted to named volumes by the schema; targets are
# container-internal paths, so only genuinely dangerous targets are blocked here.
SENSITIVE_TARGET_PREFIXES = ("/var/run/docker.sock", "/proc", "/sys/fs/cgroup")

errors: list[str] = []


def err(name: str, msg: str) -> None:
    errors.append(f"  {name}: {msg}")


def validate_schema(name: str, data: dict) -> bool:
    try:
        import jsonschema
    except ImportError:
        print("ERROR: pip install jsonschema", file=sys.stderr)
        sys.exit(2)
    v = jsonschema.Draft202012Validator(SCHEMA)
    ok = True
    for e in sorted(v.iter_errors(data), key=lambda e: e.json_path):
        err(name, f"schema: {e.json_path}: {e.message}")
        ok = False
    return ok


def lint_ports(name: str, ports: list, where: str) -> None:
    for p in ports or []:
        # Well-known data-service container ports must not default to a public bind
        if p.get("container") in (3306, 5432, 6379, 27017, 9200, 11211, 5672) and p.get("host_ip") != "127.0.0.1":
            err(name, f"{where}: container port {p.get('container')} is a data service — set \"host_ip\": \"127.0.0.1\" (the panel lets the user expose it explicitly)")


def lint(name: str, data: dict) -> None:
    # Filename must match slug
    if data.get("slug") and name != f"{data['slug']}.json":
        err(name, f"filename must be {data['slug']}.json")

    # privileged is not even in the schema, but reject it loudly if someone adds it
    for forbidden in ("privileged", "pid_mode", "network_mode", "security_opt", "devices"):
        if forbidden in data:
            err(name, f"'{forbidden}' is not allowed in community templates")

    # Image registry allowlist
    img = data.get("image", "")
    if "/" in img and img.split("/")[0].count(".") > 0:  # has a registry host
        if not img.startswith(ALLOWED_REGISTRY_PREFIXES):
            err(name, f"image registry not allowed: {img} (allowed: Docker Hub, {', '.join(ALLOWED_REGISTRY_PREFIXES)})")

    # Volumes: schema already forces {{slug}}-prefixed named volumes; belt & braces
    for v in data.get("volumes", []) + [vv for ls in data.get("linked_services", []) for vv in ls.get("volumes", [])]:
        if v.get("source", "").startswith("/"):
            err(name, f"host path mount not allowed: {v['source']}")
        if any(v.get("target", "").startswith(t) for t in SENSITIVE_TARGET_PREFIXES):
            err(name, f"sensitive mount target not allowed: {v['target']}")

    # Env keys
    for e in data.get("env_vars", []):
        if e.get("key") in DENIED_ENV_KEYS:
            err(name, f"env key not allowed: {e['key']}")
        if e.get("secret") and e.get("default"):
            err(name, f"secret env '{e['key']}' must have an empty default (Panelica auto-generates secrets)")

    # from_env references must point at a real main-container env key
    main_keys = {e["key"] for e in data.get("env_vars", [])}
    for ls in data.get("linked_services", []):
        for e in ls.get("env_vars", []):
            if "from_env" in e and e["from_env"] not in main_keys:
                err(name, f"linked service '{ls.get('name_suffix')}': from_env '{e['from_env']}' does not exist in env_vars")
            if "value" in e and "from_env" in e:
                err(name, f"linked service '{ls.get('name_suffix')}': env '{e.get('key')}' sets both value and from_env")

    lint_ports(name, data.get("ports"), "ports")
    for ls in data.get("linked_services", []):
        lint_ports(name, ls.get("ports"), f"linked service '{ls.get('name_suffix')}'")

    # linked service command must be empty or a JSON argv array
    for ls in data.get("linked_services", []):
        cmd = ls.get("command", "")
        if cmd:
            try:
                parsed = json.loads(cmd)
                assert isinstance(parsed, list) and all(isinstance(x, str) for x in parsed)
            except Exception:
                err(name, f"linked service '{ls.get('name_suffix')}': command must be a JSON string array")


def main() -> int:
    files = sorted((ROOT / "templates").glob("*.json"))
    if not files:
        print("no templates found", file=sys.stderr)
        return 2
    slugs = set()
    for f in files:
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            err(f.name, f"invalid JSON: {e}")
            continue
        if validate_schema(f.name, data):
            lint(f.name, data)
        slug = data.get("slug")
        if slug in slugs:
            err(f.name, f"duplicate slug: {slug}")
        slugs.add(slug)

    if errors:
        print(f"FAIL — {len(errors)} problem(s):")
        print("\n".join(errors))
        return 1
    print(f"OK — {len(files)} template(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
