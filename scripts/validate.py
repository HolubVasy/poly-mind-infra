#!/usr/bin/env python3
"""Static checks for the LibreChat config and the presets file.

Runs on every pull request (validate workflow), inside the monthly model
check, and before apply.sh touches the live server. Exit code 1 means the
change must not reach the server.

The most important rule is the one that broke the mother's presets on
2026-09-22: a preset whose model is not in its endpoint's `models.default`
list does not fail - LibreChat silently answers with the FIRST model of the
list instead. So every preset model must be listed, byte for byte.
"""
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "librechat" / "librechat.yaml"
PRESETS_PATH = ROOT / "presets" / "presets.json"

errors: list[str] = []
warnings: list[str] = []


def load_endpoints() -> dict[str, dict]:
    cfg = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    custom = (cfg.get("endpoints") or {}).get("custom") or []
    if not custom:
        errors.append("librechat.yaml: endpoints.custom is empty")
    endpoints: dict[str, dict] = {}
    for ep in custom:
        name = ep.get("name")
        if not name:
            errors.append("librechat.yaml: a custom endpoint has no name")
            continue
        if name in endpoints:
            errors.append(f"librechat.yaml: duplicate endpoint name {name!r}")
        api_key = str(ep.get("apiKey", ""))
        # Keys live in /opt/LibreChat/.env on the server, never in this repo.
        if not re.fullmatch(r"\$\{[A-Z0-9_]+\}", api_key) and api_key != "user_provided":
            errors.append(f"librechat.yaml: endpoint {name!r} has a literal apiKey - use ${{ENV_VAR}}")
        models = ((ep.get("models") or {}).get("default")) or []
        if not models:
            errors.append(f"librechat.yaml: endpoint {name!r} has no models.default")
        if len(models) != len(set(models)):
            errors.append(f"librechat.yaml: endpoint {name!r} lists a model twice")
        if "fetch" in ep:
            # LibreChat reads models.fetch; a `fetch:` next to `models:` is ignored.
            # That is why "Все" exposed only its default list on 2026-09-22
            # despite `fetch: true`. The lists are curated on purpose, so the
            # key is just noise here - flag it so nobody trusts it again.
            warnings.append(f"librechat.yaml: endpoint {name!r} has endpoint-level fetch, which LibreChat ignores")
        endpoints[name] = ep
    return endpoints


def check_presets(endpoints: dict[str, dict]) -> None:
    data = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    presets = data.get("presets")
    if not isinstance(presets, list) or not presets:
        errors.append("presets.json: 'presets' must be a non-empty list")
        return
    ids, titles = set(), set()
    for i, p in enumerate(presets):
        where = f"presets.json[{i}] {p.get('title')!r}"
        for field in ("presetId", "title", "endpoint", "model"):
            if not p.get(field):
                errors.append(f"{where}: missing {field}")
        if p.get("presetId") in ids:
            errors.append(f"{where}: duplicate presetId {p.get('presetId')}")
        if p.get("title") in titles:
            errors.append(f"{where}: duplicate title")
        ids.add(p.get("presetId"))
        titles.add(p.get("title"))
        ep = endpoints.get(p.get("endpoint"))
        if ep is None:
            errors.append(f"{where}: endpoint {p.get('endpoint')!r} is not in librechat.yaml")
            continue
        models = ((ep.get("models") or {}).get("default")) or []
        if p.get("model") not in models:
            errors.append(
                f"{where}: model {p.get('model')!r} is not in the models.default list of "
                f"{p.get('endpoint')!r} - LibreChat would silently answer with {models[0] if models else '?'!r}"
            )


def main() -> int:
    endpoints = load_endpoints()
    check_presets(endpoints)
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        return 1
    print(f"ok: {len(endpoints)} endpoints, presets consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
