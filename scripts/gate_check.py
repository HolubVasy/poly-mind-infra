#!/usr/bin/env python3
"""Guards a model change: every replaced model must have earned it.

Compares models/slots.yaml in the working tree with the one on a base ref
(default origin/main). For every slot whose model changed, and for every
model added, one of these must hold:
  - the old model is missing from OpenRouter (the "missing" list of the
    check_models.py --json report), so its successor goes in without a test;
  - docs/model-log.md has an entry dated today where the new model beat or
    equalled the old one ("better" / "equal").
Anything else is a problem and the change must not become a pull request.

Also says whether the change is safe to merge without the owner: only
vanished-model replacements and price markers, no added or removed models.

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


def arg(name: str, default: str | None) -> str | None:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def models_of(slots: dict) -> dict[str, dict]:
    out = {}
    for vendor in slots.get("vendors") or []:
        for category in slots.get("categories") or {}:
            for m in vendor.get(category) or []:
                out[m["presetId"]] = {"id": m["id"], "slot": f"{vendor['name']}/{category}", "out_per_m": m["out_per_m"]}
    return out


def verdicts(today: str) -> set[tuple[str, str]]:
    """(candidate, current) pairs that won or tied today.

    Only headings outside the fenced blocks count. judge.py fences every model
    answer, so an answer cannot contain a verdict line that would be read here
    as a passed quality gate.
    """
    if not LOG_PATH.exists():
        return set()
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
    return {(cand, cur) for day, _slot, cand, cur, verdict in ENTRY.findall("\n".join(lines))
            if day == today and verdict in ("better", "equal")}


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

    changes, problems = [], []
    for pid, n in new.items():
        o = old.get(pid)
        if o is None:
            changes.append({"slot": n["slot"], "old": None, "new": n["id"], "kind": "added"})
            if not any(cand == n["id"] for cand, _ in won):
                problems.append(f"{n['slot']}: {n['id']} added without a winning verdict today in docs/model-log.md")
            continue
        if o["id"] != n["id"]:
            if o["id"] in missing:
                changes.append({"slot": n["slot"], "old": o["id"], "new": n["id"], "kind": "vanished"})
            elif (n["id"], o["id"]) in won:
                changes.append({"slot": n["slot"], "old": o["id"], "new": n["id"], "kind": "upgrade"})
            else:
                changes.append({"slot": n["slot"], "old": o["id"], "new": n["id"], "kind": "unjustified"})
                problems.append(f"{n['slot']}: {o['id']} -> {n['id']} has no winning verdict today and {o['id']} is not missing from OpenRouter")
        elif float(o["out_per_m"]) != float(n["out_per_m"]):
            changes.append({"slot": n["slot"], "old": o["id"], "new": n["id"], "kind": "price", "from": o["out_per_m"], "to": n["out_per_m"]})
    for pid, o in old.items():
        if pid not in new:
            changes.append({"slot": o["slot"], "old": o["id"], "new": None, "kind": "removed"})

    auto_merge = bool(changes) and not problems and all(c["kind"] in ("vanished", "price") for c in changes)
    result = {"ok": not problems, "changes": changes, "problems": problems, "auto_merge": auto_merge}
    if "--json" in sys.argv:
        Path(arg("--json", "")).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    for c in changes:
        print(f"{c['kind']:12} {c['slot']}: {c.get('old')} -> {c.get('new')}" + (f" ({c['from']} -> {c['to']})" if c["kind"] == "price" else ""))
    for p in problems:
        print(f"ERROR: {p}")
    if not changes:
        print("no model changes against", base)
    else:
        print("auto-merge:", "yes" if auto_merge else "no, waits for the owner")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
