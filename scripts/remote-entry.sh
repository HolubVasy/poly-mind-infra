#!/usr/bin/env bash
# The only thing the deploy key may run on the server. Installed as
# /usr/local/sbin/poly-mind-apply and pinned in /root/.ssh/authorized_keys with
# command="/usr/local/sbin/poly-mind-apply",restrict - whatever command the
# client asks for is ignored, except the literal word "dry-run".
#
# It syncs /opt/poly-mind-infra to origin/main and runs scripts/apply.sh from
# there, so apply.sh itself is always the reviewed version on main.
set -euo pipefail
exec 9>/run/poly-mind-apply.lock
flock -n 9 || { echo "another apply is running"; exit 1; }

cd /opt/poly-mind-infra
git fetch -q origin main
git reset -q --hard origin/main

if [ "${SSH_ORIGINAL_COMMAND:-}" = "dry-run" ]; then
  export DRY_RUN=1
fi
exec bash scripts/apply.sh
