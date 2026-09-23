# Model evaluation for chat.poly-mind.net, 22-23 September 2026

Everything that was tested to decide which models the chat offers, how they are
ranked, and what the owner's mother should use for what. Raw reports and every
model answer are in this folder (`bench-*.md`, `longctx-*.md`, `model-log.md`);
scripts in `scripts/` (`bench.py`, `longctx.py`, `judge.py`).

## 1. What was tested

| Test | Method | Scored by | Cost |
|---|---|---|---|
| **Bench, run 1** (22 Sep) | 11 models x 5 short tasks from her real work | 3 judges, blind, Borda | $5.23 |
| **Bench, run 2** (23 Sep) | same, plus Opus 5.5 as a guest | same | $4.36 |
| **Long context, 50k / 200k tokens** | seed-generated manuscript with 8 planted contradictions | key (no judge) | ~$17 incl. two retries |
| **Long context, tiered 7k / 13k / 100k** | same, 3 / 5 / 8 plants, answer budget 8k | key | $5.72 |
| **Sol Pro vs Terra Pro** (23 Sep) | bench 2 models x 5 tasks; long context 100k / 200k for Sol | 2 judges (Astra Pro skips OpenAI); key | $0.92 + $1.59 |
| **Pairwise judge** (`judge.py`) | candidate vs current on one standard prompt | 1 judge, blind | cents per pair |
| **Her usage log** | MongoDB `transactions`, Feb-Sep 2026 | - | free |

Total spent on evaluation: about $31 - more than any month of her actual use
except February. Should have been ~$7: fewer models, no 200k tier, no full
reruns, reasoning models capped at 8k output.

### The five short tasks (`tests/bench_prompts.md`)

1. **edit** - correct a paragraph of a chemistry paper (planted grammar, unit and
   logic errors), keep the author's meaning, list the changes.
2. **method** - write a Materials & Methods section from a list of data, add
   nothing, list what is missing.
3. **sources** - plan a Scopus/WoS literature search: five different queries,
   what each catches, what such a search misses. No fake references.
4. **terms** - Russian equivalents for ten nanochemistry terms, as a table.
5. **shrink** - compress a conclusion paragraph to 60-80 words keeping every
   number and the author's claim.

Judges: Claude Fable 5.1, GPT-6 Astra Pro, Grok 4.7. Each judge ranks all
anonymised, shuffled answers to a task in one call and never grades its own
vendor. Score = Borda place scaled 0..1, averaged.

### The long-context test (`scripts/longctx.py`)

A Russian manuscript about silver nanoparticle samples is generated from a
fixed seed. Every sample's parameters (size, zeta potential, PDI, plasmon peak,
temperature, time, pH) are restated many times with the same values; N of them
are restated with a different value far away. Literature values for other
materials are sprinkled in as distractors. The model must list every
contradiction as JSON; recall, false alarms and F1 are computed against the key.

## 2. Results

### 2.1 Bench, two runs averaged (0..1, higher is better)

| Model | $/1M out | Run 1 | Run 2 | Avg |
|---|---|---|---|---|
| Fable 5.1 | 50 | 0.67 | 0.72 | **0.70** |
| Grok 4.7 | 4.8 | 0.67 | 0.66 | **0.67** |
| Opus 5.5 (guest) | 20 | - | 0.64 | 0.64 |
| GPT-6 Luna Pro | 0.5 | 0.61 | 0.65 | **0.63** |
| GPT-6 Astra Pro | 50 | 0.63 | 0.57 | 0.60 |
| Gemini 3.8 Flash | 3.75 | 0.64 | 0.52 | 0.58 |
| Kimi K3 | 15 | 0.60 | 0.54 | 0.57 |
| GPT-5.6 Terra Pro | 12 | 0.57 | 0.52 | 0.54 |
| DeepSeek V4 | 1.98 | 0.40 | 0.35 | 0.38 |
| GLM 5.3 | 2.05 | 0.29 | 0.46 | 0.38 |
| MiniMax M3 | 1.2 | 0.26 | 0.37 | 0.32 |
| Sonnet 5 | 10 | 0.30 | 0.13 | **0.21** |

Judge agreement (Spearman): +0.60 and +0.66. Top and bottom are stable; places
4-8 are within noise. On the **edit** task agreement is near zero: editing
quality is a matter of taste even between flagships.

### 2.2 Bench by task (mean place, 0 = always first, 1 = always last)

