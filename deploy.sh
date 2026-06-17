#!/usr/bin/env bash
# deploy.sh — auto-deploy the Book Formatter worker.
#
# Pulls the latest code from origin/main and rebuilds the container ONLY when the
# remote has a new commit. Safe to run on a frequent cron (it no-ops when nothing
# changed). The .env (service key) is git-ignored, so it is never touched.
#
# Install (on the VPS, once):
#   chmod +x /opt/book-formatter-worker/deploy.sh
#   (crontab -l 2>/dev/null; echo '*/3 * * * * /opt/book-formatter-worker/deploy.sh >> /var/log/book-formatter-deploy.log 2>&1') | crontab -
set -euo pipefail
cd /opt/book-formatter-worker

git fetch --quiet origin main
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
  echo "$(date -u +%FT%TZ) [deploy] new commit $REMOTE — pulling + rebuilding"
  git pull --ff-only origin main
  docker compose up -d --build
  echo "$(date -u +%FT%TZ) [deploy] done"
fi
