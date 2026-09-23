#!/usr/bin/env bash
# Applies this repository (the checkout in /opt/poly-mind-infra) to the live
# server. Runs as root on the server; normally started by the deploy workflow
# through scripts/remote-entry.sh, never by hand-editing the live files.
#
# Idempotent: files that already match are not touched and nothing restarts.
# DRY_RUN=1 prints what would change and changes nothing.
#
# Safety net: every replaced file is backed up next to itself as
# <file>.bak-<timestamp>. If the chat does not come back healthy after the
# change, all files of this run are restored and the services restarted again.
set -euo pipefail

REPO=/opt/poly-mind-infra
LC=/opt/LibreChat
TS=$(date -u +%Y%m%dT%H%M%SZ)
DRY=${DRY_RUN:-0}
HEALTH_URL=https://chat.poly-mind.net/health

log() { echo "[apply $TS] $*"; }

# repo path : live path. The live files are single-file bind mounts into the
# LibreChat and nginx containers, so they are rewritten in place (cat >) to
# keep the inode; `cp`/`mv`/`sed -i` would leave the containers reading the
# old file.
FILES=(
  "librechat/librechat.yaml:$LC/librechat.yaml"
  "librechat/docker-compose.override.yml:$LC/docker-compose.override.yml"
  "librechat/deploy-compose.yml:$LC/deploy-compose.yml"
  "nginx/nginx.conf:$LC/client/nginx.conf"
  "certbot/renewal-hooks/pre/stop-nginx.sh:/etc/letsencrypt/renewal-hooks/pre/stop-nginx.sh"
  "certbot/renewal-hooks/post/start-nginx.sh:/etc/letsencrypt/renewal-hooks/post/start-nginx.sh"
)

cd "$REPO"
log "repo at $(git log -1 --format='%h %s')"

# 1. Static checks first - a broken config must never reach the server.
python3 scripts/validate.py

# 2. Files.
changed=()
backups=()
for pair in "${FILES[@]}"; do
  src="$REPO/${pair%%:*}"
  dst="${pair#*:}"
  if cmp -s "$src" "$dst"; then
    continue
  fi
  changed+=("${pair%%:*}")
  if [ "$DRY" = 1 ]; then
    log "would update $dst"
    diff -u "$dst" "$src" || true
    continue
  fi
  if [ -e "$dst" ]; then
    cp -p "$dst" "$dst.bak-$TS"
    backups+=("$dst")
  fi
  cp "$src" "$dst"
  log "updated $dst"
done
chmod +x /etc/letsencrypt/renewal-hooks/pre/stop-nginx.sh /etc/letsencrypt/renewal-hooks/post/start-nginx.sh

# 2b. Secrets. They never live in this repository: librechat/secrets-generation
#     is only a number. When it is higher than the generation recorded on the
#     server, new random values for the secrets LibreChat ships with public
#     example defaults are generated HERE, written into .env in place (it is a
#     single-file bind mount), and never printed. Everyone is logged out once.
#     CREDS_KEY/CREDS_IV encrypt user-provided keys; this chat stores none.
SECRETS=(JWT_SECRET JWT_REFRESH_SECRET CREDS_KEY CREDS_IV MEILI_MASTER_KEY)
SECRETS_DONE="$LC/.secrets-generation"
want=$(tr -dc 0-9 < "$REPO/librechat/secrets-generation" 2>/dev/null || true)
have=$(tr -dc 0-9 < "$SECRETS_DONE" 2>/dev/null || true)
want=${want:-0}; have=${have:-0}
rotated=0
if [ "$want" -gt "$have" ]; then
  if [ "$DRY" = 1 ]; then
    log "would rotate ${SECRETS[*]}: generation $have -> $want"
  else
    tmp=$(mktemp)
    JWT_SECRET=$(openssl rand -hex 32) JWT_REFRESH_SECRET=$(openssl rand -hex 32) \
    CREDS_KEY=$(openssl rand -hex 32) CREDS_IV=$(openssl rand -hex 16) \
    MEILI_MASTER_KEY=$(openssl rand -hex 32) \
      awk -F= 'BEGIN { split("JWT_SECRET JWT_REFRESH_SECRET CREDS_KEY CREDS_IV MEILI_MASTER_KEY", k, " "); for (i in k) new[k[i]] = ENVIRON[k[i]] }
               ($1 in new) { print $1 "=" new[$1]; seen[$1] = 1; next } { print }
               END { for (n in new) if (!(n in seen)) { print "missing " n > "/dev/stderr"; exit 3 } }' \
      "$LC/.env" > "$tmp" || { log "ERROR: .env lacks one of ${SECRETS[*]} - nothing rotated"; rm -f "$tmp"; exit 1; }
    cp -p "$LC/.env" "$LC/.env.bak-$TS"
    chmod 600 "$LC/.env.bak-$TS"
    backups+=("$LC/.env")
    cat "$tmp" > "$LC/.env"
    rm -f "$tmp"
    rotated=1
    log "rotated ${SECRETS[*]}: generation $have -> $want (values stay on the server)"
  fi
