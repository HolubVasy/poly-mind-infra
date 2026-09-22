#!/usr/bin/env python3
"""Collects the facts the monthly model review is based on.

Compares every model used in librechat.yaml and presets.json with the live
OpenRouter catalogue (public endpoint, no key needed) and prints a Markdown
report. It decides nothing: which model replaces which is judged by Claude in
the model-check workflow under the rules in CLAUDE.md, and by the owner when
he reviews the pull request.

Usage: python scripts/check_models.py [--json out.json]
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE_URL = "https://openrouter.ai/api/v1/models"
# How many newer models per vendor to surface as candidates.
CANDIDATES_PER_VENDOR = 8


def per_million(price: str | None) -> float | None:
    try:
        return round(float(price) * 1_000_000, 3)
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


def main() -> int:
    cfg = yaml.safe_load((ROOT / "librechat" / "librechat.yaml").read_text(encoding="utf-8"))
    presets = json.loads((ROOT / "presets" / "presets.json").read_text(encoding="utf-8"))["presets"]
    cat = fetch_catalogue()

    endpoints = {
        ep["name"]: list((ep.get("models") or {}).get("default") or [])
        for ep in (cfg.get("endpoints") or {}).get("custom") or []
    }
    used = sorted({m for ms in endpoints.values() for m in ms} | {p["model"] for p in presets})
    info = {m: describe(m, cat) for m in used}

    newest_used: dict[str, int] = {}
    for m in used:
        if m in cat:
            vendor = m.split("/")[0]
            newest_used[vendor] = max(newest_used.get(vendor, 0), cat[m].get("created", 0))
    candidates: dict[str, list[dict]] = {}
    for vendor, since in sorted(newest_used.items()):
        newer = [c for c in cat.values() if c["id"].startswith(vendor + "/") and c.get("created", 0) > since]
        newer.sort(key=lambda c: c.get("created", 0), reverse=True)
        candidates[vendor] = [describe(c["id"], cat) for c in newer[:CANDIDATES_PER_VENDOR]]

    report = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "catalogue_size": len(cat),
        "presets": [{"title": p["title"], "endpoint": p["endpoint"], **info[p["model"]]} for p in presets],
        "endpoints": {name: [info[m] for m in ms] for name, ms in endpoints.items()},
        "missing": [m for m in used if not info[m]["exists"]],
        "newer_by_vendor": candidates,
    }

    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    def row(d: dict) -> str:
        if not d["exists"]:
            return f"| `{d['id']}` | **MISSING from OpenRouter** | | | |"
        return f"| `{d['id']}` | {d['name']} | {d['created']} | {d['input_per_m']} / {d['output_per_m']} | {d['context']} |"

    print(f"# Model check {report['generated']}\n")
    print(f"OpenRouter catalogue: {len(cat)} models. Prices are USD per 1M tokens, input / output.\n")
    print("## Missing models (must be replaced)\n")
    print("\n".join(f"- `{m}`" for m in report["missing"]) or "None.")
    print("\n## Presets\n")
    print("| Title | Model | Name | Released | Price in/out | Context |")
    print("|---|---|---|---|---|---|")
    for p in report["presets"]:
        print(f"| {p['title']} " + row(p))
    for name, models in report["endpoints"].items():
        print(f"\n## Endpoint list: {name}\n")
        print("| Model | Name | Released | Price in/out | Context |")
        print("|---|---|---|---|---|")
        for d in models:
            print(row(d))
    print("\n## Newer models from the same vendors (candidates, not decisions)\n")
    for vendor, cands in candidates.items():
        if not cands:
            continue
        print(f"\n### {vendor}\n")
        print("| Model | Name | Released | Price in/out | Context |")
        print("|---|---|---|---|---|")
        for d in cands:
            print(row(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
