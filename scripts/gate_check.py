#!/usr/bin/env python3
"""Guards a model change: every replaced model must have earned it.

Compares models/slots.yaml in the working tree with the one on a base ref
(default origin/main). One rule: a slot whose model changed, or a model
added, needs either
  - the old model missing from OpenRouter (the "missing" list of the
    check_models.py --json report), so its successor goes in untested, or
  - an entry dated today in docs/model-log.md where the new model beat or
    equalled the old one ("better" / "equal").
Anything else is a problem and the change must not become a pull request.

Also prints one short Russian line per change (".digest" in the JSON) for
the Telegram message: what was replaced, why, and what it costs now.

Usage: python scripts/gate_check.py [--base origin/main] [--report /tmp/model-report.json] [--json out.json]
Exit 0 when the change passes (or nothing changed), 1 otherwise.
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SLOTS_PATH = ROOT / "models" / "slots.yaml"
LOG_PATH = ROOT / "docs" / "model-log.md"

ENTRY = re.compile(r"^## (\d{4}-\d{2}-\d{2}) · (.+?): `([^`]+)` vs `([^`]+)` -> \*\*(\w+)\*\*", re.M)
VERDICT_RU = {"better": "судья: лучше", "equal": "судья: не хуже"}


def arg(name: str, default: str | None) -> str | None:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def models_of(slots: dict) -> dict[str, dict]:
    out = {}
    cats = slots.get("categories") or {}
    for vendor in slots.get("vendors") or []:
        for category, cat in cats.items():
            for m in vendor.get(category) or []:
                out[m["presetId"]] = {
                    "id": m["id"],
                    "name": f"{vendor['name']} · {cat.get('title', category)}",
                    "label": m.get("label", m["id"]),
                    "out_per_m": float(m["out_per_m"]),
                }
    return out


def verdicts(today: str) -> dict[tuple[str, str], str]:
    """(candidate, current) -> verdict for the pairs that won or tied today.

    Only headings outside fenced blocks count: judge.py fences every model
    answer, so an answer cannot smuggle in a verdict line.
    """
    if not LOG_PATH.exists():
        return {}
    lines, fence = [], None
    for line in LOG_PATH.read_text(encoding="utf-8").split("\n"):
        m = re.match(r"^(`{3,})\s*$", line)
        if fence is None:
            if m:
                fence = m.group(1)
            else:
                lines.append(line)
        elif m and m.group(1) == fence:
            fence = None
    return {(cand, cur): verdict for day, _slot, cand, cur, verdict in ENTRY.findall("\n".join(lines))
            if day == today and verdict in ("better", "equal")}


def money(a: float | None, b: float | None) -> str:
    if a is None:
        return f"${b:g}/1M"
    if a == b:
        return f"${b:g}/1M"
    return f"${a:g} -> ${b:g}/1M, {'дешевле' if b < a else 'дороже'}"


def main() -> int:
    base = arg("--base", "origin/main")
    report_path = arg("--report", None)
    missing = set(json.loads(Path(report_path).read_text(encoding="utf-8")).get("missing") or []) if report_path else set()
    today = datetime.now(timezone.utc).date().isoformat()

    old_text = subprocess.run(["git", "show", f"{base}:models/slots.yaml"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if old_text.returncode != 0:
        print(f"ERROR: cannot read models/slots.yaml from {base}: {old_text.stderr.strip()}")
        return 1
    old = models_of(yaml.safe_load(old_text.stdout))
    new = models_of(yaml.safe_load(SLOTS_PATH.read_text(encoding="utf-8")))
    won = verdicts(today)

    digest, problems = [], []
    for pid, n in new.items():
        o = old.get(pid)
        if o is None:
            why = next((v for (cand, _cur), v in won.items() if cand == n["id"]), None)
            if why is None:
                problems.append(f"{n['name']}: {n['id']} added without a winning verdict today in docs/model-log.md")
            digest.append(f"{n['name']}: добавили {n['label']} - {VERDICT_RU.get(why, 'без вердикта')}, {money(None, n['out_per_m'])}")
        elif o["id"] != n["id"]:
            if o["id"] in missing:
                why = "пропала из OpenRouter"
            elif (n["id"], o["id"]) in won:
                why = VERDICT_RU[won[(n["id"], o["id"])]]
            else:
                why = "БЕЗ ВЕРДИКТА"
                problems.append(f"{n['name']}: {o['id']} -> {n['id']} has no winning verdict today and {o['id']} is not missing from OpenRouter")
            digest.append(f"{n['name']}: {o['label']} -> {n['label']} - {why}, {money(o['out_per_m'], n['out_per_m'])}")
        elif o["out_per_m"] != n["out_per_m"]:
            digest.append(f"{n['name']} ({n['label']}): цена {money(o['out_per_m'], n['out_per_m'])}")
    for pid, o in old.items():
        if pid not in new:
            digest.append(f"{o['name']}: убрали {o['label']}")

    result = {"ok": not problems, "digest": digest, "problems": problems}
    if "--json" in sys.argv:
        Path(arg("--json", "")).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    for line in digest:
        print(line)
    for p in problems:
        print(f"ERROR: {p}")
    if not digest:
        print("no model changes against", base)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