fi

has() { local x; for x in "${changed[@]:-}"; do [ "$x" = "$1" ] && return 0; done; return 1; }

# LibreChat reads .env through its bind mount; rag_api and meilisearch get the
# values as container environment at creation, so they must be recreated.
recreate_secret_readers() {
  (cd "$LC" && docker compose up -d --force-recreate --no-deps api rag_api meilisearch 2>&1 | grep -v 'variable is not set' || true)
}

rollback() {
  log "ROLLBACK: restoring ${#backups[@]} file(s)"
  local f
  for f in "${backups[@]:-}"; do
    [ -n "$f" ] && cat "$f.bak-$TS" > "$f"
  done
  if [ "$rotated" = 1 ]; then
    recreate_secret_readers
  fi
  # A restart keeps the container's image; only compose puts the old image back.
  if has librechat/docker-compose.override.yml || has librechat/deploy-compose.yml; then
    (cd "$LC" && docker compose up -d 2>&1 | grep -v 'variable is not set' || true)
  fi
  docker restart LibreChat >/dev/null || true
  docker restart LibreChat-NGINX >/dev/null || true
}

healthy() {
  local i code
  for i in $(seq 1 45); do
    code=$(curl -sk -o /dev/null -w '%{http_code}' --resolve chat.poly-mind.net:443:127.0.0.1 "$HEALTH_URL" || true)
    [ "$code" = 200 ] && return 0
    sleep 2
  done
  return 1
}

# 3. Presets live in MongoDB, not in a file. presets.json is the whole truth
#    for the owner's presets; apply_presets.js backs the collection up first.
presets_out=$(docker cp "$REPO/presets/presets.json" chat-mongodb:/tmp/presets.json \
  && docker cp "$REPO/scripts/apply_presets.js" chat-mongodb:/tmp/apply_presets.js \
  && docker exec -e DRY_RUN="$DRY" -e BACKUP_TAG="$TS" chat-mongodb mongosh --quiet LibreChat /tmp/apply_presets.js)
echo "$presets_out"

if [ "$DRY" = 1 ]; then
  log "dry run: ${#changed[@]} file(s) would change"
  exit 0
fi

# 4. Restarts, only for what changed.
if has nginx/nginx.conf; then
  if ! docker exec LibreChat-NGINX nginx -t >/dev/null 2>&1; then
    docker exec LibreChat-NGINX nginx -t || true
    rollback
    exit 1
  fi
  docker exec LibreChat-NGINX nginx -s reload >/dev/null 2>&1
  log "nginx reloaded"
fi
if has librechat/docker-compose.override.yml; then
  # A new image may migrate the database on its first start, and restoring the
  # compose file does not undo that - so a dump first, to restore by hand.
  mkdir -p /root/backup
  dump="/root/backup/librechat_before_deploy_$TS.archive.gz"
  docker exec chat-mongodb mongodump --quiet --archive --gzip --db LibreChat > "$dump"
  chmod 600 "$dump"
  log "mongo dump $dump ($(du -h "$dump" | cut -f1))"
  # Pull while the old container still serves, so the downtime is the restart only.
  (cd "$LC" && docker compose pull -q api 2>&1 | grep -v 'variable is not set' || true)
fi
if has librechat/docker-compose.override.yml || has librechat/deploy-compose.yml; then
  (cd "$LC" && docker compose up -d 2>&1 | grep -v 'variable is not set' || true)
  (cd "$LC" && docker compose -f deploy-compose.yml -f docker-compose.override.yml up -d --no-deps client 2>&1 | grep -v 'variable is not set' || true)
  log "compose re-applied"
elif has librechat/librechat.yaml; then
  docker restart LibreChat >/dev/null
  log "LibreChat restarted"
fi
if [ "$rotated" = 1 ]; then
  recreate_secret_readers
  log "LibreChat, rag_api and meilisearch recreated with the new secrets"
fi

# 5. Health, or roll everything back.
if ! healthy; then
  log "chat not healthy after the change"
  rollback
  healthy && log "rollback restored the chat" || log "chat STILL DOWN after rollback"
  exit 1
fi
if [ "$rotated" = 1 ]; then
  echo "$want" > "$SECRETS_DONE"
  log "secrets generation $want recorded"
fi
log "done: ${#changed[@]} file(s) changed, chat healthy"
