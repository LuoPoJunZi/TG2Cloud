from __future__ import annotations

import datetime as dt
import re
import shlex

from .state import validate_domain

PROXY_ROOT = "/opt/tg2cloud-proxy"

_CERTIFICATE_CHECK_SCRIPT = """import datetime
import pathlib
import sys

from cryptography import x509

certificate = x509.load_pem_x509_certificate(pathlib.Path(sys.argv[1]).read_bytes())
names = certificate.extensions.get_extension_for_class(
    x509.SubjectAlternativeName
).value.get_values_for_type(x509.DNSName)
expires = getattr(certificate, "not_valid_after_utc", None)
if expires is None:
    expires = certificate.not_valid_after.replace(tzinfo=datetime.timezone.utc)
valid = sys.argv[2] in names and expires > datetime.datetime.now(
    datetime.timezone.utc
) + datetime.timedelta(days=7)
if valid:
    print(expires.strftime("%Y-%m-%dT%H:%M:%SZ"))
raise SystemExit(0 if valid else 1)
"""

def parse_certificate_enddate(value: str, *, now: dt.datetime | None = None) -> tuple[str, int]:
    raw = value.strip().removeprefix("notAfter=").strip()
    try:
        if raw.endswith("Z"):
            expires = dt.datetime.fromisoformat(raw[:-1] + "+00:00")
        else:
            expires = dt.datetime.strptime(raw, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=dt.timezone.utc)
    except ValueError as exc:
        raise ValueError("无法解析 HTTPS 证书到期时间。") from exc
    current = now or dt.datetime.now(dt.timezone.utc)
    days = max(-1, int((expires - current).total_seconds() // 86400))
    return expires.date().isoformat(), days

def renewal_summary(markers: dict[str, str]) -> str:
    def stamp(key: str) -> str:
        value = markers.get("PROXY_RENEW_" + key, "")
        try:
            if not re.fullmatch(r"[0-9]{1,12}", value):
                return "尚无记录"
            return dt.datetime.fromtimestamp(int(value), dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        except (ValueError, OverflowError, OSError):
            return "记录无法识别"

    result = {"OK": "通过", "FAILED": "失败，需查看 VPS 的 Certbot 日志"}.get(
        markers.get("PROXY_RENEW_RESULT", ""), "尚无记录"
    )
    return (
        f"\n最近续期检查：{stamp('ATTEMPT')}（{result}）"
        f"\n最近检查成功：{stamp('SUCCESS')}；最近证书变更：{stamp('RENEWED')}"
        f"\n预计下次检查：{stamp('NEXT')}。检查成功不代表本次发生续签。"
    )

def renewal_warnings(markers: dict[str, str], now: dt.datetime | None = None) -> tuple[str, ...]:
    warnings = []
    if markers.get("PROXY_RENEW_RESULT") == "FAILED":
        warnings.append("最近自动续期检查失败，请查看 Certbot 日志并执行续期演练。")
    value = markers.get("PROXY_RENEW_ATTEMPT", "")
    if value:
        try:
            checked = int(value) if re.fullmatch(r"[0-9]{1,12}", value) else 0
            age = (now or dt.datetime.now(dt.timezone.utc)).timestamp() - checked
            if checked <= 0 or age < -300:
                warnings.append("续期记录时间异常，请核对 VPS 时钟和检查记录。")
            elif age > 26 * 3600:  # Two 12h cycles plus scheduling grace.
                warnings.append("超过 26 小时没有新的续期检查记录，请检查续期容器。")
        except (ValueError, OverflowError):
            warnings.append("续期记录无法识别，请检查续期容器。")
    return tuple(warnings)

def dry_run_cleanup_script(task_id: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{32}", task_id):
        raise ValueError("invalid maintenance task id")
    name = "tg2cloud-proxy-dry-run-" + task_id
    return f"""
name={shlex.quote(name)}
if timeout 10s docker container inspect "$name" >/dev/null 2>&1; then
  owner="$(timeout 10s docker inspect --format '{{{{index .Config.Labels "com.tg2cloud.task"}}}}' "$name" 2>/dev/null)"
  role="$(timeout 10s docker inspect --format '{{{{index .Config.Labels "com.tg2cloud.role"}}}}' "$name" 2>/dev/null)"
  if [[ "$owner" != {task_id} || "$role" != maintenance-dry-run ]]; then
    printf 'TG2CLOUD_PROXY_TASK_CLEANUP=REFUSED\\n'; return 1
  fi
  timeout 10s docker rm -f "$name" >/dev/null 2>&1 || {{ printf 'TG2CLOUD_PROXY_TASK_CLEANUP=FAILED\\n'; return 1; }}
else
  timeout 10s docker info >/dev/null 2>&1 || {{ printf 'TG2CLOUD_PROXY_TASK_CLEANUP=UNKNOWN\\n'; return 1; }}
fi
printf 'TG2CLOUD_PROXY_TASK_CLEANUP=OK\\n'
"""

def renewal_dry_run_command(domain: str, task_id: str, seconds: int = 540) -> str:
    domain = validate_domain(domain)
    cleanup = dry_run_cleanup_script(task_id)
    if type(seconds) is not int or not 1 <= seconds <= 540:
        raise ValueError("invalid task deadline")
    script = f"""
cleanup() {{ {cleanup} }}
finish() {{ local result="$?"; trap - EXIT HUP INT TERM; cleanup || result=1; exit "$result"; }}
trap finish EXIT
trap 'exit 143' HUP TERM
trap 'exit 130' INT
timeout --signal=TERM --kill-after=15s {seconds}s docker compose \
  -f {PROXY_ROOT}/docker-compose.yml run --rm --no-deps \
  --name tg2cloud-proxy-dry-run-{task_id} \
  --label com.tg2cloud.task={task_id} --label com.tg2cloud.role=maintenance-dry-run \
  --entrypoint certbot certbot renew --dry-run --cert-name {shlex.quote(domain)} \
  --webroot -w /var/www/certbot --non-interactive --no-random-sleep-on-renew --no-directory-hooks
"""
    return "bash -c " + shlex.quote(script)
