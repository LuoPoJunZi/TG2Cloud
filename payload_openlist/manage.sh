#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

INSTALL_DIR="${INSTALL_DIR:-/opt/tg115-openlist}"
BACKUP_DIR="/opt/tg115-openlist-backups"
BOT_SERVICE="tg115-bot"
BOT_CONTAINER="tg115-openlist-bot"
OPENLIST_SERVICE="openlist"
OPENLIST_CONTAINER="tg115-openlist"

[[ "$INSTALL_DIR" =~ ^/opt/[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$ ]] || exit 2
[[ "/$INSTALL_DIR/" != *"/../"* && "/$INSTALL_DIR/" != *"/./"* ]] || exit 2
[[ "$(realpath -e -- "$INSTALL_DIR")" == "$INSTALL_DIR" ]] || exit 2
cd "$INSTALL_DIR"
# shellcheck disable=SC1091
source ./backup_retention.sh

check_config() {
  local fingerprint
  fingerprint="$(sha256sum app/*.py | LC_ALL=C sort -k2 | sha256sum | cut -d' ' -f1)"
  docker compose config --format json \
    | docker compose exec -T "$BOT_SERVICE" python -m app.deployment_check \
        --expected-code "$fingerprint"
}

validate_config() {
  docker compose config --quiet || return 1
  docker compose run --rm --no-deps --entrypoint python "$BOT_SERVICE" \
    -m app.deployment_check --validate-only
}

check_openlist() {
  [[ "$(docker inspect --format '{{.State.Running}}' "$OPENLIST_CONTAINER" 2>/dev/null || true)" == true ]] \
    || return 1
  curl -fsS --max-time 10 http://127.0.0.1:5244/ >/dev/null
}

wait_openlist() {
  for _ in $(seq 1 40); do
    if check_openlist; then
      return
    fi
    sleep 3
  done
  return 1
}

wait_healthy() {
  local health
  for _ in $(seq 1 40); do
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$BOT_CONTAINER" 2>/dev/null || true)"
    if [[ "$health" == healthy ]]; then
      check_config
      return
    fi
    [[ "$health" != unhealthy && "$health" != exited ]] || return 1
    sleep 3
  done
  return 1
}

redact_runtime_logs() {
  # OpenList may print the one-time initial administrator password on first boot.
  # Keep routine support output useful without echoing that credential.
  sed -E \
    -e '/[Pp]assword|密码/ s/(:|=)[^:=]*$/\1 [REDACTED]/' \
    -e 's/([A-Z0-9_]*(PASSWORD|TOKEN|API_HASH|SECRET)[A-Z0-9_]*=)[^[:space:]]+/\1[REDACTED]/g' \
    -e 's/[0-9]{6,12}:[A-Za-z0-9_-]{20,}/[REDACTED_BOT_TOKEN]/g' \
    -e 's#(https?://)[^[:space:]/:@]+:[^[:space:]/@]+@#\1[REDACTED]@#g'
}

create_backup() (
  local config_backup="" database_backup="" openlist_backup=""
  local db_temp_name="" services_stopped=false exit_code

  # Invoked indirectly by the signal/error trap below.
  # shellcheck disable=SC2329
  recover_backup_failure() {
    exit_code=$?
    [[ "$exit_code" -ne 0 ]] || exit_code=1
    trap - ERR INT TERM HUP
    if [[ -n "$db_temp_name" && "$db_temp_name" == .manual-backup-*.db ]]; then
      rm -f -- "$INSTALL_DIR/data/$db_temp_name" || true
    fi
    [[ -z "$config_backup" || ! -f "$config_backup" ]] \
      || rm -f -- "$config_backup"
    [[ -z "$database_backup" || ! -f "$database_backup" ]] \
      || rm -f -- "$database_backup"
    [[ -z "$openlist_backup" || ! -f "$openlist_backup" ]] \
      || rm -f -- "$openlist_backup"
    if [[ "$services_stopped" == true ]]; then
      docker compose up -d "$OPENLIST_SERVICE" "$BOT_SERVICE" >/dev/null 2>&1 \
        || true
    fi
    printf 'TG115_BACKUP=FAILED\n' >&2
    exit "$exit_code"
  }
  trap recover_backup_failure ERR INT TERM HUP

  install -d -m 700 "$BACKUP_DIR"
  config_backup="$(mktemp "$BACKUP_DIR/config-XXXXXXXX.tar.gz")"
  tar -czf "$config_backup" -C "$INSTALL_DIR" \
    --exclude='./data' --exclude='./downloads' --exclude='./logs' \
    --exclude='./openlist' .
  tar -tzf "$config_backup" >/dev/null
  chmod 600 "$config_backup"

  if [[ -f "$INSTALL_DIR/data/tg115.db" ]]; then
    database_backup="$(mktemp "$BACKUP_DIR/database-XXXXXXXX.db")"
    rm -f -- "$database_backup"
    db_temp_name=".manual-backup-$$.db"
    docker compose exec -T "$BOT_SERVICE" python -m app.backup_database \
      /data/tg115.db "/data/$db_temp_name"
    install -m 600 "$INSTALL_DIR/data/$db_temp_name" "$database_backup"
    rm -f -- "$INSTALL_DIR/data/$db_temp_name"
    db_temp_name=""
  fi

  services_stopped=true
  docker compose stop "$BOT_SERVICE" "$OPENLIST_SERVICE" >/dev/null
  if [[ -f "$INSTALL_DIR/openlist/data/data.db" ]]; then
    openlist_backup="$(mktemp "$BACKUP_DIR/openlist-state-XXXXXXXX.tar.gz")"
    tar -czf "$openlist_backup" -C "$INSTALL_DIR" \
      --exclude='./openlist/data/temp' --exclude='./openlist/data/log' \
      openlist/data
    tar -tzf "$openlist_backup" >/dev/null
    chmod 600 "$openlist_backup"
  fi
  docker compose up -d "$OPENLIST_SERVICE" "$BOT_SERVICE" >/dev/null
  wait_openlist
  wait_healthy
  services_stopped=false
  trap - ERR INT TERM HUP

  printf 'TG115_BACKUP=OK\n'
  printf 'TG115_BACKUP_CONFIG=%s\n' "$config_backup"
  [[ -z "$database_backup" ]] \
    || printf 'TG115_BACKUP_DATABASE=%s\n' "$database_backup"
  [[ -z "$openlist_backup" ]] \
    || printf 'TG115_BACKUP_OPENLIST=%s\n' "$openlist_backup"
)

apply_config() {
  local candidate="${2:-}" backup staged restarted=false
  [[ -f "$candidate" && "$candidate" == /* ]] \
    || { echo "请提供新配置文件的绝对路径" >&2; return 2; }
  install -d -m 700 "$BACKUP_DIR"
  backup="$(mktemp "$BACKUP_DIR/env-XXXXXXXX.env")"
  install -m 600 .env "$backup"
  restore_config() {
    install -m 600 "$backup" .env
    if [[ "$restarted" == true ]]; then
      if ! docker compose up -d --no-deps "$BOT_SERVICE" || ! wait_healthy; then
        echo '旧配置已恢复，但容器恢复未通过核验，请人工检查。' >&2
      fi
    fi
    [[ -z "${staged:-}" || ! -f "$staged" ]] || rm -f -- "$staged"
  }
  trap 'trap - ERR INT TERM HUP; restore_config; exit 1' ERR INT TERM HUP
  staged="$(mktemp "$INSTALL_DIR/.env-staged-XXXXXXXX")"
  install -m 600 "$candidate" "$staged"
  sed -i 's/\r$//' "$staged"
  mv -f -- "$staged" .env
  if validate_config; then
    restarted=true
    if docker compose up -d --no-deps "$BOT_SERVICE" && wait_healthy; then
      trap - ERR INT TERM HUP
      printf 'TG115_APPLY_CONFIG=OK\n配置备份：%s\n' "$backup"
      return
    fi
  fi
  restore_config
  trap - ERR INT TERM HUP
  printf 'TG115_APPLY_CONFIG=FAILED\n已恢复旧配置；备份：%s\n' "$backup" >&2
  return 1
}

case "${1:-status}" in
  status)
    docker compose ps
    if ! check_openlist; then
      printf 'TG115_OPENLIST=FAILED\n' >&2
      exit 1
    fi
    bot_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$BOT_CONTAINER" 2>/dev/null || true)"
    if [[ "$bot_health" != healthy ]]; then
      printf 'TG115_BOT_HEALTH=%s\nTG115_STATUS=FAILED\n' "${bot_health:-unknown}" >&2
      exit 1
    fi
    printf 'TG115_OPENLIST=OK\nTG115_BOT_HEALTH=healthy\nTG115_STATUS=OK\n'
    ;;
  logs)
    docker compose logs --since=30m --tail=200 -f \
      "$BOT_SERVICE" "$OPENLIST_SERVICE" | redact_runtime_logs
    ;;
  recent-logs)
    docker compose logs --since=30m --tail=200 \
      "$BOT_SERVICE" "$OPENLIST_SERVICE" | redact_runtime_logs
    printf 'TG115_LOGS=OK\n'
    ;;
  restart)
    docker compose restart "$OPENLIST_SERVICE" "$BOT_SERVICE"
    wait_openlist
    wait_healthy
    ;;
  restart-bot)
    docker compose restart "$BOT_SERVICE"
    wait_healthy
    printf 'TG115_BOT_RESTART=OK\n'
    ;;
  restart-openlist)
    docker compose restart "$OPENLIST_SERVICE"
    wait_openlist
    wait_healthy
    printf 'TG115_OPENLIST_RESTART=OK\n'
    ;;
  backup)
    create_backup
    ;;
  stop)
    docker compose stop "$BOT_SERVICE" "$OPENLIST_SERVICE"
    ;;
  start)
    docker compose up -d "$OPENLIST_SERVICE" "$BOT_SERVICE"
    wait_openlist
    wait_healthy
    ;;
  update)
    docker compose pull "$OPENLIST_SERVICE"
    docker compose build "$BOT_SERVICE"
    validate_config
    docker compose up -d "$OPENLIST_SERVICE" "$BOT_SERVICE"
    wait_openlist
    wait_healthy
    ;;
  apply-config)
    apply_config "$@"
    ;;
  backups)
    tg115_backup_inventory "$BACKUP_DIR"
    ;;
  prune-backups)
    tg115_prune_backups "$BACKUP_DIR" "${2:-5}"
    ;;
  check|doctor)
    check_openlist
    check_config
    docker compose exec -T "$BOT_SERVICE" python -m app.healthcheck
    ;;
  validate)
    validate_config
    ;;
  ready)
    wait_openlist
    wait_healthy
    ;;
  verify)
    docker compose ps
    if ! check_openlist; then
      printf 'TG115_OPENLIST=FAILED\n' >&2
      exit 1
    fi
    printf 'TG115_OPENLIST=OK\n'
    bot_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$BOT_CONTAINER" 2>/dev/null || true)"
    printf 'BOT_HEALTH=%s\n' "${bot_health:-unknown}"
    [[ "$bot_health" == healthy ]] || exit 1
    docker compose exec -T "$BOT_SERVICE" python -m app.verify_destination
    ;;
  *)
    echo "用法：$0 {status|logs|recent-logs|restart|restart-bot|restart-openlist|backup|stop|start|update|verify|check|doctor|validate|ready|backups|prune-backups [1-50]|apply-config /absolute/config.env}" >&2
    exit 2
    ;;
esac
