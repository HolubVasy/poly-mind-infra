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
| `presets/presets.json` | MongoDB `LibreChat.presets` | The presets in the chat's preset menu |
| `scripts/validate.py` | - | Static checks (PR, deploy, server) |
| `scripts/apply.sh` | runs from `/opt/poly-mind-infra` | Applies main to the server |
| `scripts/apply_presets.js` | runs in `chat-mongodb` | Syncs presets.json into MongoDB |
| `scripts/remote-entry.sh` | `/usr/local/sbin/poly-mind-apply` | The only command the deploy key may run |
| `scripts/check_models.py` | - | Facts for the monthly model review |

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
truth: `apply_presets.js` adds, updates and **deletes** to match it, matching by
`presetId` (a rename updates in place). Before writing it copies the current
presets to a collection `presets_backup_<timestamp>`.

Consequence: a preset created in the chat UI is deleted by the next deploy. New
presets are added here - give them a fresh UUID as `presetId`.

**The rule that broke the presets on 2026-09-22:** a preset's `model` must be in
the `models.default` list of its `endpoint` in `librechat.yaml`. If it is not,
LibreChat does not fail - it silently answers with the FIRST model of that list
(`anthropic/claude-fable-5.1` for "Все"), while the UI shows the preset.
`validate.py` enforces this. Endpoint-level `fetch:` keys are ignored by
LibreChat (it reads `models.fetch`), so model lists are exactly what is written.

The first model of each list is also the silent fallback - keep a sensible,
not-too-expensive model first.

## Monthly model review

`Model check` runs on the 1st of each month at 06:00 UTC, and on demand. It runs
`scripts/check_models.py` against the OpenRouter catalogue, then a Claude session
decides under these rules. They are binding.

Who this serves: the mother, writing and editing scientific texts in Russian
(nanoparticle methods, literature search, article editing). Quality of Russian
and reliability beat novelty. Cost matters: the owner pays per token.

What the review may do:
1. **Vanished model** (in a preset or a list, absent from OpenRouter): replace it
   with its direct successor - same vendor, same tier (pro -> pro, flash -> flash,
   mini -> mini), the newest release of that line. Keep the preset's `presetId`,
   update the name part of its `title` and its price marker. In endpoint lists,
   put the successor where the old model was. If there is no clear successor,
   remove it from lists and, for a preset, pick the closest model in price and
   tier and say so plainly in the PR.
2. **Newer version** of a model we use (same line, released later, e.g. Sonnet 5
   -> Sonnet 5.1): propose the upgrade if its price is within +25%. Otherwise
   mention it in the PR body only.
3. **Price change** of a model we keep: update the marker in the title if the
   marker changes.

What it must not do: add new presets beyond replacements, delete presets,
change endpoint names or anything outside model ids, titles and model lists,
touch `nginx/`, `certbot/`, compose files or scripts.

Label `dead-models-only` means every change is of type 1. Such a PR is merged and
deployed automatically, because the preset is already broken. Anything of type 2
or 3 in the same PR -> no label -> waits for the owner.

**Title format** `<colour> x<N> | <icon> <Name>`, e.g. `🟢 x4 | 🧠 Claude Sonnet 5`.
Reconstructed from the presets as of 2026-09-22 (the owner may correct it):
- `x<N>` is roughly the output price in USD per 1M tokens divided by 2.5, rounded;
  the cheapest models are `x0`. Sonnet 5 (10/M) is x4, Opus 5 (25/M) is x10,
  Fable 5.1 and GPT-6 Astra (50/M) are x20.
- Colour: `⚪️` budget (about x0-x2), `🟢` middle (x2-x6), `🔴` expensive (x10+).
- Icon: `⚡` fast and cheap, `🔥` strong non-flagship, `🧠` flagship reasoning.
- If the price did not change, keep the existing marker as it is.

## Notifications

`PR reminder` (daily 19:00 UTC) sends the list of open, non-draft pull requests
to the owner's Telegram with plain curl, and stays silent when there are none.
Secrets `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` - the same bot his Claude
briefing routines use. No Claude runs in it.

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
  `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (PR reminder).
- Actions may create pull requests (repo setting).

## Conventions

Personal repository: short imperative commit messages, no ticket prefix, no AI
attribution trailers. Every change goes through a pull request, including the
ones Claude makes.
