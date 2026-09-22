#!/usr/bin/env python3
"""JSON template → Panelica seed SQL converter (maintainers only, runs in the
panelica-server release pipeline — contributors never touch SQL).

Usage:  python3 scripts/convert_to_seed.py <slug> [migration_number]
Prints an idempotent INSERT ... ON CONFLICT (slug) DO UPDATE seed matching the
docker_app_templates schema. The generated file goes into backend/seeds/ and is
embedded into the panelica-server binary by the normal release build.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def q(s: str) -> str:
    """SQL single-quote escape."""
    return "'" + str(s).replace("'", "''") + "'"


def jq(obj) -> str:
    """JSON value → quoted ::jsonb literal."""
    return q(json.dumps(obj, ensure_ascii=False)) + "::jsonb"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    slug = sys.argv[1]
    data = json.loads((ROOT / "templates" / f"{slug}.json").read_text())

    cats = "ARRAY[" + ", ".join(q(c) for c in data["categories"]) + "]"
    command = json.dumps(data["command"]) if data.get("command") else ""
    ports = []
    for p in data.get("ports", []):
        p = dict(p)
        # host_ip travels inside the ports JSON; the engine understands ip:host:container
        ports.append(p)

    cols = {
        "slug": q(data["slug"]),
        "name": q(data["name"]),
        "description": q(data["description"]),
        "logo_url": q(data.get("logo_url", "")),
        "image": q(data["image"]),
        "default_tag": q(data["default_tag"]),
        "categories": cats,
        "ports": jq(ports),
        "env_vars": jq(data.get("env_vars", [])),
        "volumes": jq(data.get("volumes", [])),
        "linked_services": jq(data.get("linked_services", [])),
        "entrypoint": q(data.get("entrypoint", "")),
        "command": q(command),
        "post_deploy_commands": jq(data.get("post_deploy_commands", [])),
        "restart_policy": q(data.get("restart_policy", "unless-stopped")),
        "min_memory_mb": str(data["min_memory_mb"]),
        "cap_add": jq(data.get("cap_add", [])),
        "sysctls": jq(data.get("sysctls", {})),
        "privileged": "false",  # never settable from community templates
        "documentation_url": q(data.get("documentation_url", "")),
        "docker_hub_url": q(data.get("docker_hub_url", "")),
        "website_url": q(data.get("website_url", "")),
        "post_install_notes": q(data.get("post_install_notes", "")),
        "credential_patterns": jq(data.get("credential_patterns", [])),
        "tier": q(data.get("tier", "community")),
        "contributed_by": q(data.get("contributed_by", "")),
        "is_popular": "true" if data.get("is_popular") else "false",
        "sort_order": str(data.get("sort_order", 100)),
    }

    update_cols = [c for c in cols if c != "slug"]
    sql = (
        f"-- generated from docker-templates/templates/{slug}.json — do not edit by hand\n"
        f"INSERT INTO docker_app_templates (\n  " + ", ".join(cols) + "\n) VALUES (\n  "
        + ",\n  ".join(cols.values())
        + "\n) ON CONFLICT (slug) DO UPDATE SET\n  "
        + ",\n  ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        + ";\n"
    )
    print(sql)
    return 0


if __name__ == "__main__":
    sys.exit(main())
