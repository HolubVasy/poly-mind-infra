# CLAUDE.md

Rules for any Claude session or workflow working in this repository. Read it
whole before changing anything.

## What this repository is

The configuration of the owner's self-hosted chat, `https://chat.poly-mind.net`
(LibreChat), and of the reverse proxy in front of it. The owner's mother uses this
chat every working day from Belarus; it is her main work tool. **Keeping it up
and answering with the model she picked matters more than anything else here.**

This repository is the only source of truth for the files listed below. Nothing
is edited on the server by hand: a change is a pull request, a merge deploys it.
Server-side edits made outside this repo are overwritten by the next deploy.

Not in this repository, on purpose:
- `/opt/LibreChat/.env` - API keys and secrets. `librechat.yaml` refers to them as
  `${OPENROUTER_API_KEY}`; `scripts/validate.py` rejects a literal key.
- `/opt/LibreChat/client/.htpasswd` - the basic-auth password hash.
- Data: MongoDB (chats, users), pgvector, uploads. Only presets are managed here.
- The LibreChat code itself. `/opt/LibreChat` is a checkout of upstream LibreChat
  (Feb 2026) with our files laid over it.

## Layout

| Repo path | Live path on the server | What it does |
|---|---|---|
| `librechat/librechat.yaml` | `/opt/LibreChat/librechat.yaml` | Endpoints and their model lists |
| `librechat/docker-compose.override.yml` | `/opt/LibreChat/docker-compose.override.yml` | Pins the LibreChat image, mounts |
| `librechat/secrets-generation` | `/opt/LibreChat/.secrets-generation` | A bare number; raising it makes `apply.sh` rotate the secrets in `.env` on the server |
| `librechat/deploy-compose.yml` | `/opt/LibreChat/deploy-compose.yml` | Only its `client` service (LibreChat-NGINX) is used |
| `nginx/nginx.conf` | `/opt/LibreChat/client/nginx.conf` | TLS, basic auth, proxy for chat, forpost and jobs |
| `certbot/renewal-hooks/{pre,post}/*.sh` | `/etc/letsencrypt/renewal-hooks/...` | Stop/start nginx around cert renewal |
| `models/slots.yaml` | - | Which models the chat offers: vendor x category, with prices. Source of `presets.json` |
| `presets/presets.json` | MongoDB `LibreChat.presets` | The presets in the chat's preset menu. Generated, do not edit |
| `scripts/validate.py` | - | Static checks (PR, deploy, server) |
| `scripts/apply.sh` | runs from `/opt/poly-mind-infra` | Applies main to the server |
| `scripts/apply_presets.js` | runs in `chat-mongodb` | Syncs presets.json into MongoDB |
| `scripts/remote-entry.sh` | `/usr/local/sbin/poly-mind-apply` | The only command the deploy key may run |
| `scripts/build_presets.py` | - | Generates `presets.json` from `slots.yaml` |
| `scripts/check_models.py` | - | Facts for the monthly model review |
| `scripts/judge.py` | - | Quality gate: candidate vs current on `tests/standard_prompt.md`, verdict to `docs/model-log.md` |
| `scripts/gate_check.py` | - | Guard: every replaced model vanished or won its verdict today; writes the Telegram lines |
| `docs/model-log.md` | - | Every verdict with both answers; written by `judge.py` only |
| `docs/памятка.md` | MongoDB, inside the ❓ preset | THE памятка, one source of truth. «❓ Какую кнопку?» reads it; the .docx is built from it; its menu table is generated |
| `docs/памятка.docx` | - | The mother's Word памятка. Rebuilt from the .md by the `Memo` workflow after every merge, do not edit |
| `scripts/strength_check.py` | - | Long-text signal on a replacement: old vs new on a ~100k manuscript, capped at $5 |
| `scripts/balance_check.py` | - | One Telegram message when the OpenRouter balance falls below $1 (workflow `Balance`, daily 06:00 UTC) |
| `scripts/memo_docx.js` | - | Converts `docs/памятка.md` to `docs/памятка.docx` (`npm ci` first); `--check` says whether the .docx is current |

## How a change reaches the server

1. Pull request. `Claude review` runs `Validate` (`scripts/validate.py` and
   syntax checks) as its `checks` job, then reviews the diff (see Conventions).
