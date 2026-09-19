#!/usr/bin/env bash
# Test-only fake Docker and /opt boundary. All files stay in TG115_TEST_DIR.
set -Eeuo pipefail

realpath() { printf '%s\n' /opt/tg2cloud-test; }
cd() { builtin cd "$TG115_TEST_DIR"; }
install() {
  [[ "${1:-}" != -d ]] || return 0
  command install "$@"
}
mktemp() { command mktemp "$TG115_TEST_DIR/backup-XXXXXXXX"; }
docker() {
  printf '%s\n' "$*" >> "$TG115_TEST_DIR/calls"
  case "$*" in
    'compose config --quiet')
      [[ "$TG115_TEST_MODE" != interrupt ]] || kill -TERM "$$"
      [[ "$TG115_TEST_MODE" != invalid ]] || return 1
      ;;
    'compose config --format json') printf '%s\n' '{}' ;;
    'compose exec -T tg2cloud-clouddrive2-bot python -m app.deployment_check'*)
      command cat >/dev/null
      ;;
    inspect*)
      if [[ "$*" == *'.State.Running'* ]]; then
        printf '%s\n' true
        return 0
      fi
      if [[ "$TG115_TEST_MODE" == unhealthy ]] && [[ "$(<.env)" == new ]]; then
        printf '%s\n' unhealthy
      else
        printf '%s\n' healthy
      fi
      ;;
  esac
  return 0
}
curl() {
  if [[ "${TG115_TEST_ACTION:-}" == update ]]; then return 0; fi
  command curl "$@"
}

export INSTALL_DIR=/opt/tg2cloud-test
# shellcheck disable=SC1090
source "$TG115_TEST_SCRIPT" "${TG115_TEST_ACTION:-apply-config}" "$TG115_TEST_CANDIDATE"
