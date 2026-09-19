#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SOURCE_DIR="${1:-}"
CONFIG_FILE="${2:-}"
INSTALL_DIR="${INSTALL_DIR:-/opt/tg115-openlist}"
BACKUP_DIR="/opt/tg115-openlist-backups"
BOT_SERVICE="tg115-bot"
BOT_CONTAINER="tg115-openlist-bot"
OPENLIST_SERVICE="openlist"
OPENLIST_CONTAINER="tg115-openlist"
BACKUP=""
DATABASE_BACKUP=""
OPENLIST_BACKUP=""
RELEASE_STAGE=""
CANDIDATE_TAG=""
OLD_BOT_IMAGE_ID=""
OLD_BOT_IMAGE_TAG=""
OLD_OPENLIST_IMAGE_ID=""
OLD_OPENLIST_IMAGE_TAG=""
DB_TEMP_NAME=""
ROLLBACK_ARMED=false
OPENLIST_WAS_NEW=false

PROGRAM_PATHS=(
  app .dockerignore backup_retention.sh Dockerfile docker-compose.yml manage.sh
  openlist_admin.sh preserve_webdav_config.sh remote_install.sh requirements.txt
)

log() {
  printf '[TG115-OPENLIST] %s\n' "$*"
}

remove_program_files() {
  local relative
  for relative in "${PROGRAM_PATHS[@]}"; do
    rm -rf -- "${INSTALL_DIR:?}/$relative" || return 1
  done
}

wait_container_healthy() {
  local health=""
  for _ in $(seq 1 40); do
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$BOT_CONTAINER" 2>/dev/null || true)"
    [[ "$health" == healthy ]] && return 0
    [[ "$health" != unhealthy && "$health" != exited ]] || break
    sleep 3
  done
  return 1
}

wait_openlist_http() {
  for _ in $(seq 1 40); do
    curl -fsS --max-time 5 http://127.0.0.1:5244/ >/dev/null 2>&1 && return 0
    [[ "$(docker inspect --format '{{.State.Running}}' "$OPENLIST_CONTAINER" 2>/dev/null || true)" == true ]] \
      || break
    sleep 3
  done
  return 1
}

rollback_install() {
  ROLLBACK_ARMED=false
  [[ -n "$BACKUP" && -f "$BACKUP" ]] || return 1
  log "新版本未通过验收，开始恢复升级前的程序、配置和 Bot 数据库"
  if [[ -f "$INSTALL_DIR/docker-compose.yml" ]]; then
    (cd "$INSTALL_DIR" && docker compose rm -sf "$BOT_SERVICE") || true
  fi
  remove_program_files || return 1
  tar -xzf "$BACKUP" -C "$INSTALL_DIR" || return 1
  if [[ -n "$DATABASE_BACKUP" && -f "$DATABASE_BACKUP" ]]; then
    rm -f -- "$INSTALL_DIR/data/tg115.db-wal" "$INSTALL_DIR/data/tg115.db-shm" || return 1
    install -m 600 "$DATABASE_BACKUP" "$INSTALL_DIR/data/tg115.db" || return 1
    chown 10001:10001 "$INSTALL_DIR/data/tg115.db" || return 1
  fi
  if [[ -n "$OLD_BOT_IMAGE_ID" && -n "$OLD_BOT_IMAGE_TAG" ]]; then
    docker tag "$OLD_BOT_IMAGE_ID" "$OLD_BOT_IMAGE_TAG" || return 1
  fi
  if [[ -n "$OLD_OPENLIST_IMAGE_ID" && -n "$OLD_OPENLIST_IMAGE_TAG" ]]; then
    docker tag "$OLD_OPENLIST_IMAGE_ID" "$OLD_OPENLIST_IMAGE_TAG" || return 1
  fi
  cd "$INSTALL_DIR" || return 1
  docker compose up -d "$OPENLIST_SERVICE" || return 1
  wait_openlist_http || return 1
  docker compose up -d --no-deps --force-recreate "$BOT_SERVICE" || return 1
  wait_container_healthy
}

