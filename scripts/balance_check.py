#!/usr/bin/env python3
"""Tells the owner once when the OpenRouter balance falls below a threshold.

The mother's chat, the monthly judge and every experiment spend from one
OpenRouter account. When it hits zero the chat stops answering and nobody
knows. The owner wants ONE message when the balance goes below the line, not
a daily "still low": so the script remembers the last state in a small file
(kept between runs by the workflow's cache) and speaks only on the way down.
A top-up above the line resets it silently.

Usage: OPENROUTER_API_KEY=... python scripts/balance_check.py
         [--threshold 1] [--state balance-state.json] [--message out.txt]
Writes the Telegram text to --message only when the balance just crossed the
line; prints the balance and the decision either way. Exit 1 on API errors.
"""
import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

API = "https://openrouter.ai/api/v1"
TOP_UP = "https://openrouter.ai/settings/credits"


def get(path: str, key: str) -> dict:
    req = urllib.request.Request(f"{API}/{path}", headers={
        "Authorization": f"Bearer {key}", "User-Agent": "poly-mind-infra/balance-check"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)["data"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=1.0)
    ap.add_argument("--state", default="balance-state.json")
    ap.add_argument("--message", default="balance-message.txt")
    args = ap.parse_args()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("ERROR: OPENROUTER_API_KEY is not set")
        return 1

    credits = get("credits", key)
    balance = float(credits["total_credits"]) - float(credits["total_usage"])
    try:
        weekly = float(get("key", key).get("usage_weekly") or 0)
    except Exception:
        weekly = 0.0
    per_day = weekly / 7

    state_path = Path(args.state)
    try:
        was_low = bool(json.loads(state_path.read_text(encoding="utf-8")).get("low"))
    except (OSError, ValueError):
        was_low = False
    low = balance < args.threshold
    print(f"balance ${balance:.2f}, threshold ${args.threshold:g}, low={low}, was_low={was_low}, "
          f"spent ${weekly:.2f} in 7 days")

    if low and not was_low:
        days = (f". За последние 7 дней ушло ${weekly:.2f}, такими темпами хватит примерно на {balance / per_day:.1f} дн."
                if per_day > 0 else "")
        text = (f"💸 OpenRouter: осталось ${balance:.2f} - меньше ${args.threshold:g}{days}\n"
                f"На этом балансе работает чат мамы: на нуле он перестанет отвечать.\n"
                f"Пополнить: {TOP_UP}")
        Path(args.message).write_text(text, encoding="utf-8")
        print("crossed the line - message written")
    else:
        print("no message")
    state_path.write_text(json.dumps({"low": low, "balance": round(balance, 2)}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
