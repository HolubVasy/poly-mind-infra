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


ORDER = ["flagship", "frontier", "workhorse", "cheap"]
# A variant is not a line of its own: :batch, :free, :thinking, previews.
VARIANT = (":", "-preview", "-exp")


def rung_of(short_id: str, ladder: dict[str, list[str]]) -> str | None:
    """Same rule as validate.py: the longest matching rung word wins."""
    best = None
    for category, words in ladder.items():
        for w in words or []:
            if w in short_id and (best is None or len(w) > len(best[1])):
                best = (category, w)
    return best[0] if best else None


def shelf_notes(slots: dict, cat: dict[str, dict]) -> list[str]:
    """Sanity of the shelves, by price - the one objective signal there is.

    Categories are assigned by hand in slots.yaml and the monthly review only
    bumps versions inside a line, so nothing would otherwise notice that a
    vendor shuffled its line-up or launched a whole new line above our
    flagship. These notes go into the pull request for the owner to judge;
    the review never re-categorises on its own. Empty shelves are not
    reported: a vendor that sells no model of a rung legitimately has none.
    """
    notes = []
    for vendor in slots.get("vendors") or []:
        name, prefix = vendor["name"], vendor["prefix"]
        prices: dict[str, float] = {}
        ours: set[str] = set()
        for category in ORDER:
            models = vendor.get(category) or []
            ours |= {m["id"] for m in models}
            if models:
                prices[category] = max(float(m["out_per_m"]) for m in models)
        # the shelves must not cross: flagship >= frontier >= workhorse
        for higher, lower in (("flagship", "frontier"), ("frontier", "workhorse")):
            if higher in prices and lower in prices and prices[lower] > prices[higher]:
                notes.append(
                    f"{name}: полки разъехались - {lower} дороже, чем {higher} "
                    f"(${prices[lower]:g} против ${prices[higher]:g} за 1M). Посмотри, та ли это категория."
                )
        if not prices:
            continue
        ceiling = max(prices.values())
        # Only something RELEASED AFTER everything we run counts as news; an
        # old expensive model (o1-pro, Opus 4.1) is not a new line.
        newest_ours = max((cat[mid].get("created", 0) for mid in ours if mid in cat), default=0)
        above = []
        for m in cat.values():
            mid = m["id"]
            if not mid.startswith(prefix) or mid in ours or any(v in mid[len(prefix):] for v in VARIANT):
                continue
            if m.get("created", 0) <= newest_ours:
                continue
            out = per_million((m.get("pricing") or {}).get("completion"))
            if out is not None and out > ceiling:
                above.append((out, mid, m.get("name") or mid))
        for out, mid, title in sorted(above, reverse=True)[:3]:
            notes.append(
                f"{name}: вышла {title} (`{mid}`) дороже нашего верха - ${out:g} против ${ceiling:g} за 1M. "
                f"Похоже на новую линейку: если это новый флагман, поставь руками."
            )
        # A model newer than ours whose name fits no rung: a new line the
        # ladder does not know. Reported, never placed.
        ladder = vendor.get("ladder") or {}
        unknown = sorted(
            {m["id"] for m in cat.values()
             if m["id"].startswith(prefix) and m.get("created", 0) > newest_ours
             and not any(v in m["id"][len(prefix):] for v in VARIANT)
             and rung_of(m["id"][len(prefix):], ladder) is None})
        if unknown:
            notes.append(f"{name}: новые имена, которых нет в лестнице - {', '.join(f'`{u}`' for u in unknown[:5])}. "
                         f"Реши, какая это ступень, и допиши слово в ladder.")
    return notes


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
                ladder = vendor.get("ladder") or {}
                # A candidate is a newer model of the SAME rung of the vendor's
                # ladder: Opus 5 -> Opus 5.5, never Opus -> Sonnet.
                newer = [c for c in cat.values()
                         if c["id"].startswith(prefix) and c.get("created", 0) > since
                         and rung_of(c["id"][len(prefix):], ladder) == category
                         and not any(v in c["id"][len(prefix):] for v in VARIANT)]
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
        "shelves": shelf_notes(slots, cat),
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
    print("\n## Полки: что проверить руками (категории по цене)\n")
    print("\n".join(f"- {n}" for n in report["shelves"]) or "Порядок полок в норме, новых линеек дороже нашего верха нет.")
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
