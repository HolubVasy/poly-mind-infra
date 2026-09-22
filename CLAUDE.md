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
it, matching by `presetId` (a rename updates in place). Before writing it copies
the current presets to a collection `presets_backup_<timestamp>`.

Consequence: a preset created in the chat UI is deleted by the next deploy.

**`presets.json` is itself generated** from `models/slots.yaml` by
`scripts/build_presets.py`. Change models in `slots.yaml`, run the script, commit
both. `validate.py` fails when `presets.json` is not byte for byte what
`slots.yaml` generates - so nobody edits it by hand or types a price marker.

`slots.yaml` in one breath: vendors (Claude, OpenAI, Grok, Gemini, Kimi, GLM,
plus the cheap ones kept from before), three categories each - `flagship`,
`frontier`, `workhorse` - and in each category any number of models, at most
`max_models` (15) in total. A model = OpenRouter id, a stable `presetId`, a short
`label`, and `out_per_m`, the output price OpenRouter reports. Preset = slot, not
model: a new version of a line replaces the entry in place and keeps its
`presetId`, so the mother sees the same preset with a new version in brackets.

**Title format**, assembled by `build_presets.py`, never typed:
`<colour> x<N> | <icon> <Vendor> · <category> (<label>)`, e.g.
`🔴 x20 | 🧠 Claude · флагман (Fable 5.1)`.
- `x<N>` = `out_per_m / price_unit` (2.5), rounded: Sonnet 5 (10/M) is x4,
  Opus 5 (25/M) x10, Fable 5.1 (50/M) x20.
- Colour by N: `⚪️` up to x1, `🟢` up to x7, `🔴` above. Icon by category:
  `🧠` flagship, `🔥` frontier, `⚡` workhorse. All thresholds are in `slots.yaml`.

**The rule that broke the presets on 2026-09-22:** a preset's `model` must be in
the `models.default` list of its `endpoint` in `librechat.yaml`. If it is not,
LibreChat does not fail - it silently answers with the FIRST model of that list
(`anthropic/claude-fable-5.1` for "Все"), while the UI shows the preset.
`validate.py` enforces this for `presets.json` and for `slots.yaml`. Endpoint-level
`fetch:` keys are ignored by LibreChat (it reads `models.fetch`), so model lists
are exactly what is written.

The first model of each list is also the silent fallback - keep a sensible,
not-too-expensive model first.

## Monthly model review

`Model check` runs on the 1st of each month at 06:00 UTC, and on demand. The
owner's part is one Telegram message a month: open the pull request, read the
before -> after table, merge. Nothing else - no lists to edit, no models to look
up, no scripts to run.

Who this serves: the mother, writing and editing scientific texts in Russian
(nanoparticle methods, literature search, article editing). Quality of Russian
and reliability beat novelty. Cost matters: the owner pays per token.

What the review does, in order:
1. `scripts/check_models.py` compares `slots.yaml` and the endpoint lists with
   the OpenRouter catalogue: vanished models, newer models per vendor, prices.
2. For every slot, the newest model of the same line and category is the
   candidate (GPT-5.2 -> GPT-5.6, Sonnet 5 -> Sonnet 5.1). A slot is filled only
   from its own vendor; categories never mix (a Flash never replaces a Pro).
3. **Quality gate.** The candidate and the current model of that slot get the
   same standard test prompt from `tests/standard_prompt.md` (a short Russian
   scientific-editing task). A judge - the current Claude flagship - compares
   the two answers blind. Candidate worse -> the slot is NOT changed; the
   verdict and both answers go to `docs/model-log.md` with the date, so the
   reasoning is on record. Equal or better -> it goes into the pull request.
   No answer, or not in Russian -> not in the pull request. A vanished model
   has no current answer to compare with: its successor goes in without the
   gate. Run by hand: `OPENROUTER_API_KEY=... python scripts/judge.py --slot
   "Claude/frontier" --current <id> --candidate <id> --judge <flagship id>`;
   it prints one JSON line with `verdict` better / equal / worse / failed.
   First check on 2026-09-22 (Opus 5 vs Sonnet 5, judge Fable 5.1): about
   50 s and a few cents per pair.
4. Prices in `slots.yaml` are refreshed from the catalogue
   (`check_models.py --update-prices`), `build_presets.py` regenerates the
   titles.
5. ONE pull request with a before -> after table (slot, old model, new model,
   old price, new price, why). Label `dead-models-only` when every change only
   replaces a model missing from OpenRouter: such a preset is already broken,
   so the PR is merged and deployed at once. Anything else waits for the owner.
6. A Telegram message with the link, sent by a plain `curl` from the workflow
   (no Claude in that step). Silent when there is no pull request.

Rules that bind whoever edits `slots.yaml`, human or Claude:
- A newer model in the same slot replaces the old entry: same `presetId`, new
  `id`, new `label`, new `out_per_m`. The replaced model leaves the endpoint
  list too, unless another slot still uses it.
- A vanished model (absent from OpenRouter) is replaced by its direct
  successor: same vendor, same category, newest release of that line. No
  successor -> the previous version of the line; a slot never stays empty
  because of a vanished model.
- Vendors: Claude, OpenAI, Grok, Gemini, Kimi, GLM stay. A new vendor is added
  only after it won the quality gate against the model it would replace. A
  vendor block may hold an empty category.
- At most `max_models` presets in total. Beyond the cap a model replaces one,
  it is not added next to it.
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
