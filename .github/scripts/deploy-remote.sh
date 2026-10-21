#!/usr/bin/env bash
set -euo pipefail

command -v git >/dev/null
command -v flock >/dev/null
cd -- "$DEPLOY_PATH"
project_root=$(git rev-parse --show-toplevel)
[[ "$(pwd -P)" == "$(cd -- "$project_root" && pwd -P)" ]] || {
  echo 'DEPLOY_PATH must be the repository root'; exit 1;
}

# Also protect deployments started outside GitHub Actions on the same checkout.
exec 9>"$(git rev-parse --git-path actions-deploy.lock)"
flock -w 600 9

origin=$(git remote get-url origin)
case "$origin" in
  "https://github.com/$DEPLOY_REPOSITORY"|"https://github.com/$DEPLOY_REPOSITORY.git"|\
  "git@github.com:$DEPLOY_REPOSITORY"|"git@github.com:$DEPLOY_REPOSITORY.git"|\
  "ssh://git@github.com/$DEPLOY_REPOSITORY"|"ssh://git@github.com/$DEPLOY_REPOSITORY.git") ;;
  *) echo 'Server origin does not match this GitHub repository'; exit 1 ;;
esac

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo 'Tracked files on server have local changes; deployment stopped'; exit 1
fi

# The server needs its own read access to origin; Actions credentials stay local.
export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND='ssh -o BatchMode=yes -o StrictHostKeyChecking=yes'
git fetch --quiet --no-tags origin refs/heads/main
latest_sha=$(git rev-parse FETCH_HEAD)
if [[ "$latest_sha" != "$DEPLOY_SHA" ]]; then
  echo 'A newer main commit exists. Deploying the latest main instead.'
fi
DEPLOY_SHA=$latest_sha

# No reset --hard or clean: preserve .env, database files and server-only files.
# Refuse overwriting untracked files, including ignored .env/database files.
git -c advice.detachedHead=false checkout --quiet --no-overwrite-ignore --detach "$DEPLOY_SHA"
export DEPLOY_SHA DEPLOY_PATH DEPLOY_REPOSITORY
# Prevent configured commands from consuming the rest of the SSH script input.
bash -e -o pipefail -c "$DEPLOY_COMMAND" </dev/null
printf 'Deployment command completed for commit %s\n' "$DEPLOY_SHA"
