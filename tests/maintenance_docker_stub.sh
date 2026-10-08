#!/usr/bin/env bash
# Local fixture for an owned one-off container; never invokes real Docker.
set -eu
case "$1" in
  compose)
    touch "$TG2CLOUD_TEST_TASK_ROOT/container"
    sleep 10
    ;;
  container) test -f "$TG2CLOUD_TEST_TASK_ROOT/container" ;;
  inspect)
    if [[ "$3" == *com.tg2cloud.task* ]]; then
      printf '%s\n' "$TG2CLOUD_TEST_TASK_OWNER"
    else
      printf 'maintenance-dry-run\n'
    fi
    ;;
  rm) rm -- "$TG2CLOUD_TEST_TASK_ROOT/container" ;;
  info) exit 0 ;;
  *) exit 2 ;;
esac
