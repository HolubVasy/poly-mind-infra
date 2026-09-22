#!/usr/bin/env python3
"""Quality gate for a model replacement: candidate vs current, judged blind.

Both models get the standard prompt from tests/standard_prompt.md. A judge
model sees the two answers as A and B in random order and says which is
better for the task. The verdict, the reason and both answers are appended to
docs/model-log.md, so a rejected candidate leaves its reasoning on record.

Only the standard library is used, so it runs anywhere with Python 3.10+.
Needs OPENROUTER_API_KEY in the environment.

Usage:
  python scripts/judge.py --slot "Claude/frontier" \
      --current anthropic/claude-sonnet-5 --candidate anthropic/claude-opus-5 \
      --judge anthropic/claude-fable-5.1 [--log docs/model-log.md] [--no-log]

Prints one JSON line: {"verdict": "better|equal|worse|failed", "reason": ...}.
Exit code 0 whenever the gate ran; 2 on a usage or API error.
verdict "better"/"equal" -> the candidate may replace the current model.
verdict "worse"/"failed" -> keep the current model.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = ROOT / "tests" / "standard_prompt.md"
LOG_PATH = ROOT / "docs" / "model-log.md"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT = 180
# Reasoning models (Kimi, GLM) spend most of the budget on thinking; at 6000
# they produced no answer at all and were scored as failures.
MAX_TOKENS = 16000

JUDGE_INSTRUCTIONS = """Ты сравниваешь два ответа на одно и то же задание по редактированию научного
текста на русском языке. Оцени только качество выполнения задания: исправлены
ли реальные ошибки (терминология, согласование, единицы, логика), сохранены ли
смысл и данные автора, нет ли выдуманного, русский ли язык, ясен ли список
изменений. Длина и стиль оформления сами по себе не важны.

Ответь строго одной строкой JSON без пояснений вокруг:
{"winner": "A" | "B" | "tie", "reason": "<одно-два предложения по-русски>"}
"""


def standard_prompt() -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    marker = "## Запрос"
    if marker not in text:
        sys.exit(f"{PROMPT_PATH}: no '{marker}' section")
    return text.split(marker, 1)[1].strip()


def ask(model: str, messages: list[dict], key: str) -> str:
    body = json.dumps({"model": model, "messages": messages, "max_tokens": MAX_TOKENS, "temperature": 0}).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/HolubVasy/poly-mind-infra",
        "X-Title": "poly-mind-infra model check",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.load(resp)
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"{model}: empty choices: {json.dumps(data)[:300]}")
    return (choices[0].get("message") or {}).get("content") or ""


def answer(model: str, prompt: str, key: str) -> tuple[str, str | None]:
    """Returns (text, failure). failure is None when the answer is usable."""
    try:
        text = ask(model, [{"role": "user", "content": prompt}], key)
    except (urllib.error.URLError, RuntimeError, TimeoutError) as e:
        return "", f"no answer: {e}"
    if len(text.strip()) < 200:
        return text, "answer too short"
    letters = [c for c in text if c.isalpha()]
    cyrillic = sum("а" <= c.lower() <= "я" or c.lower() == "ё" for c in letters)
    if not letters or cyrillic / len(letters) < 0.6:
        return text, "not in Russian"
    return text, None


def judge(judge_model: str, prompt: str, a: str, b: str, key: str) -> tuple[str, str]:
    content = (
        f"{JUDGE_INSTRUCTIONS}\n\n=== ЗАДАНИЕ ===\n{prompt}\n\n"
        f"=== ОТВЕТ A ===\n{a}\n\n=== ОТВЕТ B ===\n{b}\n"
    )
    raw = ask(judge_model, [{"role": "user", "content": content}], key)
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise RuntimeError(f"judge did not return JSON: {raw[:200]}")
    data = json.loads(m.group(0))
    winner = str(data.get("winner", "")).strip().upper()
    if winner not in ("A", "B", "TIE"):
        raise RuntimeError(f"judge winner unclear: {raw[:200]}")
    return winner, str(data.get("reason", "")).strip()


def log_entry(args, verdict: str, reason: str, cur_text: str, cand_text: str, judge_model: str) -> str:
    day = datetime.now(timezone.utc).date().isoformat()
    def block(title: str, text: str) -> str:
        # A model's answer is data, never log structure: it is fenced, with a
        # fence longer than any backtick run inside it, so an answer cannot
        # forge a verdict heading that gate_check.py would read as a passed
        # quality gate.
        body = (text.strip() or "(нет ответа)").replace("\r\n", "\n")
        fence = "`" * max(4, *(len(m) + 1 for m in re.findall(r"`+", body) or [""]))
        return f"<details><summary>{title}</summary>\n\n{fence}\n{body}\n{fence}\n\n</details>\n"
    return (
        f"\n## {day} · {args.slot}: `{args.candidate}` vs `{args.current}` -> **{verdict}**\n\n"
        f"Судья `{judge_model}`: {reason}\n\n"
        + block(f"Текущая: {args.current}", cur_text)
        + block(f"Кандидат: {args.candidate}", cand_text)
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--slot", required=True, help='e.g. "Claude/frontier"')
    p.add_argument("--current", required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--judge", required=True)
    p.add_argument("--log", default=str(LOG_PATH))
    p.add_argument("--no-log", action="store_true")
    args = p.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("ERROR: OPENROUTER_API_KEY is not set", file=sys.stderr)
        return 2
    prompt = standard_prompt()

    cand_text, cand_fail = answer(args.candidate, prompt, key)
    cur_text, cur_fail = answer(args.current, prompt, key)
    if cand_fail:
        verdict, reason = "failed", f"кандидат: {cand_fail}"
    elif cur_fail:
        # The current model cannot answer any more: the candidate wins by default.
        verdict, reason = "better", f"текущая модель: {cur_fail}"
    else:
        a_is_candidate = random.random() < 0.5
        a, b = (cand_text, cur_text) if a_is_candidate else (cur_text, cand_text)
        try:
            winner, why = judge(args.judge, prompt, a, b, key)
        except (urllib.error.URLError, RuntimeError, ValueError) as e:
            print(f"ERROR: judge failed: {e}", file=sys.stderr)
            return 2
        if winner == "TIE":
            verdict = "equal"
        elif (winner == "A") == a_is_candidate:
            verdict = "better"
        else:
            verdict = "worse"
        reason = f"{why} (кандидат был ответом {'A' if a_is_candidate else 'B'})"

    if not args.no_log:
        log = Path(args.log)
        log.parent.mkdir(parents=True, exist_ok=True)
        if not log.exists():
            log.write_text("# Model log\n\nВердикты судьи по каждому кандидату; см. CLAUDE.md, Monthly model review.\n",
                           encoding="utf-8", newline="\n")
        with log.open("a", encoding="utf-8", newline="\n") as f:
            f.write(log_entry(args, verdict, reason, cur_text, cand_text, args.judge))
    print(json.dumps({"slot": args.slot, "current": args.current, "candidate": args.candidate,
                      "verdict": verdict, "reason": reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