cleanup_release_stage() {
  if [[ -n "$RELEASE_STAGE" && "$RELEASE_STAGE" == /opt/tg115-openlist-release-* && -d "$RELEASE_STAGE" ]]; then
    rm -rf -- "$RELEASE_STAGE"
  fi
  if [[ -n "$CANDIDATE_TAG" ]]; then
    docker image rm "$CANDIDATE_TAG" >/dev/null 2>&1 || true
  fi
  if [[ "$DB_TEMP_NAME" == .upgrade-backup-*.db ]]; then
    rm -f -- "$INSTALL_DIR/data/$DB_TEMP_NAME"
  fi
}

fail() {
  trap - ERR INT TERM HUP
  local message="$*"
  if [[ "$ROLLBACK_ARMED" == true ]]; then
    if rollback_install; then
      message+=" 已自动恢复升级前版本。"
    else
      message+=" 自动恢复未完成，请保留备份并人工处理。"
    fi
  fi
  printf '[TG115-OPENLIST][ERROR] %s\n' "$message" >&2
  [[ -z "$OPENLIST_BACKUP" ]] \
    || printf '[TG115-OPENLIST] OpenList 状态备份：%s\n' "$OPENLIST_BACKUP" >&2
  printf 'TG115_RESULT=FAILED\n' >&2
  exit 1
}

trap 'fail "安装在第 ${LINENO} 行失败。请保留完整日志。"' ERR
trap 'fail "安装被中断。请保留完整日志。"' INT TERM HUP
trap cleanup_release_stage EXIT

[[ "$(id -u)" -eq 0 ]] || fail "remote_install.sh 必须以 root 或 sudo 运行"
[[ -d "$SOURCE_DIR" ]] || fail "找不到部署源目录"
[[ -f "$CONFIG_FILE" ]] || fail "找不到配置文件"
[[ "$INSTALL_DIR" =~ ^/opt/[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$ ]] \
  || fail "安装目录必须是 /opt/ 下的安全绝对路径"
[[ "/$INSTALL_DIR/" != *"/../"* && "/$INSTALL_DIR/" != *"/./"* ]] \
  || fail "安装目录不能包含 . 或 .. 路径段"
[[ "$(realpath -m -- "$INSTALL_DIR")" == "$INSTALL_DIR" ]] \
  || fail "安装目录不能经过符号链接"
SOURCE_DIR="$(realpath -e -- "$SOURCE_DIR")"
CONFIG_FILE="$(realpath -e -- "$CONFIG_FILE")"
PRESERVE_CONFIG_HELPER="$SOURCE_DIR/preserve_webdav_config.sh"
[[ -f "$PRESERVE_CONFIG_HELPER" ]] || fail "部署包缺少 WebDAV 配置保留脚本"
# shellcheck disable=SC1090
source "$PRESERVE_CONFIG_HELPER"
[[ "$SOURCE_DIR/" != "$INSTALL_DIR/"* && "$INSTALL_DIR/" != "$SOURCE_DIR/"* ]] \
  || fail "部署源目录和安装目录不能重叠"
[[ "$CONFIG_FILE" != "$INSTALL_DIR/"* ]] || fail "请将输入配置放在安装目录之外"
export INSTALL_DIR
sed -i 's/\r$//' "$CONFIG_FILE"
if tg115_preserve_existing_webdav_config "$CONFIG_FILE" "$INSTALL_DIR/.env"; then
  grep -Fxq 'TG115_PRESERVE_WEBDAV=true' "$CONFIG_FILE" \
    && log "已在 VPS 内复用现有 WebDAV 配置；不会输出或传回凭据"
else
  fail "无法安全保留 VPS 上的现有 WebDAV 配置"
fi

if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  source /etc/os-release
else
  fail "无法识别 Linux 系统"
fi
case "${ID:-}" in
  ubuntu|debian) ;;
  *) fail "目前只自动支持 Ubuntu 或 Debian，当前系统：${ID:-unknown}" ;;
esac
[[ -n "${VERSION_CODENAME:-}" ]] || fail "系统缺少 VERSION_CODENAME，无法配置软件源"

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64|aarch64|arm64) ;;
  *) fail "当前 CPU 架构暂不支持：$ARCH" ;;
