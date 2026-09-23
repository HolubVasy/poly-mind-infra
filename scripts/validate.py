#!/usr/bin/env python3
"""Static checks for the LibreChat config, models/slots.yaml and presets.json.

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
SLOTS_PATH = ROOT / "models" / "slots.yaml"

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


def check_slots(endpoints: dict[str, dict]) -> None:
    """models/slots.yaml is where models are chosen; presets.json is generated from it."""
    slots = yaml.safe_load(SLOTS_PATH.read_text(encoding="utf-8"))
    endpoint = slots.get("endpoint")
    ep = endpoints.get(endpoint)
    if ep is None:
        errors.append(f"slots.yaml: endpoint {endpoint!r} is not in librechat.yaml")
        return
    listed = ((ep.get("models") or {}).get("default")) or []
    categories = list(slots.get("categories") or {})
    if not categories:
        errors.append("slots.yaml: no categories")
    seen: set[str] = set()
    for vendor in slots.get("vendors") or []:
        name = vendor.get("name") or "?"
        prefix = vendor.get("prefix") or ""
        if len(vendor.get("flagship") or []) > 1:
            errors.append(f"slots.yaml vendor {name!r}: {len(vendor['flagship'])} flagships - the flagship is ONE model")
        for key in vendor:
            if key not in ("name", "prefix", *categories):
                errors.append(f"slots.yaml vendor {name!r}: unknown key {key!r} (categories are {categories})")
        for cat in categories:
            for m in vendor.get(cat) or []:
                where = f"slots.yaml {name}/{cat} {m.get('id')!r}"
                for field in ("id", "presetId", "label", "line", "out_per_m"):
                    if m.get(field) in (None, ""):
                        errors.append(f"{where}: missing {field}")
                if m.get("presetId") in seen:
                    errors.append(f"{where}: presetId {m.get('presetId')} used twice")
                seen.add(m.get("presetId"))
                mid = str(m.get("id") or "")
                if mid not in listed:
                    errors.append(f"{where}: not in the models.default list of {endpoint!r}")
                if not mid.startswith(prefix):
                    errors.append(f"{where}: id does not start with the vendor prefix {prefix!r}")
                if m.get("line") and str(m["line"]) not in mid:
                    errors.append(f"{where}: line {m['line']!r} is not a part of the id")
                if "rank" in m and not (isinstance(m["rank"], int) and m["rank"] >= 1):
                    errors.append(f"{where}: rank must be a whole number from 1")
    lines = [str(m.get("line")) for v in slots.get("vendors") or [] for c in categories for m in v.get(c) or []]
    for dup in sorted({x for x in lines if lines.count(x) > 1}):
        errors.append(f"slots.yaml: line {dup!r} is used by more than one slot - helpers could not tell them apart")
    for h in slots.get("helpers") or []:
        where = f"slots.yaml helper {h.get('title')!r}"
        for field in ("presetId", "title", "slot"):
            if not h.get(field):
                errors.append(f"{where}: missing {field}")
        if "model" in h:
            errors.append(f"{where}: names a model id - use `slot: <line>` so the monthly refresh moves the button too")
        if h.get("slot") and str(h["slot"]) not in lines:
            errors.append(f"{where}: slot {h['slot']!r} is not the line of any model slot")
        if not (h.get("instructions") or h.get("instructions_file")):
            errors.append(f"{where}: needs instructions or instructions_file")
        if h.get("presetId") in seen:
            errors.append(f"{where}: presetId used twice")
        if h.get("instructions_file") and not (ROOT / h["instructions_file"]).exists():
            errors.append(f"{where}: {h['instructions_file']} does not exist")
    cap = int(slots.get("max_models") or 0)
    if cap and len(seen) > cap:
        errors.append(f"slots.yaml: {len(seen)} models, the cap is max_models: {cap} - replace, do not add")
    import build_presets
    try:
        generated = build_presets.render(build_presets.build(slots))
    except SystemExit as e:
        errors.append(f"build_presets.py cannot build from slots.yaml: {e}")
        return
    if generated != PRESETS_PATH.read_text(encoding="utf-8"):
        errors.append("presets.json is not what slots.yaml generates - edit slots.yaml, run scripts/build_presets.py")


def main() -> int:
    endpoints = load_endpoints()
    check_presets(endpoints)
    check_slots(endpoints)
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        return 1
    print(f"ok: {len(endpoints)} endpoints, presets consistent with librechat.yaml and slots.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
