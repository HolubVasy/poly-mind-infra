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

The menu order is the `order` field LibreChat sorts by: category (top to
bottom as in slots.yaml), then the owner's `rank` inside the category
(1 = strongest, decided on the evidence in docs/), then vendor order, then
the dearer one first. A new version inherits its slot's rank.

It also writes the menu table at the end of docs/памятка.md (between the
menu:begin / menu:end markers): every button with its model and the same
price marker as the title, so the памятка's prices follow OpenRouter too.
The памятка is written first, because the helper «❓ Какую кнопку?» carries
it in its promptPrefix.

Usage: python scripts/build_presets.py           # writes presets.json and the памятка's menu
       python scripts/build_presets.py --check   # exit 1 if either is stale
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SLOTS_PATH = ROOT / "models" / "slots.yaml"
PRESETS_PATH = ROOT / "presets" / "presets.json"
MEMO_PATH = ROOT / "docs" / "памятка.md"
MENU_BEGIN = "<!-- menu:begin"
MENU_END = "<!-- menu:end -->"

# Fields every preset carries besides the ones derived from slots.yaml.
PRESET_DEFAULTS = {
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
    """Menu order: category, then the owner's rank (1 = strongest), then vendor
    as listed, then dearer first."""
    for category in slots["categories"]:
        rows = []
        for vi, vendor in enumerate(slots["vendors"]):
            for model in vendor.get(category) or []:
                rows.append((model.get("rank", 10 ** 6), vi, -float(model["out_per_m"]), vendor, model))
        rows.sort(key=lambda r: r[:3])
        for _rank, _vi, _price, vendor, model in rows:
            yield vendor, category, model


def with_common(slots: dict, text: str) -> str:
    """Every preset starts with the owner's one line that blocks the two
    failure modes seen in the tests: inventing, and guessing instead of
    saying "I do not know"."""
    common = (slots.get("common_prefix") or "").strip()
    return (common + "\n\n" + text).strip() if common else text.strip()


def direct_model(vendor: dict, model: dict) -> str:
    """The model's id on its vendor's own API: the OpenRouter id without the
    vendor prefix, dots to dashes (anthropic/claude-opus-5.5 gives
    claude-opus-5-5)."""
    return str(model["id"])[len(str(vendor["prefix"])):].replace(".", "-")


def route(slots: dict, vendor: dict, model: dict) -> dict:
    """Where a preset sends its requests. By default the custom endpoint of
    slots.yaml (OpenRouter), with the OpenRouter id. A vendor with its own
    `endpoint` runs on a built-in LibreChat endpoint, so the preset carries the
    vendor's own model id and no endpointType."""
    if "endpoint" in vendor:
        return {"endpoint": vendor["endpoint"], "model": direct_model(vendor, model)}
    return {"endpoint": slots["endpoint"], "endpointType": "custom", "model": model["id"]}


def slot_entry(slots: dict, line: str) -> tuple[dict, dict]:
    """The vendor and the model a helper runs on: the one slot whose `line` is
    `line`. Helpers name a slot, not an id, so a monthly replacement moves them
    too."""
    found = [(v, m) for v, _c, m in iter_models(slots) if str(m["line"]) == str(line)]
    if len(found) != 1:
        raise SystemExit(f"ERROR: helper slot {line!r} matches {len(found)} model slots, needs exactly one")
    return found[0]


def slot_model(slots: dict, line: str) -> dict:
    return slot_entry(slots, line)[1]


def context_cap(model: dict) -> dict:
    """A model's own maxContextTokens (slots.yaml `max_context`), when it has
    one; a helper gets the cap of the slot it runs on."""
    return {"maxContextTokens": int(model["max_context"])} if "max_context" in model else {}


def helper_presets(slots: dict) -> list[dict]:
    """Buttons with a procedure instead of a model choice: a model and
    instructions baked in, so the rule lives in the button. The model is
    whatever the named slot holds today."""
    out = []
    for i, h in enumerate(slots.get("helpers") or []):
        text = (h.get("instructions") or "").strip()
        if h.get("instructions_file"):
            text = (text + "\n\n" + (ROOT / h["instructions_file"]).read_text(encoding="utf-8").strip()).strip()
        vendor, model = slot_entry(slots, h["slot"])
        out.append({
            "presetId": h["presetId"],
            **route(slots, vendor, model),
            "title": h["title"],
            "promptPrefix": with_common(slots, (h.get("intro", "").strip() + "\n\n" + text).strip()),
            "order": -len(slots["helpers"]) + i,
            **PRESET_DEFAULTS,
            **context_cap(model),
        })
    return out


def menu_table(slots: dict) -> str:
    """The памятка's «Меню сверху вниз»: helpers, then models, in menu order."""
    rows = ["| Кнопка | Цена | Внутри / для чего |", "|---|---|---|",
            "| **Кнопки с готовым порядком работы** | | |"]
    for h in slots.get("helpers") or []:
        m = slot_model(slots, h["slot"])
        n, colour = price_marker(m["out_per_m"], slots)
        rows.append(f"| **{h['title']}** | {colour} x{n} | {m['label']} · {h.get('purpose', '')} |")
    icons = ", ".join(f"{c['icon']} {c['title']}" for c in slots["categories"].values())
    rows.append(f"| **Просто модели: {icons}** | | |")
    for _vendor, category, m in iter_models(slots):
        n, colour = price_marker(m["out_per_m"], slots)
        rows.append(f"| **{slots['categories'][category]['icon']} {m['label']}** | {colour} x{n} | {m.get('purpose', '')} |")
    return "\n".join(rows)


def memo_with_menu(slots: dict, text: str) -> str:
    """The памятка with its menu table regenerated between the markers."""
    begin, end = text.find(MENU_BEGIN), text.find(MENU_END)
    if begin < 0 or end < begin:
        raise SystemExit("ERROR: docs/памятка.md has no menu:begin / menu:end markers")
    head_end = text.index("-->", begin) + 3
    return text[:head_end] + "\n" + menu_table(slots) + "\n" + text[end:]


def build(slots: dict) -> dict:
    presets = helper_presets(slots)
    for order, (vendor, category, model) in enumerate(iter_models(slots), start=1):
        presets.append({
            "presetId": model["presetId"],
            **route(slots, vendor, model),
            "title": title_for(vendor, category, model, slots),
            "order": order,
            "promptPrefix": with_common(slots, ""),
            **PRESET_DEFAULTS,
            **context_cap(model),
        })
    return {"presets": presets}


def render(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    slots = load_slots()
    memo_now = MEMO_PATH.read_text(encoding="utf-8")
    memo = memo_with_menu(slots, memo_now)
    if "--check" in sys.argv:
        bad = memo != memo_now
        if bad:
            print("ERROR: the menu in docs/памятка.md is not what models/slots.yaml generates - "
                  "run scripts/build_presets.py")
        current = PRESETS_PATH.read_text(encoding="utf-8") if PRESETS_PATH.exists() else ""
        if current != render(build(slots)):
            bad = True
            print("ERROR: presets/presets.json is not what models/slots.yaml generates - "
                  "edit slots.yaml and run scripts/build_presets.py")
        if bad:
            return 1
        print("ok: presets.json and the памятка's menu match slots.yaml")
        return 0
    if memo != memo_now:
        MEMO_PATH.write_text(memo, encoding="utf-8", newline="\n")
        print("wrote docs/памятка.md: menu")
    data = build(slots)
    text = render(data)
    PRESETS_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {PRESETS_PATH.relative_to(ROOT)}: {len(data['presets'])} presets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