esac

TOTAL_MEM_MB="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)"
CPU_CORES="$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc)"
INSTALL_PROBE_PATH="$INSTALL_DIR"
while [[ ! -e "$INSTALL_PROBE_PATH" ]]; do
  PARENT_PATH="$(dirname -- "$INSTALL_PROBE_PATH")"
  [[ "$PARENT_PATH" != "$INSTALL_PROBE_PATH" ]] || break
  INSTALL_PROBE_PATH="$PARENT_PATH"
done
[[ -e "$INSTALL_PROBE_PATH" ]] || INSTALL_PROBE_PATH=/
INSTALL_TOTAL_KB="$(df -Pk -- "$INSTALL_PROBE_PATH" | awk 'NR==2 {print $2}')"
INSTALL_FREE_KB="$(df -Pk -- "$INSTALL_PROBE_PATH" | awk 'NR==2 {print $4}')"
log "检测到 ${CPU_CORES} 核 CPU、约 ${TOTAL_MEM_MB}MB 内存、安装文件系统可用约 $((INSTALL_FREE_KB / 1024))MB"
[[ "$TOTAL_MEM_MB" -ge 900 ]] || fail "内存不足 1GB，无法安全安装 OpenList 与 Bot"
[[ "$INSTALL_TOTAL_KB" -ge 20000000 ]] || log "警告：安装文件系统总容量低于推荐的 20GB"
[[ "$INSTALL_FREE_KB" -ge 8000000 ]] || fail "安装文件系统可用空间不足 8GB，无法安全安装"

export DEBIAN_FRONTEND=noninteractive
log "安装基础软件"
apt-get -o DPkg::Lock::Timeout=120 update -y
apt-get -o DPkg::Lock::Timeout=120 install -y --no-install-recommends \
  ca-certificates curl gnupg tar gzip openssh-client

configure_docker_repository() {
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/${ID}/gpg" \
    -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  printf '%s\n' \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
}

if ! command -v docker >/dev/null 2>&1; then
  log "通过 Docker 官方 APT 仓库安装 Docker"
  configure_docker_repository
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
if ! docker compose version >/dev/null 2>&1; then
  configure_docker_repository
  apt-get install -y docker-compose-plugin
fi
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 不可用"

DOCKER_ROOT_DIR="$(docker info --format '{{.DockerRootDir}}')" \
  || fail "无法读取 Docker 数据目录"