2. Merge to `main`. `Deploy` connects with `DEPLOY_SSH_KEY`; the server's
   authorized_keys forces that key to run `/usr/local/sbin/poly-mind-apply`,
   which resets `/opt/poly-mind-infra` to `origin/main` and runs `scripts/apply.sh`.
3. `apply.sh` validates again, rewrites only files that differ (backup
   `<file>.bak-<timestamp>` next to each), syncs presets, restarts only what
   needs it, then waits for `https://chat.poly-mind.net/health` = 200. If the chat
   is not healthy it restores every file of that run and restarts again.

Dry run: Actions -> Deploy -> Run workflow -> dry_run. Prints the diff, changes
nothing.

What restarts: `librechat.yaml` -> `docker restart LibreChat` (about 10 s of
downtime for the chat). A new image in the override -> first a `mongodump` to
`/root/backup/librechat_before_deploy_<ts>.archive.gz` (a new version may
migrate the database, and putting the old file back does not undo that), a
`docker compose pull` while the old container still serves, then the
restart; a rollback runs `docker compose up -d` again so the old image comes
back. Every image change goes through the `Image smoke test` workflow first:
the pinned image is started in CI on an empty MongoDB with our
`librechat.yaml`, registered into, and must list the "Все" endpoint with
exactly our models and return every preset. `nginx.conf` -> `nginx -t`, then `nginx -s reload` (no
downtime; a failing `nginx -t` aborts and rolls back). Compose files ->
`docker compose up -d` plus the nginx `client` service. Presets -> nothing, they
are read from the database per request. **Merge config changes when the mother is
not in the chat** (evenings Minsk time are safest).

## Presets

Presets live in MongoDB, owned by the single ADMIN account. The mother logs in to
that same account, so these are her presets. `presets/presets.json` is the whole
truth for the database: `apply_presets.js` adds, updates and **deletes** to match
it, matching by `presetId` (a rename updates in place), after copying the current
presets to a collection `presets_backup_<timestamp>`. A preset created in the
chat UI is deleted by the next deploy.

**`presets.json` is generated** from `models/slots.yaml` by
`scripts/build_presets.py`. Change models in `slots.yaml`, run the script, commit
both; `validate.py` fails when the file is not byte for byte what `slots.yaml`
generates, so nobody edits it by hand or types a price marker.

`slots.yaml`: vendors (Claude, OpenAI, Gemini, Grok), three categories each, top to bottom -
`flagship` (exactly ONE model: the one the vendor positions as its best),
`workhorse` (the everyday model; a vendor's only strong line lives here),
`cheap` (cost-effective, for simple tasks) - at
most `max_models` (20) in total. A model = OpenRouter `id`, a stable
`presetId`, a short `label`, a `line` (the word in the id that names its
line: sonnet, terra-pro, flash) and `out_per_m`, the output price OpenRouter
reports.

The category is the owner's call, by how the vendor positions the model - not
by price, not computed. There is no "frontier" shelf on purpose: "a step
below the flagship" is a tier for vendors, not for the mother (Opus at twice
the price of Sonnet was neither here nor there - dropped 2026-09-23). Empty
shelves are legitimate: a vendor that sells no model of a rung has none here,
and nothing is added to fill a grid. Current set:

| | flagship | workhorse | cheap |
|---|---|---|---|
| Claude | Fable 5.1 | Opus 5.5 | - |
| OpenAI | GPT-6 Astra Pro | GPT-5.6 Terra Pro | GPT-6 Luna Pro |
| Gemini | - | - | Gemini 3.8 Flash |
| Grok | - | Grok 4.7 | - |

Iteration 2, 2026-09-23, decided on evidence: two blind bench runs
(`docs/bench-2026-09-22.md`, `docs/bench-2026-09-23.md`) and the long-context
test (`docs/longctx-2026-09-23.md`). Dropped: Sonnet 5 (last in both bench
runs), Kimi K3 ($15, mid-table), DeepSeek V4, GLM 5.3 and MiniMax M3 (bottom
half; GLM never answered the long manuscript). Opus 5.5 came back: third in
the bench, 8/8 at 200k tokens. OpenAI flagship is GPT-6 Astra Pro: same price
as the plain Astra she used to pick, and the Pro is the vendor's top - owner's
call, 2026-09-23. Gemini Flash stays: fine at her sizes (~12k tokens
a request, 8/8 at 50k), used by her, fails only at 200k.

