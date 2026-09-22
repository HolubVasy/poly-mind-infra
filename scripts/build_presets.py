#!/usr/bin/env python3
"""Generates presets/presets.json from models/slots.yaml.

Every model in slots.yaml becomes one preset. The title is assembled here:
    <icon> <label> · <colour> x<N>
    e.g.  🧠 Fable 5.1 · 🔴 x20
The category shows as its icon only, and the vendor is not repeated: LibreChat
prints the model id right after the title in the menu.
x<N> is the output price divided by price_unit, rounded; the colour follows N.
Nobody types a price marker: check_models.py refreshes out_per_m from
OpenRouter, this script turns it into the title.

The menu order is the `order` field LibreChat sorts by (owner's rule,
2026-09-22): category (top to bottom as in slots.yaml), then vendor in the
order the vendors are listed in slots.yaml, then - only when one vendor has
two models on one shelf - the dearer one first. The order changes only when
the owner changes the vendor list, never when a version or a price does.

Usage: python scripts/build_presets.py           # writes presets/presets.json
       python scripts/build_presets.py --check   # exit 1 if the file is stale
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SLOTS_PATH = ROOT / "models" / "slots.yaml"
PRESETS_PATH = ROOT / "presets" / "presets.json"

# Fields every preset carries besides the ones derived from slots.yaml.
PRESET_DEFAULTS = {
    "endpointType": "custom",
    "isArchived": False,
    "maxContextTokens": 900000,
    "resendFiles": True,
    "tags": [],
    "web_search": False,
}


def load_slots() -> dict:
    return yaml.safe_load(SLOTS_PATH.read_text(encoding="utf-8"))


def price_marker(out_per_m: float, slots: dict) -> tuple[int, str]:
    n = round(float(out_per_m) / float(slots["price_unit"]))
    for rule in slots["colours"]:
        if "max" not in rule or n <= rule["max"]:
            return n, rule["emoji"]
    return n, slots["colours"][-1]["emoji"]


def title_for(vendor: dict, category: str, model: dict, slots: dict) -> str:
    n, colour = price_marker(model["out_per_m"], slots)
    cat = slots["categories"][category]
    # Icon for the category, no word: LibreChat shows the model id right after
    # the title, so anything more than the label and the price is noise.
    return f"{cat['icon']} {model['label']} · {colour} x{n}"


def iter_models(slots: dict):
    """Menu order: category, then vendor as listed, then dearer first."""
    for category in slots["categories"]:
        for vendor in slots["vendors"]:
            models = sorted(vendor.get(category) or [], key=lambda m: -float(m["out_per_m"]))
            for model in models:
                yield vendor, category, model


def build(slots: dict) -> dict:
    presets = []
    for order, (vendor, category, model) in enumerate(iter_models(slots), start=1):
        presets.append({
            "presetId": model["presetId"],
            "endpoint": slots["endpoint"],
            "model": model["id"],
            "title": title_for(vendor, category, model, slots),
            "order": order,
            **PRESET_DEFAULTS,
        })
    return {"presets": presets}


def render(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    data = build(load_slots())
    text = render(data)
    if "--check" in sys.argv:
        current = PRESETS_PATH.read_text(encoding="utf-8") if PRESETS_PATH.exists() else ""
        if current != text:
            print("ERROR: presets/presets.json is not what models/slots.yaml generates - "
                  "edit slots.yaml and run scripts/build_presets.py")
            return 1
        print("ok: presets.json matches slots.yaml")
        return 0
    PRESETS_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {PRESETS_PATH.relative_to(ROOT)}: {len(data['presets'])} presets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
