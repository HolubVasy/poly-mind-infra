#!/usr/bin/env python3
"""Does a model keep hold of a long document? Scored against a key, no judge.

bench.py uses short tasks (a paragraph, a list of data). The mother works with
whole articles and theses, where the real test is whether a model still
remembers page 3 when it reads page 90. This builds a long Russian manuscript
about silver nanoparticle samples, plants contradictions in it - the same
quantity of the same sample stated differently in two distant places - and
asks every model to find them all. The answer is checked against the key:
found (recall), invented (false alarms), F1.

The manuscript is generated from a fixed seed, so every model reads exactly
the same text and a rerun reproduces it. It is realistic on purpose: every
sample is mentioned several times with the SAME values (so listing mentions is
not enough, a model has to compare), and the text quotes literature values
for other materials that must not be confused with our samples.

Usage:
  OPENROUTER_API_KEY=... python scripts/longctx.py [--tokens 50000,200000]
      [--models a/b,c/d] [--extra a/b] [--plants 8] [--seed 7] [--out docs/longctx-<date>.md]
      [--dry-run]   # build the documents, print sizes and the key, call nothing
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
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
API_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT = 900
MAX_TOKENS = 16000
CHARS_PER_TOKEN = 2.6  # rough for Russian scientific text; real counts come from usage

# canonical parameter -> (how it is written, unit, generator, formatter)
PARAMS = {
    "размер": ("средний размер частиц по данным ПЭМ", "нм", lambda r: r.randint(8, 60), lambda v: f"{v} нм"),
    "дзета": ("дзета-потенциал", "мВ", lambda r: -r.randint(18, 48), lambda v: f"{v} мВ".replace("-", "−")),
    "pdi": ("индекс полидисперсности", "", lambda r: round(r.uniform(0.08, 0.45), 2), lambda v: f"{v:.2f}".replace(".", ",")),
    "lmax": ("максимум плазмонного поглощения", "нм", lambda r: r.randint(395, 460), lambda v: f"{v} нм"),
    "температура": ("температура синтеза", "°C", lambda r: r.choice([20, 25, 40, 60, 70, 80, 85, 90, 95, 100]), lambda v: f"{v} °C"),
    "время": ("время выдержки", "мин", lambda r: r.choice([5, 10, 15, 20, 25, 30, 40, 45, 60, 90]), lambda v: f"{v} мин"),
    "ph": ("pH реакционной смеси", "", lambda r: round(r.uniform(6.0, 11.0), 1), lambda v: f"{v:.1f}".replace(".", ",")),
}
PARAM_WORDS = {  # how an answer may name the parameter
    "размер": ["размер", "диаметр", "пэм"],
    "дзета": ["дзета", "zeta", "ζ"],
    "pdi": ["полидисперс", "pdi"],
    "lmax": ["плазмон", "λ", "lmax", "максимум поглощ", "поглощ"],
    "температура": ["температур"],
    "время": ["время", "выдерж", "длительн"],
    "ph": ["ph", "рн"],
}

INTRO = [
    "Наночастицы серебра остаются одним из наиболее изучаемых наноматериалов благодаря сочетанию плазмонных и антибактериальных свойств.",
    "Размер, форма и состояние поверхности частиц во многом определяются условиями синтеза: природой восстановителя, температурой, pH и временем реакции.",
    "Цитратный метод Туркевича, изначально предложенный для золота, широко применяется и для серебра, хотя воспроизводимость результатов в этом случае ниже.",
    "Стабилизирующий агент не только препятствует агрегации, но и влияет на кинетику роста зародышей.",
    "Положение максимума поверхностного плазмонного резонанса чувствительно к размеру частиц и диэлектрическому окружению.",
    "Коллоидную стабильность обычно оценивают по величине дзета-потенциала; значения по модулю выше 30 мВ принято считать признаком устойчивой системы.",
    "Метод динамического рассеяния света даёт гидродинамический диаметр, который, как правило, превышает размер металлического ядра по данным ПЭМ.",
    "Индекс полидисперсности ниже 0,2 обычно рассматривается как признак достаточно узкого распределения по размерам.",
    "Антибактериальная активность наночастиц серебра связана как с высвобождением ионов Ag+, так и с непосредственным взаимодействием частиц с мембраной.",
    "Для грамотрицательных бактерий эффект, как правило, выражен сильнее, что связывают с более тонким слоем пептидогликана.",
    "Сопоставление результатов разных групп затруднено тем, что условия синтеза и методы характеризации часто описаны неполно.",
    "Систематическое варьирование одного параметра при фиксированных остальных позволяет выделить его вклад в итоговые свойства коллоида.",
]
LIT = [  # literature values for OTHER materials - distractors, not our samples
    "В работе [{n}] для наночастиц золота, полученных тем же методом, сообщается о среднем размере {a} нм.",
    "Авторы [{n}] наблюдали максимум плазмонного поглощения при {b} нм для частиц серебра в поливинилпирролидоне.",
    "Согласно [{n}], дзета-потенциал цитратных коллоидов серебра находится в диапазоне от −{c} до −{d} мВ.",
    "В обзоре [{n}] отмечается, что повышение температуры синтеза до {e} °C сокращает время реакции примерно вдвое.",
    "Близкие значения индекса полидисперсности (около 0,{f}) приводятся в работе [{n}] для боргидридного метода.",
]
DISCUSS = [
    "Сравнение образцов {x} и {y} показывает, что {px} у первого составляет {vx}, тогда как у второго {py} равен {vy}.",
    "Для образца {x} {px} ({vx}) хорошо согласуется с общей тенденцией серии.",
    "Обращает на себя внимание образец {x}: {px} у него составил {vx}, что выделяет его среди соседних по условиям синтеза.",
    "Как видно из данных для образца {x}, {px} равен {vx}; этот результат использован при построении зависимости на рис. {n}.",
    "При повторном анализе данных образца {x} {px} был подтверждён на уровне {vx}.",
]


def build(target_tokens: int, n_plants: int, seed: int) -> tuple[str, list[dict]]:
    """Returns the manuscript and the key: one entry per planted contradiction.

    Built twice: the first pass measures how long a discussion fragment really
    is, the second uses that to hit the target size.
    """
    text, _, head_len, chunks = _build(target_tokens, n_plants, seed, 1400)
    per_chunk = max(300.0, (len(text) - head_len) / max(1, chunks))
    text, plants, _, _ = _build(target_tokens, n_plants, seed, per_chunk)
    return text, plants


def _build(target_tokens: int, n_plants: int, seed: int, chunk_chars: float):
    r = random.Random(seed * 1000 + target_tokens)
    target_chars = int(target_tokens * CHARS_PER_TOKEN)
    n_samples = max(12, min(80, target_tokens // 2500))
    samples = {f"S-{i:02d}": {p: g[2](r) for p, g in PARAMS.items()} for i in range(1, n_samples + 1)}
    names = list(samples)

    def para(pool: list[str], k: int) -> str:
        out = []
        for _ in range(k):
            s = r.choice(pool)
            out.append(s.format(n=r.randint(3, 140), a=r.randint(10, 40), b=r.randint(400, 450), c=r.randint(20, 30),
                                d=r.randint(31, 45), e=r.choice([80, 90, 100]), f=r.randint(12, 25)))
        return " ".join(out)

    parts: list[str] = ["# Влияние условий цитратного синтеза на размер и коллоидную стабильность наночастиц серебра", ""]
    parts += ["## 1. Введение", ""] + [para(INTRO + LIT, 6) + "\n" for _ in range(4)]
    parts += ["## 2. Методика синтеза", ""]
    for s in names:
        v = samples[s]
        parts.append(f"Образец {s} получали при {PARAMS['температура'][3](v['температура'])}; время выдержки составляло "
                     f"{PARAMS['время'][3](v['время'])}, pH реакционной смеси поддерживали на уровне {PARAMS['ph'][3](v['ph'])}. "
                     + para(INTRO, 1) + "\n")
    parts += ["## 3. Характеризация", ""]
    for s in names:
        v = samples[s]
        parts.append(f"Для образца {s} {PARAMS['размер'][0]} составил {PARAMS['размер'][3](v['размер'])}, "
                     f"{PARAMS['pdi'][0]} — {PARAMS['pdi'][3](v['pdi'])}, {PARAMS['дзета'][0]} — "
                     f"{PARAMS['дзета'][3](v['дзета'])}, {PARAMS['lmax'][0]} наблюдался при {PARAMS['lmax'][3](v['lmax'])}. "
                     + para(INTRO + LIT, 1) + "\n")
    head = "\n".join(parts)

    # Discussion: many consistent re-mentions, filler, and the planted contradictions.
    plants: list[dict] = []
    chosen = r.sample([(s, p) for s in names for p in PARAMS], n_plants)
    body: list[str] = []
    budget = max(0, target_chars - len(head) - 4000)
    n_chunks = max(n_plants * 3, int(budget // chunk_chars))
    plant_at = sorted(r.sample(range(1, n_chunks), n_plants)) if n_chunks > n_plants else list(range(n_plants))
    section = 4
    for i in range(n_chunks):
        if i % 12 == 0:
            body += [f"## {section}. Обсуждение, часть {section - 3}", ""]
            section += 1
        chunk = [para(INTRO + LIT, 3)]
        for _ in range(3):  # consistent re-mentions
            x, y = r.sample(names, 2)
            px, py = r.sample(list(PARAMS), 2)
            t = r.choice(DISCUSS)
            chunk.append(t.format(x=x, y=y, n=r.randint(2, 12), px=PARAMS[px][0], py=PARAMS[py][0],
                                  vx=PARAMS[px][3](samples[x][px]), vy=PARAMS[py][3](samples[y][py])))
        if i in plant_at:
            s, p = chosen[plant_at.index(i)]
            true = samples[s][p]
            gen = PARAMS[p][2]
            wrong = gen(r)
            for _ in range(50):
                if PARAMS[p][3](wrong) != PARAMS[p][3](true):
                    break
                wrong = gen(r)
            t = r.choice(DISCUSS[1:])
            chunk.insert(r.randint(1, len(chunk)), t.format(x=s, y=s, n=r.randint(2, 12), px=PARAMS[p][0], py=PARAMS[p][0],
                                                           vx=PARAMS[p][3](wrong), vy=PARAMS[p][3](wrong)))
            plants.append({"sample": s, "param": p, "true": PARAMS[p][3](true), "wrong": PARAMS[p][3](wrong),
                           "where": f"раздел {section - 1}, фрагмент {i + 1} из {n_chunks}"})
        body.append(" ".join(chunk) + "\n")
    body += [f"## {section}. Заключение", "", para(INTRO, 5)]
    return head + "\n" + "\n".join(body) + "\n", plants, len(head), n_chunks


TASK = """Ниже рукопись научной статьи. В ней для каждого образца (S-01, S-02, ...) числовые
параметры упоминаются несколько раз в разных разделах. Найди ВСЕ случаи, когда один и тот
же параметр одного и того же образца указан в разных местах рукописи по-разному.
Литературные значения для других материалов (со ссылками вида [12]) не в счёт.

