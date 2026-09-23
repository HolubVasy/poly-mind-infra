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
| `librechat/deploy-compose.yml` | `/opt/LibreChat/deploy-compose.yml` | Only its `client` service (LibreChat-NGINX) is used |
| `nginx/nginx.conf` | `/opt/LibreChat/client/nginx.conf` | TLS, basic auth, proxy for chat and forpost |
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

## How a change reaches the server

1. Pull request. `Validate` runs `scripts/validate.py` and syntax checks.
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
downtime for the chat). `nginx.conf` -> `nginx -t`, then `nginx -s reload` (no
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

`slots.yaml`: vendors (Claude, OpenAI, Gemini, Grok, GLM, Kimi, then the cheap
extras DeepSeek and MiniMax), three categories each, top to bottom -
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
and nothing is added to fill a grid. Iteration 1, approved by the owner on
2026-09-23:

| | flagship | workhorse | cheap |
|---|---|---|---|
| Claude | Fable 5.1 | Opus 5.5, Sonnet 5 | - |
| OpenAI | GPT-6 Astra Pro | GPT-5.6 Terra Pro | GPT-6 Luna Pro |
| Gemini | - | - | Gemini 3.8 Flash |
| Grok | - | Grok 4.7 | - |
| GLM | - | GLM 5.3 | - |
| Kimi | - | Kimi K3 | - |
| DeepSeek (extra) | - | - | DeepSeek V4 |
| MiniMax (extra) | - | - | MiniMax M3 |

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
`build_presets.py` assigns it - category top to bottom, then vendors in the
order they are listed in `slots.yaml`, then the dearer model first when one
vendor has two on a shelf. Every vendor sits in the same place on every shelf;
the order moves only when the owner reorders the vendor list.

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
4. Telegram by a plain `curl`: the link plus those lines. Silent when there
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
- Categories, vendors, the vendor order and empty shelves are the owner's
  decisions. Claude never moves a model between categories, never fills a
  shelf, never adds a vendor. A new line (a new word in a vendor's ids) is
  placed by the owner.
- Never: delete or rename endpoints, touch `nginx/`, `certbot/`, compose files
  or scripts, edit `presets.json` by hand.

## Server facts

- Host `145.63.130.166`, Zomro "Optimal AMD", Germany, Ubuntu 22.04. The box
  must stay in Europe: the mother's route from Belarus to Germany is the good one.
- Containers: `LibreChat` (image pinned by digest in the override - the current
  upstream image refuses the default `JWT_SECRET`), `LibreChat-NGINX`,
  `chat-mongodb`, `chat-meilisearch`, `vectordb`, `rag_api`, `forpost`, and the
  job-search `job_search_db` (managed from its own repo, not here).
- DNS at Namecheap: only `chat` and `forpost` A records, both to this host.
- Certificates: host `certbot.timer`, standalone on port 80; the hooks stop and
  start `LibreChat-NGINX`. `ufw` allows 80/tcp for that. Docker publishes
  container ports around `ufw`, so `ufw` protects nothing else.
- Registration is closed (`ALLOW_REGISTRATION=false` in `.env`); strangers had
  signed up through `/api`, which is outside basic auth.

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