Preset = slot: a new version replaces the entry in place and keeps its
`presetId`, so the mother sees the same preset with a new version.

**Title**, assembled by `build_presets.py`, never typed:
`<icon> <label> · <colour> x<N>`, e.g. `🧠 Fable 5.1 · 🔴 x20`. Icon by
category (`🧠` flagship, `⚙️` workhorse, `⚡` cheap), no
category word and no vendor - LibreChat prints the model id right after the
title in the menu, so anything more is noise. `x<N>` = `out_per_m / 2.5`,
rounded; colour `⚪️` up to x1, `🟢` up to x7, `🔴` above (thresholds in
`slots.yaml`).

**Menu order**: LibreChat sorts presets by their `order` field, and
`build_presets.py` assigns it - category top to bottom, then the owner's
`rank` inside the category (1 = strongest, set in `slots.yaml` on the evidence
in `docs/`: bench and long-context runs), then vendor order, then the dearer
model first. As of 2026-09-23: Fable, Astra Pro; Grok, Opus, Terra; Luna,
Flash. A new version inherits its slot's rank; the rank changes only on the
owner's word. Known limit: Fable 5.1 does not finish on documents of 100k+
tokens (three runs) - for those, Astra Pro or Opus.

**The rule that broke the presets on 2026-09-22:** a preset's `model` must be in
the `models.default` list of its `endpoint` in `librechat.yaml`. If it is not,
LibreChat does not fail - it silently answers with the FIRST model of that list
(`anthropic/claude-fable-5.1` for "Все"), while the UI shows the preset.
`validate.py` enforces this. Endpoint-level `fetch:` keys are ignored by
LibreChat (it reads `models.fetch`), so model lists are exactly what is written.
The first model of each list is also the silent fallback - keep a sensible,
not-too-expensive model first.

## Monthly model review

`Model check` runs on the 1st of each month at 06:00 UTC, and on demand. The
owner's part is one Telegram message a month: open the pull request, read the
before -> after table, merge. Nothing else.

Who this serves: the mother, writing and editing scientific texts in Russian
(nanoparticle methods, literature search, article editing). Quality of Russian
and reliability beat novelty. Cost matters: the owner pays per token.

The robot knows one move: **a newer version of the same line replaces the old
one if it passes the judge.** In order:
1. `scripts/check_models.py` compares `slots.yaml` with the OpenRouter
   catalogue: vanished models, prices (written back with `--update-prices`),
   and per slot the newer models of the same vendor whose id contains the
   slot's `line` (Opus 5 -> Opus 5.5). Variants (`:batch`, `:free`, previews)
   are skipped. Nothing else is ever a candidate: no other lines, no other
   categories, no empty shelves.
2. **Quality gate** - `scripts/judge.py`: the candidate and the current model
   get the same standard prompt from `tests/standard_prompt.md` (a short
   Russian scientific-editing task); a judge model (the Claude flagship slot)
   compares the two answers blind. `better` / `equal` -> the candidate goes
   in; `worse` / `failed` (no answer, not in Russian) -> the slot stays. The
   verdict and both answers go to `docs/model-log.md` (answers fenced, so a
   model cannot forge a verdict line). A vanished model has no current
   answer: its line's newest model goes in without the gate.
3. ONE pull request with a before -> after table (slot, old, new, prices,
   why). `scripts/gate_check.py` re-checks the branch: every replaced or
   added model either vanished from OpenRouter or has a winning verdict
   dated today, otherwise the workflow closes the PR. It also writes one
   Russian line per change for the message.
4. **Long text signal** - `scripts/strength_check.py`: when a model is
   replaced, the old and the new one read the same ~100k-token manuscript
   from `longctx.py` (seed 7, 8 planted contradictions; the size where Fable
   stalls). Found / invented for both go to a PR comment and the Telegram
   message, with "⚠️ хуже" when the new one scores lower. It never blocks:
   the owner decides and moves `rank` if the strength changed (owner,
   2026-09-23). Cost is estimated first with a pessimistic tokenizer and the
   run is skipped above $5 (an Opus pair is about $2, a Fable pair about $5).
5. Telegram by a plain `curl`: the link plus those lines. Silent when there
   is no PR; a failed run does send a message.