| | edit | method | sources | terms | shrink |
|---|---|---|---|---|---|
| Fable 5.1 | **0.16** | 0.61 | **0.15** | **0.18** | 0.41 |
| Opus 5.5 | **1.00** | **0.06** | 0.29 | **0.00** | **0.10** |
| Astra Pro | **0.97** | 0.41 | **0.12** | **0.14** | 0.29 |
| Grok 4.7 | 0.38 | **0.17** | 0.40 | 0.66 | 0.26 |
| Terra Pro | 0.66 | 0.38 | **0.18** | 0.25 | 0.59 |
| Luna Pro | 0.66 | **0.14** | 0.59 | 0.44 | **0.16** |
| Gemini Flash | 0.27 | 0.43 | 0.53 | 0.45 | 0.40 |
| Kimi K3 | 0.48 | 0.16 | 0.16 | 0.51 | 0.87 |
| DeepSeek V4 | 0.30 | 0.94 | 0.88 | 0.94 | **0.13** |
| GLM 5.3 | 0.36 | 0.79 | 0.74 | 0.35 | 0.81 |
| MiniMax M3 | 0.50 | 0.65 | 0.81 | 0.84 | 0.74 |
| Sonnet 5 | 0.64 | 0.82 | 0.82 | 0.76 | 0.86 |

### 2.3 Long context (found / planted, false alarms)

| Model | ~7k | ~13k | ~50k | ~100k | ~200k |
|---|---|---|---|---|---|
| Opus 5.5 | 3/3 | 5/5 | 8/8 | **8/8** | **8/8** |
| GPT-6 Astra Pro | 3/3 | 5/5 | 8/8 | **8/8** | **8/8** |
| GPT-5.6 Terra Pro | 3/3 | 5/5 | 8/8 | **8/8** | **8/8** |
| Grok 4.7 | 3/3 | 5/5 | 8/8 | not reached (402) | **8/8** |
| Gemini 3.8 Flash | 3/3 | 5/5 | 8/8 | 8/8 (at the output limit) | 0/8 - derailed into listing everything |
| GPT-6 Luna Pro | 3/3 | 5/5 | 8/8 | 6/8 | 5/8, 1 false |
| Fable 5.1 | 3/3 | 5/5 | 8/8 | **0/8** - budget spent thinking | **0/8** - same, 32k tokens |
| Sonnet 5 | - | - | 8/8 (18k output tokens) | - | 402 |
| Kimi K3 | - | - | 8/8 (30k output tokens, 8 min) | - | 402 |
| DeepSeek V4 | - | - | 8/8, **2 false** | - | 402 |
| MiniMax M3 | - | - | 8/8 | - | 0/8 - 32k tokens, no answer |
| GLM 5.3 | - | - | **0/8** twice - thinking overflow | - | 402 |

The same document is counted very differently by different tokenizers:
the ~7k document ranged from 5,273 to 23,060 prompt tokens across the seven
menu models (4.4x). Per-model numbers were not kept; measuring them costs
about $0.20 and would correct the price markers for Russian text.

### 2.4 Speed and verbosity (short tasks, mean of 10 answers)

| Model | seconds | chars | notes |
|---|---|---|---|
| Sonnet 5 | 20 | 1900 | hidden reasoning on long docs (18k tokens, 116 s) |
| Gemini Flash | 22 | 2500 | many bold marks and tables |
| Terra Pro | 28 | 2400 | |
| Astra Pro | 30 | 2500 | most tables/bold; 300-1000 output tokens on long docs, 10-20 s at any size |
| Opus 5.5 | 30 | 3000 | 800-2000 output tokens on long docs |
| Luna Pro | 30 | 2100 | up to 15k output tokens on 100k |
| Fable 5.1 | 42 | 2800 | 8k-32k thinking tokens on 100k+, never finishes |
| Grok 4.7 | 45 | 1800 | plain prose; 206 s at 50k, 451 s at 200k |
| Kimi K3 | 96 | 2100 | 30k tokens per long answer |

Effective cost per answer differs from list price: Astra Pro (~$0.05) is cheap
because it answers briefly; Fable on a long document costs $0.40-1.60 per
attempt and returns nothing.

### 2.5 Her actual usage (chat log, Feb-Sep 2026)

| Month | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep |
|---|---|---|---|---|---|---|---|---|
| $ | 56 | 15 | 21 | 26 | 46 | 13 | 0.3 | 2.8 |

