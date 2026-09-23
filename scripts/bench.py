#!/usr/bin/env python3
"""Compares every model of the menu against the others on the mother's own tasks.

The monthly review only asks "is the new version of this line better than the
old one". This asks the question the shelves are actually built on: on her
work, who is better than whom - a workhorse against a flagship, one vendor
against another.

How it runs (one pass):
  1. every model in models/slots.yaml answers each prompt of
     tests/bench_prompts.md (one call per model per prompt);
  2. per prompt the answers are anonymised as A, B, C..., shuffled, and each
     JUDGE ranks them best to worst in one go - a ranking, not 55 pairs;
  3. a judge never ranks a prompt where a model of its own vendor answered
     under a letter it could recognise... it cannot, but its own vendor's
     answers are still dropped from ITS ranking, so nobody grades their own
     family;
  4. rankings become points (Borda: first place of n gets n-1 points, scaled
     to 0..1 because judges see different numbers of answers), averaged over
     judges and prompts.

Output: docs/bench-<date>.md - the table, the per-prompt places, who failed to
answer, the cost, and every raw answer in a fenced block. Nothing in the repo
changes on its own: the report is for the owner to read and decide.

Usage:
  OPENROUTER_API_KEY=... python scripts/bench.py [--out docs/bench-<date>.md]
      [--prompts edit,method] [--models a/b,c/d] [--extra a/b,c/d]
      [--judges a/b,c/d] [--dry-run]

--extra adds models that are not in the menu (a guest, e.g. a model we
dropped or are thinking of adding); price comes from the OpenRouter catalogue.

--dry-run prints what would be asked, and calls nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SLOTS_PATH = ROOT / "models" / "slots.yaml"
PROMPTS_PATH = ROOT / "tests" / "bench_prompts.md"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT = 300
# Reasoning models (Kimi, GLM) spend most of the budget on thinking: with
# 6000 they ran out before writing anything and looked like they refused.
MAX_TOKENS = 16000
# Judges: strong models from different camps. A judge never grades its own
# vendor's answers.
DEFAULT_JUDGES = ["anthropic/claude-fable-5.1", "openai/gpt-6-astra-pro", "x-ai/grok-4.7"]

JUDGE_INSTRUCTIONS = """Ты оцениваешь ответы разных моделей на одно и то же задание. Ранжируй их от
лучшего к худшему по тому, насколько хорошо выполнено именно это задание:
соблюдён ли формат, сделано ли то, что просили, сохранены ли данные и величины,
нет ли выдуманного (несуществующих ссылок, приборов, чисел), русский ли язык и
научный ли стиль. Длина сама по себе не достоинство и не недостаток.