[[ "$DOCKER_ROOT_DIR" == /* && "$DOCKER_ROOT_DIR" != *$'\n'* && "$DOCKER_ROOT_DIR" != *$'\r'* ]] \
  || fail "Docker 数据目录不是安全的绝对路径"
DOCKER_PROBE_PATH="$DOCKER_ROOT_DIR"
while [[ ! -e "$DOCKER_PROBE_PATH" ]]; do
  PARENT_PATH="$(dirname -- "$DOCKER_PROBE_PATH")"
  [[ "$PARENT_PATH" != "$DOCKER_PROBE_PATH" ]] || break
  DOCKER_PROBE_PATH="$PARENT_PATH"
done
[[ -e "$DOCKER_PROBE_PATH" ]] || DOCKER_PROBE_PATH=/
if [[ "$(stat -c %d -- "$INSTALL_PROBE_PATH")" != "$(stat -c %d -- "$DOCKER_PROBE_PATH")" ]]; then
  DOCKER_FREE_KB="$(df -Pk -- "$DOCKER_PROBE_PATH" | awk 'NR==2 {print $4}')"
  DOCKER_MIN_FREE_KB=4000000
  [[ -f "$INSTALL_DIR/docker-compose.yml" ]] && DOCKER_MIN_FREE_KB=2000000
  log "Docker 数据目录位于另一文件系统，可用约 $((DOCKER_FREE_KB / 1024))MB"
  [[ "$DOCKER_FREE_KB" -ge "$DOCKER_MIN_FREE_KB" ]] \
    || fail "Docker 数据文件系统空间不足，无法安全构建和启动容器"
fi

log "准备隔离的持久化目录"
mkdir -p \
  "$INSTALL_DIR" "$INSTALL_DIR/data" "$INSTALL_DIR/downloads" \
  "$INSTALL_DIR/logs" "$INSTALL_DIR/config/rclone" "$INSTALL_DIR/openlist/data"
install -d -m 700 "$BACKUP_DIR"
[[ -f "$INSTALL_DIR/openlist/data/data.db" ]] || OPENLIST_WAS_NEW=true

RELEASE_STAGE="$(mktemp -d /opt/tg115-openlist-release-XXXXXXXX)"
CANDIDATE_TAG="tg115-openlist-candidate:$(date +%s)-$$"
log "在隔离目录预检新程序和配置"
cp -a "$SOURCE_DIR/." "$RELEASE_STAGE/"
install -m 600 "$CONFIG_FILE" "$RELEASE_STAGE/.env"
(cd "$RELEASE_STAGE" && docker compose config --quiet)
docker build --tag "$CANDIDATE_TAG" "$RELEASE_STAGE"
docker run --rm --read-only --tmpfs /tmp --entrypoint python \
  --env-file "$RELEASE_STAGE/.env" "$CANDIDATE_TAG" \
  -m app.deployment_check --validate-only
(cd "$RELEASE_STAGE" && docker compose pull "$OPENLIST_SERVICE")

if [[ -f "$INSTALL_DIR/docker-compose.yml" ]]; then
  BACKUP="$(mktemp "$BACKUP_DIR/config-XXXXXXXX.tar.gz")"
  log "备份现有程序配置"
  tar -czf "$BACKUP" -C "$INSTALL_DIR" \
    --exclude='./data' --exclude='./downloads' --exclude='./logs' \
    --exclude='./config' --exclude='./openlist' . \
    || fail "配置备份失败，尚未替换程序文件"
  tar -tzf "$BACKUP" >/dev/null || fail "配置备份无法读取，停止升级"
  OLD_BOT_IMAGE_ID="$(docker inspect --format '{{.Image}}' "$BOT_CONTAINER" 2>/dev/null || true)"
  OLD_BOT_IMAGE_TAG="$(docker inspect --format '{{.Config.Image}}' "$BOT_CONTAINER" 2>/dev/null || true)"
  OLD_OPENLIST_IMAGE_ID="$(docker inspect --format '{{.Image}}' "$OPENLIST_CONTAINER" 2>/dev/null || true)"
  OLD_OPENLIST_IMAGE_TAG="$(docker inspect --format '{{.Config.Image}}' "$OPENLIST_CONTAINER" 2>/dev/null || true)"
  [[ "$OLD_BOT_IMAGE_TAG" != "<no value>" ]] || OLD_BOT_IMAGE_TAG=""
  [[ "$OLD_OPENLIST_IMAGE_TAG" != "<no value>" ]] || OLD_OPENLIST_IMAGE_TAG=""
  if [[ -n "$OLD_BOT_IMAGE_ID" ]]; then
    ROLLBACK_ARMED=true
    docker stop --time 30 "$BOT_CONTAINER" >/dev/null
  fi
  if [[ -f "$INSTALL_DIR/data/tg115.db" ]]; then
    DATABASE_BACKUP="$(mktemp "$BACKUP_DIR/database-XXXXXXXX.db")"
    rm -f -- "$DATABASE_BACKUP"
    DB_TEMP_NAME=".upgrade-backup-$$.db"
    docker run --rm --read-only --tmpfs /tmp --user 10001:10001 \
      --volume "$INSTALL_DIR/data:/data" --entrypoint python "$CANDIDATE_TAG" \
      -m app.backup_database /data/tg115.db "/data/$DB_TEMP_NAME"
    install -m 600 "$INSTALL_DIR/data/$DB_TEMP_NAME" "$DATABASE_BACKUP"
    rm -f -- "$INSTALL_DIR/data/$DB_TEMP_NAME"
  fi
  if [[ -f "$INSTALL_DIR/openlist/data/data.db" ]]; then
    OPENLIST_BACKUP="$(mktemp "$BACKUP_DIR/openlist-state-XXXXXXXX.tar.gz")"
    tar -czf "$OPENLIST_BACKUP" -C "$INSTALL_DIR" \
      --exclude='./openlist/data/temp' --exclude='./openlist/data/log' openlist/data \
      || fail "OpenList 状态备份失败，停止升级"
    tar -tzf "$OPENLIST_BACKUP" >/dev/null || fail "OpenList 状态备份无法读取"
  fi
  ROLLBACK_ARMED=true
fi

log "提交已预检的程序和配置"
remove_program_files
cp -a "$RELEASE_STAGE/." "$INSTALL_DIR/"
chmod 700 "$INSTALL_DIR" "$INSTALL_DIR/data" "$INSTALL_DIR/downloads" \
  "$INSTALL_DIR/logs" "$INSTALL_DIR/config" "$INSTALL_DIR/openlist" \
  "$INSTALL_DIR/openlist/data" "$BACKUP_DIR"
chown -R 10001:10001 "$INSTALL_DIR/data" "$INSTALL_DIR/downloads" \
  "$INSTALL_DIR/logs" "$INSTALL_DIR/config"
chown -R 1001:1001 "$INSTALL_DIR/openlist/data"
chmod 600 "$INSTALL_DIR/.env"
chmod +x "$INSTALL_DIR/remote_install.sh" "$INSTALL_DIR/manage.sh" \
  "$INSTALL_DIR/openlist_admin.sh" "$INSTALL_DIR/preserve_webdav_config.sh"

cd "$INSTALL_DIR"
docker compose config --quiet
log "启动仅监听 VPS 回环地址的 OpenList"
docker compose up -d "$OPENLIST_SERVICE"
if ! wait_openlist_http; then
  docker compose logs --tail=120 "$OPENLIST_SERVICE" \
    | sed -E \
        -e '/[Pp]assword|密码/ s/(:|=)[^:=]*$/\1 [REDACTED]/' \
        -e 's/(OPENLIST_ADMIN_PASSWORD=)[^[:space:]]+/\1[REDACTED]/g' \
    || true
  fail "OpenList 没有在 VPS 本机 127.0.0.1:5244 正常响应"
fi

log "构建并启动 Telegram → 115 Bot"
docker compose build "$BOT_SERVICE"
bash "$INSTALL_DIR/manage.sh" validate
docker compose up -d --no-deps "$BOT_SERVICE"
if ! wait_container_healthy; then
  docker compose ps || true
  docker compose logs --tail=120 "$BOT_SERVICE" || true
  fail "Bot 未通过基础健康检查；OpenList 基础服务不会因此被误报为 WebDAV 已配置"
fi
bash "$INSTALL_DIR/manage.sh" ready

ROLLBACK_ARMED=false
# shellcheck disable=SC1091
source "$INSTALL_DIR/backup_retention.sh"
if BACKUP_INVENTORY="$(tg115_backup_inventory "$BACKUP_DIR")"; then
  BACKUP_COUNT="$(awk -F= '$1=="TOTAL_COUNT" {print $2}' <<< "$BACKUP_INVENTORY")"
  BACKUP_BYTES="$(awk -F= '$1=="TOTAL_BYTES" {print $2}' <<< "$BACKUP_INVENTORY")"
  log "当前保留 ${BACKUP_COUNT:-0} 份程序／数据库／配置备份，占用约 $(( ${BACKUP_BYTES:-0} / 1024 / 1024 ))MB"
fi
log "OpenList 与 Bot 基础部署完成；WebDAV 最终验收需在用户完成存储配置后单独执行"
docker compose ps
printf 'TG115_INSTALL_DIR=%s\n' "$INSTALL_DIR"
printf 'TG115_BOT_HEALTH=healthy\n'
if [[ "$OPENLIST_WAS_NEW" == true ]]; then
  printf 'TG115_OPENLIST_INITIALIZED=NEW\n'
else
  printf 'TG115_OPENLIST_INITIALIZED=EXISTING\n'
fi
printf 'TG115_OPENLIST_MANAGEMENT=127.0.0.1:5244\n'
printf 'TG115_DESTINATION=PENDING_USER_CONFIGURATION\n'
printf 'TG115_RESULT=SUCCESS\n'
