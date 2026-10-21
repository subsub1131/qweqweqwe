#!/usr/bin/env bash
set -euo pipefail

for name in SSH_HOST SSH_PORT SSH_USERNAME SSHPASS SSH_KNOWN_HOSTS DEPLOY_PATH DEPLOY_COMMAND DEPLOY_SHA DEPLOY_REPOSITORY; do
  if [[ -z "${!name:-}" ]]; then
    echo "::error::Missing deployment setting: $name"
    exit 1
  fi
done
[[ "$SSH_HOST" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*$ ]] || { echo 'Invalid SSH host'; exit 1; }
[[ "$SSH_USERNAME" =~ ^[a-zA-Z0-9_][a-zA-Z0-9_.-]*$ ]] || { echo 'Invalid SSH username'; exit 1; }
[[ "$SSH_PORT" =~ ^[0-9]{1,5}$ ]] && (( 10#$SSH_PORT > 0 && 10#$SSH_PORT <= 65535 )) || { echo 'Invalid SSH port'; exit 1; }
[[ "$DEPLOY_PATH" == /* && "$DEPLOY_PATH" != / ]] || { echo 'DEPLOY_PATH must be an absolute project directory'; exit 1; }
[[ "$DEPLOY_SHA" =~ ^[a-f0-9]{40}$ ]] || { echo 'Invalid deployment commit'; exit 1; }

temporary_dir=$(mktemp -d)
trap 'rm -rf -- "$temporary_dir"' EXIT
printf '%s\n' "$SSH_KNOWN_HOSTS" > "$temporary_dir/known_hosts"
chmod 600 "$temporary_dir/known_hosts"

# Pass values through stdin as Bash-escaped assignments, never inline YAML code
# or SSH command arguments. SSHPASS is only consumed locally by sshpass.
{
  for name in DEPLOY_PATH DEPLOY_COMMAND DEPLOY_SHA DEPLOY_REPOSITORY; do
    printf '%s=%q\n' "$name" "${!name}"
  done
  cat .github/scripts/deploy-remote.sh
} | sshpass -e ssh -T \
  -p "$SSH_PORT" \
  -o StrictHostKeyChecking=yes \
  -o "UserKnownHostsFile=$temporary_dir/known_hosts" \
  -o PreferredAuthentications=password,keyboard-interactive \
  -o PubkeyAuthentication=no \
  -o ConnectTimeout=20 \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=4 \
  "$SSH_USERNAME@$SSH_HOST" 'bash -se'