Ответь строго одной строкой JSON, без текста вокруг:
{"ranking": ["B", "A", "D", ...], "why": "<одно-два предложения про первое и последнее место>"}
В "ranking" должны быть все буквы ответов, каждая ровно один раз.
"""


def ask(model: str, content: str, key: str) -> tuple[str, dict]:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/HolubVasy/poly-mind-infra",
        "X-Title": "poly-mind-infra bench",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.load(resp)
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"empty choices: {json.dumps(data)[:200]}")
    text = (choices[0].get("message") or {}).get("content") or ""
    return text, data.get("usage") or {}


def load_prompts(only: list[str] | None) -> list[dict]:
    text = PROMPTS_PATH.read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r"^## (\S+) · (.+?)\n(.*?)(?=^## |\Z)", text, re.M | re.S):
        pid, title, body = m.group(1), m.group(2).strip(), m.group(3).strip()
        if not only or pid in only:
            out.append({"id": pid, "title": title, "prompt": body})
    if not out:
        sys.exit(f"{PROMPTS_PATH}: no prompts matched")
    return out


def load_models(only: list[str] | None) -> list[dict]:
    slots = yaml.safe_load(SLOTS_PATH.read_text(encoding="utf-8"))
    out = []
    for vendor in slots["vendors"]:
        for category in slots["categories"]:
            for m in vendor.get(category) or []:
                if not only or m["id"] in only:
                    out.append({"id": m["id"], "label": m["label"], "vendor": vendor["name"],
                                "prefix": vendor["prefix"], "category": category,
                                "out_per_m": float(m["out_per_m"])})
    if not out:
        sys.exit("slots.yaml: no models matched")
    return out


def load_extra(ids: list[str]) -> list[dict]:
    """Guests: models outside slots.yaml, priced from the OpenRouter catalogue."""
    if not ids:
        return []
    slots = yaml.safe_load(SLOTS_PATH.read_text(encoding="utf-8"))
    req = urllib.request.Request("https://openrouter.ai/api/v1/models",
                                 headers={"User-Agent": "poly-mind-infra/bench"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        cat = {m["id"]: m for m in json.load(resp)["data"]}
    out = []
    for mid in ids:
        if mid not in cat:
            sys.exit(f"--extra {mid}: not in the OpenRouter catalogue")
        vendor = next((v for v in slots["vendors"] if mid.startswith(v["prefix"])), None)
        prefix = vendor["prefix"] if vendor else mid.split("/")[0] + "/"
        out.append({"id": mid, "label": cat[mid].get("name", mid).split(": ")[-1] + " (гость)",
                    "vendor": vendor["name"] if vendor else prefix.rstrip("/"), "prefix": prefix,
                    "category": "guest",
                    "out_per_m": round(float(cat[mid]["pricing"]["completion"]) * 1_000_000, 4)})
    return out


def usable(text: str) -> str | None:
    """None when the answer is fine, otherwise why it is not."""
    if len(text.strip()) < 200:
        return f"слишком короткий ответ ({len(text.strip())} знаков)"
    letters = [c for c in text if c.isalpha()]
    cyr = sum("а" <= c.lower() <= "я" or c.lower() == "ё" for c in letters)
    # 0.3, not 0.5: the "sources" task asks for search queries IN ENGLISH, and
    # on 2026-09-23 two correct answers were thrown out as "not Russian".
    if not letters or cyr / len(letters) < 0.3:
        return "ответ не по-русски"
    return None


def fence(text: str) -> str:
    body = (text.strip() or "(нет ответа)").replace("\r\n", "\n")
    n = max([len(m) for m in re.findall(r"`+", body)] or [0]) + 1
    f = "`" * max(4, n)
    return f"{f}\n{body}\n{f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out")
    ap.add_argument("--prompts", help="comma-separated prompt ids")
    ap.add_argument("--models", help="comma-separated model ids")
    ap.add_argument("--extra", help="comma-separated model ids outside the menu")
    ap.add_argument("--judges", default=",".join(DEFAULT_JUDGES))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    prompts = load_prompts(args.prompts.split(",") if args.prompts else None)
    models = load_models(args.models.split(",") if args.models else None)
    models += load_extra(args.extra.split(",") if args.extra else [])
    judges = [j for j in args.judges.split(",") if j]
    day = datetime.now(timezone.utc).date().isoformat()
    out_path = Path(args.out) if args.out else ROOT / "docs" / f"bench-{day}.md"

    print(f"{len(models)} models x {len(prompts)} prompts = {len(models) * len(prompts)} answers, "
          f"then {len(judges)} judges x {len(prompts)} rankings", file=sys.stderr)
    if args.dry_run:
        for p in prompts:
            print(f"\n=== {p['id']} · {p['title']}\n{p['prompt'][:300]}...", file=sys.stderr)
        print("\nmodels: " + ", ".join(m["id"] for m in models), file=sys.stderr)
        print("judges: " + ", ".join(judges), file=sys.stderr)
        return 0

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("ERROR: OPENROUTER_API_KEY is not set", file=sys.stderr)
        return 2

    answers: dict[tuple[str, str], dict] = {}
    cost = 0.0
    for p in prompts:
        for m in models:
            t0 = time.time()
            try:
                text, usage = ask(m["id"], p["prompt"], key)
                bad = usable(text)
            except (urllib.error.URLError, RuntimeError, TimeoutError) as e:
                text, usage, bad = "", {}, f"ошибка вызова: {e}"
            answers[(p["id"], m["id"])] = {"text": text, "bad": bad, "usage": usage,
                                           "seconds": round(time.time() - t0, 1)}
            cost += float(usage.get("cost") or 0)
            print(f"  {p['id']:8} {m['id']:32} {'OK' if not bad else bad}", file=sys.stderr)

    rankings: list[dict] = []
    for p in prompts:
        good = [m for m in models if not answers[(p["id"], m["id"])]["bad"]]
        for judge in judges:
            # A judge does not grade its own vendor's answers.
            shown = [m for m in good if not judge.startswith(m["prefix"])]
            if len(shown) < 2:
                continue
            order = shown[:]
            random.shuffle(order)
            letters = {chr(ord("A") + i): m["id"] for i, m in enumerate(order)}
            blocks = "\n\n".join(f"=== ОТВЕТ {ltr} ===\n{answers[(p['id'], mid)]['text'].strip()}"
                                 for ltr, mid in letters.items())
            content = f"{JUDGE_INSTRUCTIONS}\n\n=== ЗАДАНИЕ ===\n{p['prompt']}\n\n{blocks}\n"
            try:
                raw, usage = ask(judge, content, key)
                cost += float(usage.get("cost") or 0)
                mm = re.search(r"\{.*\}", raw, re.S)
                data = json.loads(mm.group(0)) if mm else {}
                seq = [str(x).strip().upper()[:1] for x in (data.get("ranking") or [])]
                seq = [s for i, s in enumerate(seq) if s in letters and s not in seq[:i]]
                if len(seq) != len(letters):
                    raise RuntimeError(f"ranking has {len(seq)} of {len(letters)} answers")
                rankings.append({"prompt": p["id"], "judge": judge,
                                 "order": [letters[s] for s in seq], "why": str(data.get("why", "")).strip()})
                print(f"  rank {p['id']:8} by {judge:28} ok", file=sys.stderr)
            except (urllib.error.URLError, RuntimeError, ValueError, json.JSONDecodeError) as e:
                print(f"  rank {p['id']:8} by {judge:28} FAILED: {e}", file=sys.stderr)

    # Borda, scaled to 0..1 so rankings of different length compare.
    points: dict[str, list[float]] = {m["id"]: [] for m in models}
    for r in rankings:
        n = len(r["order"])
        for place, mid in enumerate(r["order"]):
            points[mid].append((n - 1 - place) / (n - 1) if n > 1 else 1.0)
    score = {mid: (sum(v) / len(v) if v else None) for mid, v in points.items()}
    by_model = {m["id"]: m for m in models}
    ordered = sorted(models, key=lambda m: (score[m["id"]] is None, -(score[m["id"]] or 0)))

    lines = [f"# Сравнение моделей {day}", "",
             f"{len(models)} моделей, {len(prompts)} задач, судьи: {', '.join(f'`{j}`' for j in judges)}. "
             f"Ответы обезличены и перемешаны; судья не оценивает модели своего вендора. "
             f"Балл - среднее место по Борда (1.00 - всегда первый, 0.00 - всегда последний). "
             f"Стоимость прогона: ${cost:.2f}.", "",
             "| # | Модель | Полка | $/1M | Балл | Оценок | Провалов |", "|---|---|---|---|---|---|---|"]
    for i, m in enumerate(ordered, start=1):
        s = score[m["id"]]
        fails = sum(1 for p in prompts if answers[(p["id"], m["id"])]["bad"])
        lines.append(f"| {i} | {m['label']} (`{m['id']}`) | {m['category']} | {m['out_per_m']:g} | "
                     f"{'-' if s is None else f'{s:.2f}'} | {len(points[m['id']])} | {fails} |")
    lines += ["", "## Кто не ответил", ""]
    bad_rows = [f"- `{mid}` на задаче `{pid}`: {a['bad']}" for (pid, mid), a in answers.items() if a["bad"]]
    lines += bad_rows or ["Все модели ответили."]
    lines += ["", "## Места по задачам", ""]
    for p in prompts:
        lines.append(f"### {p['id']} · {p['title']}")
        lines.append("")
        for r in [r for r in rankings if r["prompt"] == p["id"]]:
            names = " > ".join(by_model[mid]["label"] for mid in r["order"])
            lines.append(f"- судья `{r['judge']}`: {names}")
            if r["why"]:
                lines.append(f"  - {r['why']}")
        lines.append("")
    lines += ["## Ответы", ""]
    for p in prompts:
        lines.append(f"### {p['id']} · {p['title']}")
        lines.append("")
        for m in models:
            a = answers[(p["id"], m["id"])]
            mark = f" - НЕ ЗАСЧИТАН: {a['bad']}" if a["bad"] else ""
            lines.append(f"<details><summary>{m['label']} ({a['seconds']} c){mark}</summary>\n")
            lines.append(fence(a["text"]))
            lines.append("\n</details>\n")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"\nwrote {out_path}  (${cost:.2f})", file=sys.stderr)
    for i, m in enumerate(ordered[:5], start=1):
        s = score[m["id"]]
        print(f"  {i}. {m['label']:20} {'-' if s is None else f'{s:.2f}'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
