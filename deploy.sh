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
# of this GitHub repo. That turned out to include images/ specifically: a
# first dry run here found 300+ unrelated files already sitting in
# public_html/images/ (old aquarium and car-project photo galleries, going
# back over a decade) -- a generic folder name this build also happens to
# use. A per-directory `--delete`, even scoped to that one subtree, would
# have wiped all of it the moment this site's own images synced over it.
#
# So there is no --delete anywhere in this script. Every sync is purely
# additive: files get added or updated, nothing already on the server is
# ever removed, no matter what name it shares with something this build
# also owns. The cost is real -- a page or file permanently dropped from a
# future build leaves its old copy on the server forever, since cleaning
# it up safely would require knowing every remote name is safe to touch,
# which public_html/images/ just proved is not a safe assumption here.
# Removing something needs a manual pass on the server when that actually
# happens.
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
    rsync $RSYNC_OPTS -e "$SSH_CMD" \
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
