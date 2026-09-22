#!/usr/bin/env python3
"""Collects the facts the monthly model review is based on.

Reads models/slots.yaml and librechat.yaml, compares every model with the
live OpenRouter catalogue (public endpoint, no key needed) and prints a
Markdown report: vanished models, each slot with its current model and the
newer models of the same vendor (candidates, not decisions), and the endpoint
lists. It decides nothing: which candidate replaces which model is judged by
scripts/judge.py and by Claude in the model-check workflow under the rules in
CLAUDE.md, and by the owner when he reviews the pull request.

Usage: python scripts/check_models.py [--json out.json] [--update-prices]
  --update-prices  rewrites out_per_m in models/slots.yaml from the catalogue
                   (the file is edited line by line, comments survive).
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SLOTS_PATH = ROOT / "models" / "slots.yaml"
YAML_PATH = ROOT / "librechat" / "librechat.yaml"
CATALOGUE_URL = "https://openrouter.ai/api/v1/models"
# How many newer models per vendor to surface as candidates.
CANDIDATES_PER_VENDOR = 10


def per_million(price) -> float | None:
    try:
        return round(float(price) * 1_000_000, 4)
    except (TypeError, ValueError):
        return None


def fetch_catalogue() -> dict[str, dict]:
    req = urllib.request.Request(CATALOGUE_URL, headers={"User-Agent": "poly-mind-infra/model-check"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)["data"]
    return {m["id"]: m for m in data}


def describe(model_id: str, cat: dict[str, dict]) -> dict:
    m = cat.get(model_id)
    if m is None:
        return {"id": model_id, "exists": False}
    pricing = m.get("pricing") or {}
    return {
        "id": model_id,
        "exists": True,
        "name": m.get("name"),
        "created": datetime.fromtimestamp(m.get("created", 0), timezone.utc).date().isoformat(),
        "input_per_m": per_million(pricing.get("prompt")),
        "output_per_m": per_million(pricing.get("completion")),
        "context": m.get("context_length"),
    }


def update_prices(slots: dict, cat: dict[str, dict]) -> list[str]:
    """Rewrites out_per_m for every slot model whose price changed. Returns the changes."""
    lines = SLOTS_PATH.read_text(encoding="utf-8").split("\n")
    changes = []
    for vendor in slots["vendors"]:
        for category in slots["categories"]:
            for model in vendor.get(category) or []:
                m = cat.get(model["id"])
                if m is None:
                    continue
                new = per_million((m.get("pricing") or {}).get("completion"))
                if new is None or abs(float(model["out_per_m"]) - new) < 1e-9:
                    continue
                pattern = re.compile(rf"(id:\s*{re.escape(model['id'])}\b.*?out_per_m:\s*)([0-9.]+)")
                for i, line in enumerate(lines):
                    if pattern.search(line):
                        lines[i] = pattern.sub(rf"\g<1>{new:g}", line)
                        changes.append(f"{model['id']}: {model['out_per_m']} -> {new:g}")
                        break
    if changes:
        SLOTS_PATH.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return changes


def main() -> int:
    slots = yaml.safe_load(SLOTS_PATH.read_text(encoding="utf-8"))
    cfg = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    cat = fetch_catalogue()

    price_changes = update_prices(slots, cat) if "--update-prices" in sys.argv else []

    endpoints = {
        ep["name"]: list((ep.get("models") or {}).get("default") or [])
        for ep in (cfg.get("endpoints") or {}).get("custom") or []
    }
    slot_rows = []
    for vendor in slots["vendors"]:
        prefix = vendor["prefix"]
        for category in slots["categories"]:
            for model in vendor.get(category) or []:
                cur = describe(model["id"], cat)
                since = cat[model["id"]].get("created", 0) if cur["exists"] else 0
                newer = [c for c in cat.values() if c["id"].startswith(prefix) and c.get("created", 0) > since]
                newer.sort(key=lambda c: c.get("created", 0), reverse=True)
                slot_rows.append({
                    "slot": f"{vendor['name']}/{category}",
                    "presetId": model["presetId"],
                    "label": model["label"],
                    "out_per_m_in_file": model["out_per_m"],
                    "current": cur,
                    "candidates": [describe(c["id"], cat) for c in newer[:CANDIDATES_PER_VENDOR]],
                })
    used = sorted({m for ms in endpoints.values() for m in ms} | {r["current"]["id"] for r in slot_rows})
    info = {m: describe(m, cat) for m in used}

    report = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "catalogue_size": len(cat),
        "max_models": slots.get("max_models"),
        "slots": slot_rows,
        "endpoints": {name: [info[m] for m in ms] for name, ms in endpoints.items()},
        "missing": [m for m in used if not info[m]["exists"]],
        "price_changes": price_changes,
    }
    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    def row(d: dict) -> str:
        if not d["exists"]:
            return f"| `{d['id']}` | **MISSING from OpenRouter** | | | |"
        return f"| `{d['id']}` | {d['name']} | {d['created']} | {d['input_per_m']} / {d['output_per_m']} | {d['context']} |"

    print(f"# Model check {report['generated']}\n")
    print(f"OpenRouter catalogue: {len(cat)} models. Prices are USD per 1M tokens, input / output. "
          f"Cap: {report['max_models']} models, {len(slot_rows)} in use.\n")
    print("## Missing models (must be replaced)\n")
    print("\n".join(f"- `{m}`" for m in report["missing"]) or "None.")
    print("\n## Price changes written to slots.yaml\n")
    print("\n".join(f"- {c}" for c in price_changes) or "None.")
    print("\n## Slots\n")
    for r in slot_rows:
        print(f"### {r['slot']} - {r['label']}\n")
        print("| Model | Name | Released | Price in/out | Context |")
        print("|---|---|---|---|---|")
        print(row(r["current"]))
        if r["candidates"]:
            print(f"\nNewer from the same vendor (candidates, not decisions):\n")
            print("| Model | Name | Released | Price in/out | Context |")
            print("|---|---|---|---|---|")
            for d in r["candidates"]:
                print(row(d))
        else:
            print("\nNo newer model from this vendor.")
        print()
    for name, models in report["endpoints"].items():
        print(f"\n## Endpoint list: {name}\n")
        print("| Model | Name | Released | Price in/out | Context |")
        print("|---|---|---|---|---|")
        for d in models:
            print(row(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
