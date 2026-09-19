#!/usr/bin/env bash

tg115_read_env_value() {
  local file="$1" key="$2" line
  line="$(grep -m1 "^${key}=" "$file" || true)"
  [[ -n "$line" ]] || return 1
  printf '%s' "${line#*=}"
}

tg115_replace_env_value() {
  local file="$1" key="$2" value="$3" staged
  staged="$(mktemp "${file}.merge-XXXXXXXX")" || return 1
  if ! awk -v prefix="${key}=" -v replacement="${key}=${value}" \
    'index($0, prefix) == 1 {$0 = replacement} {print}' \
    "$file" > "$staged"; then
    rm -f -- "$staged"
    return 1
  fi
  chmod 600 "$staged" && mv -f -- "$staged" "$file"
}

tg115_preserve_existing_webdav_config() {
  local candidate="$1" existing="$2" value primary legacy admin_password
  grep -Eq '^(TG2CLOUD|TG115)_PRESERVE_WEBDAV=true$' "$candidate" || return 0
  [[ -f "$existing" && ! -L "$existing" ]] || {
    printf 'VPS 上不存在可复用的 .env\n' >&2
    return 1
  }
  while read -r primary legacy; do
    if value="$(tg115_read_env_value "$existing" "$primary")"; then
      :
    elif value="$(tg115_read_env_value "$existing" "$legacy")"; then
      :
    else
      printf 'VPS 现有配置缺少 %s\n' "$primary" >&2
      return 1
    fi
    if [[ "$primary" != WEBDAV_TARGET_PATH_B64 && -z "$value" ]]; then
      printf 'VPS 现有配置中的 %s 为空\n' "$primary" >&2
      return 1
    fi
    tg115_replace_env_value "$candidate" "$primary" "$value" || return 1
    tg115_replace_env_value "$candidate" "$legacy" "$value" || return 1
  done <<'EOF'
WEBDAV_URL_B64 CD2_WEBDAV_URL_B64
WEBDAV_USERNAME_B64 CD2_WEBDAV_USERNAME_B64
WEBDAV_PASSWORD_B64 CD2_WEBDAV_PASSWORD_B64
WEBDAV_TARGET_PATH_B64 CD2_TARGET_PATH_B64
EOF
  if admin_password="$(
    tg115_read_env_value "$existing" OPENLIST_ADMIN_PASSWORD
  )"; then
    tg115_replace_env_value \
      "$candidate" OPENLIST_ADMIN_PASSWORD "$admin_password" || return 1
  fi
  printf 'TG2CLOUD_WEBDAV_CONFIG=PRESERVED\n'
}