Dry run: Actions -> Model check -> Run workflow -> dry_run. Report and price
diff only, no Claude, no PR, no message; needs no secret. Run the judge by
hand: `OPENROUTER_API_KEY=... python scripts/judge.py --slot "Claude/frontier"
--current <id> --candidate <id> --judge <flagship id>` (about 50 s, cents).

Pull requests opened with `GITHUB_TOKEN` do not trigger `Validate`, so the
model-check run itself runs `validate.py` and `gate_check.py` on the branch.

Rules for whoever edits `slots.yaml`, human or Claude:
- A newer model replaces the old entry in place: same `presetId`, new `id`,
  `label`, `out_per_m`; `line` stays. The replaced id leaves the "Все" list
  unless another slot or endpoint still uses it.
- Helpers are not edited: they follow their slot. `docs/памятка.md` names
  models without versions and its menu table (labels, prices) is generated,
  so a replacement normally needs no text edit; `gate_check.py` fails the
  branch while an old full label is still in the .md, and its digest names
  the buttons that moved
  (added 2026-09-23 - before that the buttons stayed on hard-coded ids and a
  replaced or vanished model would have left them behind).
- Categories, vendors, the vendor order and empty shelves are the owner's
  decisions. Claude never moves a model between categories, never fills a
  shelf, never adds a vendor. A new line (a new word in a vendor's ids) is
  placed by the owner.
- Never: delete or rename endpoints, touch `nginx/`, `certbot/`, compose files
  or scripts, edit `presets.json` by hand.

## Balance alert

The mother's chat, the monthly judge and every experiment spend from one
OpenRouter account; at zero the chat stops answering. `Balance` runs daily at
06:00 UTC (before the working day) and sends ONE Telegram message when the
balance has just gone below $1 - not every day while it stays low (owner,
2026-09-23). The last state lives in the Actions cache; a top-up re-arms it.
A regular API key can read `/api/v1/credits`, no management key needed.
Manual run: Actions -> Balance -> Run workflow (dry run by default).

## Server facts

- Host `145.63.130.166`, Zomro "Optimal AMD", Germany, Ubuntu 22.04. The box
  must stay in Europe: the mother's route from Belarus to Germany is the good one.
- Containers: `LibreChat` (stable `librechat:v0.8.7`, pinned by digest in the
  override; until 2026-09-23 a February `librechat-dev` build, pinned because
  newer images refuse the public default `JWT_SECRET`), `LibreChat-NGINX`,
  `chat-mongodb`, `chat-meilisearch`, `vectordb`, `rag_api`, `forpost`, and the
  job-search `job_search_db` and `job_search_app` (managed from their own repo,
  not here; nginx proxies `jobs.poly-mind.net` to `job_search_app:8501`, no
  login by the owner's decision 2026-09-23).
- DNS at Namecheap: `chat`, `forpost` and `jobs` A records, all to this host.
- Certificates: host `certbot.timer`, standalone on port 80; the hooks stop and
  start `LibreChat-NGINX`. `ufw` allows 80/tcp for that. Docker publishes
  container ports around `ufw`, so `ufw` protects nothing else.
- Registration is closed (`ALLOW_REGISTRATION=false` in `.env`); strangers had
  signed up through `/api`, which is outside basic auth.
- Secrets rotate by pull request without ever entering the repo:
  `librechat/secrets-generation` is a bare number. When it goes above the
  number in `/opt/LibreChat/.secrets-generation`, `apply.sh` generates new
  random `JWT_SECRET`, `JWT_REFRESH_SECRET`, `CREDS_KEY`, `CREDS_IV` and
  `MEILI_MASTER_KEY` on the server (`openssl rand`), rewrites them in `.env`
  in place, backs `.env` up, recreates `api`, `rag_api` and `meilisearch`
  (rag_api and meilisearch take them as container env), and rolls `.env`
  back if the chat is not healthy. Everyone is logged out once. Until
  2026-09-23 all five were the public values from LibreChat's
  `.env.example`, so anyone could forge a session for `/api`. `CREDS_*`
  encrypt user-provided keys; this chat stores none (`keys` and
  `pluginauths` are empty), so rotating them loses nothing.

`librechat.yaml` has one endpoint, "Все", whose list is exactly the models the
presets use. The seven old task endpoints («Методика наночастиц», «Редактор
статьи ...») were removed on 2026-09-23 - the log showed one of them used
last in March, the rest never. `fetch:` and `modelOptions:` were removed too:
LibreChat ignores both on a custom endpoint (its schema has only `addParams` /
`dropParams`; the log shows 10k-31k token answers despite `max_tokens: 2048`).
`apply_presets.js` keeps the three newest `presets_backup_*` collections.

`docs/памятка.md` is THE памятка for the mother and its one source of truth
(owner, 2026-09-23): which button for which task, sizes, big documents in
two steps, second opinion, ten habits, three money rules, the menu. Edit
only the .md, on GitHub if you like:
- Prose names models without versions ("Opus", "Fable", "Astra Pro"), so a
  new version needs no edit. Prices appear only in the generated menu table.
- The table between `menu:begin` / `menu:end` is written by
  `build_presets.py` from `slots.yaml` (label, price marker, `purpose`), so
  its prices follow OpenRouter with the monthly refresh.
- It is the instruction text of «❓ Какую кнопку?»: `build_presets.py` copies
  it into that preset's `promptPrefix`.
- `docs/памятка.docx` (her Word copy) is converted from it by
  `scripts/memo_docx.js` in the `Memo` workflow after every merge that
  touches it, and committed by the bot. GitHub alerts (`> [!TIP]`, `[!NOTE]`,
  `[!IMPORTANT]`, `[!CAUTION]`) become coloured boxes, a table row with only
  the first cell filled is a group band, `<!-- pagebreak -->` breaks the page.
Four more helpers are procedure buttons with inline `instructions`:
🧭 Новый вопрос and 🎛 Варианты on the `opus` slot, ✏️ Править текст on
`fable`, 🔍 Рецензия on `astra-pro`; ❓ runs on `luna-pro`. A helper names
its model by a slot's `line` (`slot: opus`), never by id: `build_presets.py`
puts in whatever that slot holds today, so the monthly refresh moves the
buttons with the slot. `validate.py` rejects a helper with a `model:` id, a
`slot` that is no slot's line, and a line used by two slots. Every preset, model buttons
included, starts with `common_prefix` from `slots.yaml` - the owner's line
«Ничего не додумывай… Не знаешь - так и скажи» - because inventing and
guessing were the two failure modes the tests showed.

Lessons already paid for - do not repeat:
- The live files are single-file bind mounts. Rewrite them in place
  (`cat new > file`); `sed -i`, `cp`, `mv` swap the inode and the container keeps
  reading the old file.
- `docker compose up -d` does not notice edits inside `.env`; use
  `--force-recreate` for the service that reads it.
- nginx resolves `api` and `forpost` per request (`resolver 127.0.0.11` plus a
  variable upstream). Keep it that way: a static `proxy_pass http://api:3080`
  pins the container's old address and gives 502 after any recreate.
- `pip`/`docker` pulls on this plan are capped at about 500 write IOPS.

## One-time setup (already done, 2026-09-22)

- `/opt/poly-mind-infra`: clone of this repo via SSH alias `github-poly-mind-infra`
  with the read-only deploy key `/root/.ssh/poly_mind_infra_deploy`.
- `/usr/local/sbin/poly-mind-apply`: copy of `scripts/remote-entry.sh`. If
  `remote-entry.sh` changes, the copy must be refreshed on the server - it is
  the one file the deploy cannot update itself.
- root's authorized_keys: the deploy key with
  `command="/usr/local/sbin/poly-mind-apply",restrict`.
- Repo secrets: `DEPLOY_SSH_KEY` (private half of that key),
  `CLAUDE_CODE_OAUTH_TOKEN` (owner's Claude subscription, `claude setup-token`),
  `OPENROUTER_API_KEY` (for the quality gate), `TELEGRAM_BOT_TOKEN` and
  `TELEGRAM_CHAT_ID` (the monthly message).
- Actions may create pull requests (repo setting).

## Conventions

Personal repository: short imperative commit messages, no ticket prefix, no AI
attribution trailers. Every change goes through a pull request, including the
ones Claude makes.

The process follows the owner's Notion page «Процесс: требования в git, ревью
с Claude» (2026-09-23), the same one job-search uses. In one line: Notion is
status and intent, git is the detail and the instructions.

Where things are written (owner, 2026-09-23):
- **Notion** - plans, constraints, idea drafts, and results after a merge.
  The table «Изменения» on the Self-Hosted Infrastructure page holds one row
  per change: status, the PR, and «Принято ✅» only after a live check, with
  the evidence. The row links the requirements in git, never copies them. It
  is a manual journal: Claude updates it at the end of a session, nothing
  automatic touches it, and where it disagrees with GitHub, GitHub is right.
  CI never reads Notion and holds no Notion token.
- **Git** - the concrete requirements. A small change is described in the
  PR itself, by `.github/pull_request_template.md` (зачем, что меняется, как
  проверено, риск). A big one - more than one file of logic, paid calls, the
  deploy path, or anything the mother sees - also gets a spec in the same
  PR, `docs/changes/<YYYY-MM-DD>-<topic>.md`, from the template in
  `docs/changes/README.md`, with numbered, checkable requirements.
- The border: while an idea is a draft it lives in Notion; once it is taken
  into work its requirements move to git, and Notion keeps a line with the
  link and later the result.

Who decides what (owner, 2026-09-23) - who decides, answers for it:
- **Owner** - what and in which order, and the risks: goals, priorities,
  secrets, DNS, money, codes from SMS.
- **Claude** - how, and the evidence: requirements in git before code, an
  honest report with numbers, the Notion journal, fixing confirmed bugs.
- **Review bot** - decides nothing; answers for findings with a scenario.
- **CI** - decides nothing; answers for the fact, green or red.

Claude's red lines: nothing outside git (server, database, config - only a
PR and the deploy); a merge only after the review verdict; money only within
the agreed cap, anything new and paid gets a price before it runs; secrets
are never written or repeated in chat; security and account risks are never
accepted on the owner's behalf.

Three autonomy baskets (revised when trust changes, and written here):
- **Silently** - design, code, checks, PRs, fixes after review, what to do
  with a PLAUSIBLE finding (the reason written in the PR), Notion rows.
- **Do and report** - a merge after a green verdict and the deploy it
  triggers, changing how the review works.
- **Ask first** - security and account risks, money over the cap, domains and
  DNS, what goes into a spec, a dispute after the third review round, paid
  experiments, anything the mother will notice (a forced re-login, downtime,
  a changed menu).

One change: a row in «Изменения» -> requirements in git (the PR template, a
spec for a big task) -> PR -> review -> fix, at most three rounds -> merge
-> live check -> «Принято ✅» with the evidence.

Every non-draft PR gets a `Claude review` (`claude-review.yml`, uses
`CLAUDE_CODE_OAUTH_TOKEN`). Four steps:
1. `checks` - `validate.yml` called as a reusable workflow; its one-line
   result goes into the review prompt, and a red check is the first finding.
   On a PR this is the only run of `Validate`; on main it runs on its own.
2. Review - bugs only: the live chat breaking, secrets leaking, money running
   away, a gap between the code and the description or the linked spec (a
   missed spec requirement counts). A finding is posted only with a concrete
   scenario (state, file:line, wrong result); no style or polishing notes.
   One inline comment per finding and one summary whose first line is
   `REVIEW <sha7>: N finding(s)`.
3. Verify - only when N > 0: a second run re-reads the findings for the same
   commit and posts `VERIFIED <sha7>: C confirmed, P plausible, R rejected`.
4. Verdict - red when there is no REVIEW line, when findings have no VERIFIED
   line, or when C > 0. PLAUSIBLE and REJECTED do not block; Claude answers
   each PLAUSIBLE one in the PR - fixed or why not.

A round is a push after a REVIEW with findings; a push after «0 findings» is
not a round. Stop when confirmed bugs are 0. After the third round the
workflow posts «Лимит ревью», reviews no more, keeps the last state (red if
bugs were not cleared), and the owner decides: false alarm, or cut the task.
The free private plan has no required checks, so red is the only lock:
nobody, Claude included, merges a PR with a red review or before its verdict.
Cost: one Claude run per push, two when there are findings, a few minutes of
the subscription quota each.

A PR that changes `claude-review.yml` is reviewed by its own new version
(`pull_request` runs the workflow from the PR head, and the action gets
`github_token`, so it does not insist on the file matching main - seen on
#45 and #47). Its description still lists what was checked by hand. The
monthly model-check PR is opened with `GITHUB_TOKEN`, which starts no
workflows, so it gets no checks and no review - the owner reads that one.
