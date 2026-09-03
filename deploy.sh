#!/bin/sh
#
# Deploy dist/ to designoutlaw.com's own web root over SSH.
#
#   ./deploy.sh          rebuild, then show exactly what would change
#   ./deploy.sh --live   rebuild, then actually deploy
#
# Dry run is the default on purpose.
#
# Credentials never live in this repo. Host details go in .deploy.env, which is
# gitignored; authentication is by SSH key, so there is no password anywhere.
set -e
cd "$(dirname "$0")"

if [ ! -f .deploy.env ]; then
  echo "Missing .deploy.env — copy .deploy.env.example and fill it in." >&2
  exit 1
fi

# shellcheck disable=SC1091
. ./.deploy.env

: "${REMOTE_USER:?set REMOTE_USER in .deploy.env}"
: "${REMOTE_HOST:?set REMOTE_HOST in .deploy.env}"
: "${REMOTE_PATH:?set REMOTE_PATH in .deploy.env}"
SSH_PORT="${SSH_PORT:-22}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/designoutlaw_deploy}"

if [ ! -f "$SSH_KEY" ]; then
  echo "No private key at $SSH_KEY." >&2
  echo "Generate one:  ssh-keygen -t ed25519 -f $SSH_KEY -N ''" >&2
  echo "Then import the .pub half in cPanel and authorize it." >&2
  exit 1
fi

LIVE=0
[ "$1" = "--live" ] && LIVE=1

echo "==> building"
python3 build.py

# Guard against deploying an empty or half-built directory over a live site.
PAGES=$(find dist -name '*.html' | wc -l | tr -d ' ')
if [ "$PAGES" -lt 6 ]; then
  echo "Only $PAGES HTML files in dist/ — expected 7. Refusing to deploy." >&2
  exit 1
fi
echo "    $PAGES pages, $(du -sh dist | cut -f1) total"

# ---------------------------------------------------------------------------
# Unlike firefighterpfister.com, REMOTE_PATH here is designoutlaw.com's own
# document root -- shared with a bunch of other things that were never part
# of this GitHub repo (file drops, one-off tools, whatever else has
# accumulated at designoutlaw.com/<path> over the years). A blanket
# `rsync --delete` against that root would erase all of it the first time
# this site's own file list changed shape.
#
# So this loops dist/'s own top-level entries one at a time and syncs each
# into the matching remote path, with --delete scoped to *that* subtree only
# (trailing slashes make rsync sync contents-into-contents, not the folder
# itself). rsync never looks at, and therefore can never touch, anything at
# REMOTE_PATH that isn't one of these names. /transfer, or anything else
# living there, is simply outside every command this script runs.
#
# The cost: if a future build permanently drops a page or folder, its old
# copy on the server is never cleaned up by this script -- deleting it
# structurally requires knowing every remote name is safe to touch, which is
# exactly what this script is built to avoid assuming. Removing a page needs
# one manual cleanup pass on the server when that actually happens.
# ---------------------------------------------------------------------------
RSYNC_OPTS="-az --stats --exclude .DS_Store"
if ! rsync --version 2>/dev/null | grep -qi "openrsync"; then
  RSYNC_OPTS="$RSYNC_OPTS --human-readable"
fi
SSH_CMD="ssh -p $SSH_PORT -i $SSH_KEY -o IdentitiesOnly=yes"

if [ "$LIVE" -eq 1 ]; then
  echo "\n==> deploying to $REMOTE_HOST:$REMOTE_PATH"
else
  echo "\n==> DRY RUN — nothing will be uploaded. Re-run with --live to deploy."
  RSYNC_OPTS="$RSYNC_OPTS -n --itemize-changes"
fi

# shellcheck disable=SC2086
for entry in dist/*; do
  name=$(basename "$entry")
  if [ -d "$entry" ]; then
    rsync $RSYNC_OPTS --delete -e "$SSH_CMD" \
      "$entry/" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/$name/"
  else
    rsync $RSYNC_OPTS -e "$SSH_CMD" \
      "$entry" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/$name"
  fi
done

if [ "$LIVE" -eq 1 ]; then
  echo "\n==> done — https://www.designoutlaw.com"
else
  echo "\n==> dry run complete. ./deploy.sh --live to deploy for real."
fi
