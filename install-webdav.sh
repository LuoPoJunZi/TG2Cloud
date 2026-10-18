#!/usr/bin/env bash
# Independent read-only add-on. Never calls install.sh or installs Bot packages.
set -Eeuo pipefail
umask 077
command -v python3 >/dev/null 2>&1 || { printf '需要 Python 3.10+，请人工准备。\n' >&2; exit 2; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 2)' || exit 2
script_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if [[ -f "$script_root/src/tg2cloud/addons/external_webdav/cli.py" && -f "$script_root/scripts/run_source.py" ]]; then
  exec python3 -B "$script_root/scripts/run_source.py" webdav "$@"
fi
# An installed management command is offline: do not download code for status.
if [[ -e /usr/local/bin/tg2cloud-webdav || -L /usr/local/bin/tg2cloud-webdav ]]; then
  python3 -B - <<'CHECK'
import os
import re
import sys
from pathlib import Path
try:
    command = Path("/usr/local/bin/tg2cloud-webdav")
    match = re.fullmatch(r'#!/bin/sh\n# TG2Cloud external_webdav managed\nexec python3 -B (/opt/tg2cloud-webdav/runtime/[0-9a-f]{64}/scripts/run_source.py) webdav "\$@"\n', command.read_text())
    if not match or os.geteuid() != 0 or command.stat().st_mode & 0o077:
        raise ValueError
    for path in (command, Path(match[1])):
        if path.resolve() != path or not path.is_file():
            raise ValueError
        for parent in (path, *path.parents):
            info = parent.stat()
            if info.st_uid != 0 or info.st_mode & 0o022:
                raise ValueError
except (OSError, ValueError):
    print("现有 tg2cloud-webdav 命令归属或权限无法验证，停止，不执行或覆盖。", file=sys.stderr)
    sys.exit(2)
CHECK
  exec /usr/local/bin/tg2cloud-webdav "$@"
fi
for argument in "$@"; do
  case "$argument" in
    -h|--help) printf '独立外部 WebDAV：install/status/check/enable/disable/configure/uninstall/upgrade/print-config\n参数：--edition clouddrive2|openlist --install-dir DIR --sample-file RELATIVE_FILE\n远程首次安装要求包含本功能的正式 Release（v1.3.1 起），并校验源码包；不使用 main 业务代码。\n'; exit 0 ;;
    status|check|enable|disable|configure|uninstall|upgrade|print-config)
      printf '尚无离线维护命令；先安装包含本功能的正式 Release。\n' >&2; exit 2 ;;
  esac
done
bootstrap_dir="$(mktemp -d /tmp/tg2cloud-webdav-bootstrap.XXXXXXXX)"
child_pid=""
cleanup() {
  case "$bootstrap_dir" in
    /tmp/tg2cloud-webdav-bootstrap.*) [[ -d "$bootstrap_dir" && ! -L "$bootstrap_dir" ]] && rm -rf -- "$bootstrap_dir" ;;
  esac
  return 0
}
trap cleanup EXIT
cancel() {
  if [[ -n "$child_pid" ]]; then kill -TERM -- "$child_pid" 2>/dev/null || true; wait "$child_pid" 2>/dev/null || true; fi
  exit 130
}
trap cancel INT TERM HUP
# This small loader verifies the stable source asset before any downloaded
# Python is executed. There is deliberately no moving-main/old-helper fallback.
python3 -B - "$bootstrap_dir" <<'PY' &
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

def valid(url):
    item = urllib.parse.urlsplit(url)
    if (item.scheme != "https" or item.hostname not in {"api.github.com", "github.com", "release-assets.githubusercontent.com"}
            or item.username or item.password or item.port not in (None, 443) or item.fragment):
        raise ValueError("不受支持的发布下载地址")

class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        valid(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def read(url, maximum):
    valid(url)
    req = urllib.request.Request(url, headers={"User-Agent": "TG2Cloud-external-WebDAV"})
    with urllib.request.build_opener(Redirect()).open(req, timeout=60) as response:
        body = response.read(maximum + 1)
    if len(body) > maximum:
        raise ValueError("发布资源超过上限")
    return body

try:
    root = Path(sys.argv[1])
    api = "https://api.github.com/repos/LuoPoJunZi/TG2Cloud"
    release = json.loads(read(api + "/releases/latest", 2097152))
    tag = release.get("tag_name", "")
    if release.get("draft") is not False or release.get("prerelease") is not False or not re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag):
        raise ValueError("只允许正式稳定 Release")
    name = "TG2Cloud-" + tag + "-source.tar.gz"
    urls = {}
    for expected in (name, "SHA256SUMS.txt"):
        assets = [asset for asset in release.get("assets", []) if asset.get("name") == expected]
        url = "https://github.com/LuoPoJunZi/TG2Cloud/releases/download/" + tag + "/" + expected
        if len(assets) != 1 or assets[0].get("browser_download_url") != url:
            raise ValueError("正式源码资源／校验清单缺失")
        urls[expected] = url
    sums = read(urls["SHA256SUMS.txt"], 16384).decode("ascii")
    hashes = re.findall(r"^([0-9a-f]{64})  " + re.escape(name) + r"$", sums, re.MULTILINE)
    content = read(urls[name], 104857600)
    if len(hashes) != 1 or hashlib.sha256(content).hexdigest() != hashes[0]:
        raise ValueError("源码 SHA256 校验失败（校验和不是数字签名）")
    archive = root / name
    with archive.open("xb") as writer:
        writer.write(content)
    source = root / "source"
    source.mkdir(mode=0o700)
    seen, size = set(), 0
    with tarfile.open(archive, "r:gz") as bundle:
        for index, member in enumerate(bundle):
            path = PurePosixPath(member.name)
            if (index >= 20000 or not path.parts or path.parts[0] != "TG2Cloud-" + tag or path.is_absolute()
                    or ".." in path.parts or "\\" in member.name or ":" in member.name
                    or member.name in seen or not (member.isfile() or member.isdir())):
                raise ValueError("发布归档包含不安全路径或类型")
            seen.add(member.name)
            size += member.size
            if member.size < 0 or member.size > 33554432 or size > 262144000:
                raise ValueError("解压资源超过上限")
            target = source.joinpath(*path.parts[1:])
            if member.isdir():
                target.mkdir(mode=0o700, parents=True, exist_ok=True)
            else:
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with bundle.extractfile(member) as reader, target.open("xb") as writer:
                    shutil.copyfileobj(reader, writer)
                target.chmod(0o600)
    sys.path.insert(0, str(source / "src"))
    from tg2cloud.addons.external_webdav.releases import CONTRACT, FEATURE
    from tg2cloud.deployment.releases import ReleaseClient, source_version
    if json.loads((source / FEATURE).read_text()) != CONTRACT or source_version(source) != tag[1:]:
        raise ValueError("此稳定版不支持外部 WebDAV；不会回退到 main")
    pinned = ReleaseClient().resolve(tag)
    identity = {"source": "stable-release", "tag": tag, "commit": pinned.commit, "archive_sha256": hashes[0]}
    (source / ".external-webdav-source.json").write_text(json.dumps(identity))
    print("外部 WebDAV 正式源码已验证：" + tag + " / " + pinned.commit, flush=True)
except Exception:
    print("外部 WebDAV 引导失败：正式资源尚未包含本功能或校验／网络失败；未使用 main、未修改实例。", file=sys.stderr)
    sys.exit(1)
PY
child_pid="$!"
wait "$child_pid"
child_pid=""
python3 -B "$bootstrap_dir/source/scripts/run_source.py" webdav "$@" &
child_pid="$!"
wait "$child_pid"
