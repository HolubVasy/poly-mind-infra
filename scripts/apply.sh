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
  cat "$src" > "$dst"
  log "updated $dst"
done
chmod +x /etc/letsencrypt/renewal-hooks/pre/stop-nginx.sh /etc/letsencrypt/renewal-hooks/post/start-nginx.sh

has() { local x; for x in "${changed[@]:-}"; do [ "$x" = "$1" ] && return 0; done; return 1; }

rollback() {
  log "ROLLBACK: restoring ${#backups[@]} file(s)"
  local f
  for f in "${backups[@]:-}"; do
    [ -n "$f" ] && cat "$f.bak-$TS" > "$f"
  done
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
if has librechat/docker-compose.override.yml || has librechat/deploy-compose.yml; then
  (cd "$LC" && docker compose up -d 2>&1 | grep -v 'variable is not set' || true)
  (cd "$LC" && docker compose -f deploy-compose.yml -f docker-compose.override.yml up -d --no-deps client 2>&1 | grep -v 'variable is not set' || true)
  log "compose re-applied"
elif has librechat/librechat.yaml; then
  docker restart LibreChat >/dev/null
  log "LibreChat restarted"
fi

# 5. Health, or roll everything back.
if ! healthy; then
  log "chat not healthy after the change"
  rollback
  healthy && log "rollback restored the chat" || log "chat STILL DOWN after rollback"
  exit 1
fi
log "done: ${#changed[@]} file(s) changed, chat healthy"