All time $181: Opus 4.6 $120 (203 requests), GPT-5.2 $45 (600 requests),
everything else $16. September: GPT-6 Astra 21 requests, Fable 17, Gemini
Flash 9, Opus 5 5, Astra Pro 2, Sonnet 2. Input per request: 12k (Astra),
14k (Fable), 22k (Opus 4.6), 37k (GPT-5.2) - long chats resend the whole
history. One Opus 5 answer of 31,277 tokens cost $0.78.

## 3. Failure modes seen

- **Sonnet 5**: rewrites the author's meaning, drops comparisons; last on 4 of 5
  tasks; hidden reasoning makes it slow.
- **Kimi K3**: Chinese characters inside Russian text, wrong terms
  («обжиг» for annealing, «сонификация»), 6 first places and 3 last - erratic.
- **DeepSeek V4**: invents (2 false contradictions), yet best at shrinking.
- **GLM 5.3**: never answers a document of 50k+ tokens.
- **Gemini Flash at 200k**: stops doing the task, lists everything.
- **Luna Pro**: unstable - one run "added a typo and an invented edit", the
  next "clean and accurate".
- **Fable 5.1 on 100k+ tokens**: three of three runs spend the whole output
  budget thinking and return nothing; confirmed on her own report in the chat.
- **Strong models on editing**: Opus 5.5 and Astra Pro are last on `edit` -
  they improve the text instead of correcting it ("removed the author's claim
  about TEM/DLS agreement", "undeclared stylistic changes").

## 4. Decisions taken

- **Menu (7 presets)**, ranked by strength inside each shelf on this evidence:
  🧠 Fable 5.1, GPT-6 Astra Pro · ⚙️ Grok 4.7, Opus 5.5, GPT-5.6 Terra Pro ·
  ⚡ GPT-6 Luna Pro, Gemini 3.8 Flash.
- **GPT-6 Sol Pro replaced GPT-5.6 Terra Pro** in the OpenAI workhorse slot
  (same `presetId`, same rank). Sol 0.60 against Terra 0.40 in a blind
  two-model bench: Sol took method, sources and shrink, Terra edit and terms,
  both judges agreeing on every task (`bench-2026-09-23-sol.md`). Long
  context 8/8, no false alarms, at 100k and 200k, as Terra
  (`longctx-2026-09-23-sol.md`). $10 against $12 per 1M output. Order in the
  menu: Opus, Sol, Grok (owner). Terra's rows above are kept as measured.
- **Dropped**: Sonnet 5, Kimi K3, DeepSeek V4, GLM 5.3, MiniMax M3.
- **Opus 5.5 returned** (third in the bench, 8/8 at 200k). Astra Pro kept as
  the OpenAI flagship (same price as plain Astra she used to pick).
- **Categories** are the vendor's positioning, not price; no "frontier" shelf;
  empty shelves are legitimate.
- **Monthly automation** does one thing: newer version of the same line ->
  `judge.py` -> one PR -> Telegram. Nothing merges on its own.
- `max_tokens: 2048` in `librechat.yaml` is ignored by LibreChat (not in its
  schema); answers of 10k-31k tokens are in the log, so nothing is capped.

## 5. What to use for what (see `памятка.md` for the mother's version)

| Task | Model | Evidence |
|---|---|---|
| Edit a chapter, keep the author's voice | Fable 5.1, chapter by chapter | best on `edit` (0.16); fails beyond ~50 pages |
| Read a thesis / 100-200 pages, find inconsistencies | Astra Pro (or Opus 5.5) | 8/8 at 100k and 200k, 20 s, short answers |
| Analyse experiment data, derive mechanisms | Opus 5.5, Astra Pro as second opinion | never invented a value; first on terms/method |
| Plan an experiment, write Methods | Luna draft -> Opus 5.5 | Luna 0.14 on method at $0.5 |
| Write a section of a paper/thesis | Opus 5.5 | first on method, terms, shrink |
| Read an ordinary paper (10-20 pages), ask about it | Grok 4.7 (cheap, 1 min) or Astra Pro (10 s) | all models flawless at <=15k tokens |
| Literature search queries | Astra Pro or Fable | 0.12 / 0.15 on `sources` |
| Terms, translation | Opus 5.5 | 0.00 on `terms` |
| Compress a paragraph | Opus 5.5 or Luna | 0.10 / 0.16 |
| Everyday questions | Luna or Gemini Flash | cheapest; health questions - Opus, and a doctor |

Rules: new chat per task (history is resent every message); start cheap;
big documents only with Astra Pro or Opus, ideally in two steps (Astra Pro
digest first, then anything on the digest); attach files for questions
instead of pasting.
