#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

INSTALL_DIR="${INSTALL_DIR:-/opt/tg2cloud-openlist}"
OPENLIST_CONTAINER="tg2cloud-openlist"
[[ "$INSTALL_DIR" =~ ^/opt/[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$ ]] || exit 2
[[ "/$INSTALL_DIR/" != *"/../"* && "/$INSTALL_DIR/" != *"/./"* ]] || exit 2
[[ "$(realpath -e -- "$INSTALL_DIR")" == "$INSTALL_DIR" ]] || exit 2
cd "$INSTALL_DIR"

case "${1:-status}" in
  status)
    docker exec "$OPENLIST_CONTAINER" ./openlist admin \
      | sed -nE 's/^.*Admin user.s username:[[:space:]]*/TG2CLOUD_OPENLIST_ADMIN_USERNAME=/p'
    ;;
  reset-random)
    [[ "${2:-}" == "I_UNDERSTAND_THIS_RESETS_THE_ADMIN_PASSWORD" ]] || {
      printf '需要明确确认后才能重置 OpenList 管理员密码\n' >&2
      exit 2
    }
    output="$(docker exec "$OPENLIST_CONTAINER" ./openlist admin random 2>&1)"
    password="$(
      printf '%s\n' "$output" \
        | sed -E $'s/\\x1B\\[[0-9;]*[mK]//g' \
        | sed -nE 's/^.*password:[[:space:]]*([^[:space:]]+)[[:space:]]*$/\1/p' \
        | tail -n 1
    )"
    [[ -n "$password" ]] || {
      printf 'TG2CLOUD_OPENLIST_ADMIN_RESET=FAILED\n' >&2
      exit 1
    }
    printf 'TG2CLOUD_OPENLIST_ADMIN_RESET=OK\n'
    printf 'TG2CLOUD_OPENLIST_ADMIN_USERNAME=admin\n'
    printf 'TG2CLOUD_OPENLIST_ADMIN_PASSWORD=%s\n' "$password"
    ;;
  *)
    echo "用法：$0 {status|reset-random I_UNDERSTAND_THIS_RESETS_THE_ADMIN_PASSWORD}" >&2
    exit 2
    ;;
esac