Ответь строго JSON-массивом, без текста вокруг:
[{"sample": "S-07", "param": "дзета-потенциал", "values": ["−31 мВ", "−24 мВ"]}, ...]
Если противоречий нет - пустой массив [].

=== РУКОПИСЬ ===
"""


def ask(model: str, content: str, key: str) -> tuple[str, dict]:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": content}],
                       "max_tokens": MAX_TOKENS, "temperature": 0}).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/HolubVasy/poly-mind-infra", "X-Title": "poly-mind-infra longctx"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.load(resp)
    if data.get("error"):
        raise RuntimeError(json.dumps(data["error"], ensure_ascii=False)[:200])
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"empty choices: {json.dumps(data)[:200]}")
    return (choices[0].get("message") or {}).get("content") or "", data.get("usage") or {}


def canon_param(text: str) -> str | None:
    t = text.lower()
    for p, words in PARAM_WORDS.items():
        if any(w in t for w in words):
            return p
    return None


def grade(answer: str, plants: list[dict]) -> dict:
    m = re.search(r"\[.*\]", answer, re.S)
    try:
        items = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        items = None
    if not isinstance(items, list):
        return {"parsed": False, "found": 0, "false": 0, "recall": 0.0, "f1": 0.0, "reported": 0}
    key = {(p["sample"], p["param"]) for p in plants}
    seen, hits, false = set(), 0, 0
    for it in items:
        if not isinstance(it, dict):
            continue
        s = str(it.get("sample", "")).strip().upper().replace("S", "S", 1)
        s = re.sub(r"^S-?(\d)$", r"S-0\1", re.sub(r"\s", "", s))
        s = re.sub(r"^S(\d\d)$", r"S-\1", s)
        p = canon_param(str(it.get("param", "")))
        if (s, p) in seen:
            continue
        seen.add((s, p))
        if (s, p) in key:
            hits += 1
        else:
            false += 1
    recall = hits / len(key) if key else 1.0
    precision = hits / (hits + false) if hits + false else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"parsed": True, "found": hits, "false": false, "recall": recall, "f1": f1, "reported": len(seen)}


def load_models(only: list[str] | None, extra: list[str]) -> list[dict]:
    slots = yaml.safe_load(SLOTS_PATH.read_text(encoding="utf-8"))
    out = []
    for vendor in slots["vendors"]:
        for category in slots["categories"]:
            for m in vendor.get(category) or []:
                if not only or m["id"] in only:
                    out.append({"id": m["id"], "label": m["label"]})
    out += [{"id": e, "label": e.split("/")[-1] + " (гость)"} for e in extra]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tokens", default="50000,200000")
    ap.add_argument("--models")
    ap.add_argument("--extra", default="")
    ap.add_argument("--plants", type=int, default=8)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sizes = [int(x) for x in args.tokens.split(",") if x]
    models = load_models(args.models.split(",") if args.models else None, [e for e in args.extra.split(",") if e])
    docs = {n: build(n, args.plants, args.seed) for n in sizes}
    for n, (text, plants) in docs.items():
        print(f"~{n} tokens: {len(text)} chars, {len(plants)} plants", file=sys.stderr)
        for p in plants:
            print(f"   {p['sample']} {p['param']:12} {p['true']:>10} vs {p['wrong']:>10}  ({p['where']})", file=sys.stderr)
    if args.dry_run:
        return 0
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("ERROR: OPENROUTER_API_KEY is not set", file=sys.stderr)
        return 2

    jobs = [(n, m) for n in sizes for m in models]
    results: dict[tuple[int, str], dict] = {}

    def run(job):
        n, m = job
        t0 = time.time()
        try:
            text, usage = ask(m["id"], TASK + docs[n][0], key)
            g = grade(text, docs[n][1])
            err = None
        except (urllib.error.URLError, RuntimeError, TimeoutError, OSError) as e:
            text, usage, g, err = "", {}, grade("", docs[n][1]), str(e)[:200]
        return job, {"text": text, "usage": usage, "grade": g, "error": err, "seconds": round(time.time() - t0)}

    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for (n, m), res in ex.map(run, jobs):
            results[(n, m["id"])] = res
            g = res["grade"]
            print(f"  {n:>7} {m['id']:32} found {g['found']}/{len(docs[n][1])} false {g['false']}"
                  f"{' ERROR ' + res['error'] if res['error'] else ''}", file=sys.stderr)

    cost = sum(float(r["usage"].get("cost") or 0) for r in results.values())
    day = datetime.now(timezone.utc).date().isoformat()
    out = Path(args.out) if args.out else ROOT / "docs" / f"longctx-{day}.md"
    lines = [f"# Длинный контекст {day}", "",
             f"Рукопись генерируется из seed {args.seed}; в неё зашито по {args.plants} противоречий "
             "(один и тот же параметр одного образца указан в двух местах по-разному). Модель должна найти все. "
             "Проверка по ключу, без судьи. «Нашла» - сколько из зашитых, «выдумала» - сколько названных "
             f"пар образец/параметр в ключе нет. F1 объединяет обе. Стоимость: ${cost:.2f}.", ""]
    for n in sizes:
        plants = docs[n][1]
        real = [results[(n, m["id"])]["usage"].get("prompt_tokens") for m in models]
        real = [x for x in real if x]
        lines += [f"## ~{n // 1000} тыс. токенов ({min(real) if real else '?'}-{max(real) if real else '?'} по счёту моделей)", "",
                  "| # | Модель | Нашла | Выдумала | F1 | Секунд |", "|---|---|---|---|---|---|"]
        ranked = sorted(models, key=lambda m: -results[(n, m["id"])]["grade"]["f1"])
        for i, m in enumerate(ranked, 1):
            r = results[(n, m["id"])]
            g = r["grade"]
            note = " (ошибка вызова)" if r["error"] else ("" if g["parsed"] else " (ответ не JSON)")
            lines.append(f"| {i} | {m['label']}{note} | {g['found']}/{len(plants)} | {g['false']} | {g['f1']:.2f} | {r['seconds']} |")
        lines += ["", "Ключ:", ""] + [f"- {p['sample']}, {p['param']}: {p['true']} и {p['wrong']} ({p['where']})" for p in plants] + [""]
    lines += ["## Ответы", ""]
    for n in sizes:
        for m in models:
            r = results[(n, m["id"])]
            body = (r["text"].strip() or f"(нет ответа: {r['error']})").replace("\r\n", "\n")
            lines += [f"<details><summary>~{n // 1000}k · {m['label']}</summary>\n", "````", body, "````", "\n</details>\n"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out}  (${cost:.2f})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
