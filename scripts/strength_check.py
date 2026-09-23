#!/usr/bin/env python3
"""A signal, not a gate: does the new version still hold a long document?

The judge (judge.py) compares a candidate with the current model on a short
editing task. Every accident so far happened on long texts (Fable stalls at
~100k tokens), so when the monthly refresh replaces a model this runs the old
and the new one on the same ~100k-token manuscript from longctx.py (seed 7,
8 planted contradictions) and reports found / invented for both. It blocks
nothing: the owner decides (and moves `rank` if the strength changed). The
lines go to the Telegram message and a comment on the pull request.

Cost is estimated before anything is called, from OpenRouter prices with a
pessimistic tokenizer (Russian text counts up to ~3x differently across
models), and the whole run is skipped above --cap dollars.

Usage: OPENROUTER_API_KEY=... python scripts/strength_check.py
         [--base origin/main] [--cap 5] [--json out.json] [--dry-run]
"""
import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import gate_check  # noqa: E402
import longctx  # noqa: E402

TOKENS, PLANTS, SEED, MAX_OUT = 100_000, 8, 7, 8000
TOKENIZER_WORST = 2.0  # longctx's 100k manuscript counted 72k-291k tokens across models


def prices() -> dict[str, tuple[float, float]]:
    req = urllib.request.Request("https://openrouter.ai/api/v1/models", headers={"User-Agent": "poly-mind-infra/strength"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)["data"]
    return {m["id"]: (float(m["pricing"]["prompt"]), float(m["pricing"]["completion"])) for m in data}


def pairs(base: str) -> list[tuple[dict, dict]]:
    old_text = subprocess.run(["git", "show", f"{base}:models/slots.yaml"], cwd=ROOT,
                              capture_output=True, text=True, encoding="utf-8", check=True).stdout
    old = gate_check.models_of(yaml.safe_load(old_text))
    new = gate_check.models_of(yaml.safe_load((ROOT / "models" / "slots.yaml").read_text(encoding="utf-8")))
    return [(old[pid], n) for pid, n in new.items() if pid in old and old[pid]["id"] != n["id"]]


def score(model_id: str, doc: str, plants: list[dict], key: str) -> dict:
    try:
        text, usage = longctx.ask(model_id, longctx.TASK + doc, key)
        g = longctx.grade(text, plants)
        return {**g, "stop": usage.get("finish_reason"), "cost": float(usage.get("cost") or 0), "error": None}
    except Exception as e:  # a failed call is a result too: the model did not answer
        return {**longctx.grade("", plants), "stop": None, "cost": 0.0, "error": str(e)[:160]}


def show(label: str, r: dict) -> str:
    if r["error"]:
        return f"{label} - ошибка вызова"
    if not r["parsed"]:
        why = "упёрся в лимит ответа" if r["stop"] == "length" else "ответ не по формату"
        return f"{label} - не ответил ({why})"
    return f"{label} {r['found']}/{PLANTS}, выдумал {r['false']}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--cap", type=float, default=5.0)
    ap.add_argument("--json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    todo = pairs(args.base)
    result = {"lines": [], "comment": "", "cost": 0.0}
    if not todo:
        print("no replaced models - nothing to check")
    else:
        doc, plants = longctx.build(TOKENS, PLANTS, SEED)
        est_in = len(doc) / longctx.CHARS_PER_TOKEN * TOKENIZER_WORST
        price = prices()
        models = {m["id"] for pair in todo for m in pair}
        missing = sorted(m for m in models if m not in price)
        estimate = sum(est_in * price[m][0] + MAX_OUT * price[m][1] for m in models if m in price)
        print(f"{len(todo)} replacement(s), {len(models)} model(s), estimate ${estimate:.2f}, cap ${args.cap:g}")
        if estimate > args.cap:
            result["lines"].append(f"длинный текст не проверен: оценка ${estimate:.2f} выше лимита ${args.cap:g}")
        elif args.dry_run:
            result["lines"].append(f"(dry run) длинный текст: проверил бы {', '.join(sorted(models))} за ~${estimate:.2f}")
        else:
            key = os.environ.get("OPENROUTER_API_KEY")
            if not key:
                print("ERROR: OPENROUTER_API_KEY is not set")
                return 1
            longctx.MAX_TOKENS = MAX_OUT
            with cf.ThreadPoolExecutor(max_workers=4) as ex:
                runs = dict(zip(sorted(models - set(missing)), ex.map(lambda m: score(m, doc, plants, key), sorted(models - set(missing)))))
            result["cost"] = round(sum(r["cost"] for r in runs.values()), 2)
            table = ["| Слот | Было | Стало |", "|---|---|---|"]
            for o, n in todo:
                ro, rn = runs.get(o["id"]), runs.get(n["id"])
                was = show(o["label"], ro) if ro else f"{o['label']} - нет в OpenRouter"
                now = show(n["label"], rn) if rn else f"{n['label']} - нет в OpenRouter"
                worse = rn is not None and (ro is None or rn["f1"] < ro["f1"])
                verdict = "⚠️ хуже - посмотри место в меню" if worse and ro else ("✅ не хуже" if rn and ro else "")
                result["lines"].append(f"длинный текст ~100k: {was} -> {now} {verdict}".rstrip())
                table.append(f"| {n['name']} | {was} | {now} {verdict} |")
            result["comment"] = "\n".join([
                "**Длинный текст** (сигнал, не блокирует): рукопись ~100 тыс. токенов из `scripts/longctx.py`, "
                f"seed {SEED}, {PLANTS} зашитых противоречий, лимит ответа {MAX_OUT}. Обе модели читают одно и то же.", "",
                *table, "", f"Стоимость прогона: ${result['cost']:.2f}. Если сила изменилась - поправь `rank` в `models/slots.yaml`."])
    for line in result["lines"]:
        print(line)
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
