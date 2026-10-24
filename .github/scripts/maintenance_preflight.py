"""Read-only maintenance release checklist for the local worktree; never publish."""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "src"))

import baseline_metadata
import prepare_bootstrap
import release_metadata
import source_release

from tg2cloud.deployment import baselines


def check_manifests(root: Path) -> None:
    for name, expected in (("bootstrap", prepare_bootstrap.helper_files(root)),
                           ("runtime", prepare_bootstrap.runtime_files(root))):
        actual = json.loads((root / f"packaging/{name}-manifest.json").read_text(encoding="utf-8"))
        if actual != {"format": 1, "files": expected}:
            raise ValueError("source manifest mismatch")


def check_helpers(root: Path) -> None:
    """Unlike Tag packaging, compare *working files*, including uncommitted edits."""
    expected = prepare_bootstrap.helper_files(root)
    pins = set()
    for name in ("install.sh", "install-lan.sh", "uninstall.sh"):
        text = (root / name).read_text(encoding="utf-8")
        matches = re.findall(r'^installer_commit\s*=\s*"([0-9a-f]{40})"$', text, re.MULTILINE)
        if len(matches) != 1:
            raise ValueError("invalid helper pin")
        pin = matches[0]
        pins.add(pin)
        paths = []
        for block in re.findall(r"<<'PY'[^\n]*\n(.*?)^PY\s*$", text, re.MULTILINE | re.DOTALL):
            for node in ast.walk(ast.parse(block)):
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "files" for t in node.targets):
                    paths.extend(ast.literal_eval(node.value))
        if sorted(paths) != expected:
            raise ValueError("bootstrap manifest mismatch")
        for path in expected:
            pinned = source_release.git(root, "show", pin + ":" + path).replace(b"\r\n", b"\n")
            if pinned != (root / path).read_bytes().replace(b"\r\n", b"\n"):
                raise ValueError("unpublished helper changes")
    if len(pins) != 1:
        raise ValueError("helper pins disagree")


def inspect(root: Path = ROOT, *, previous_tag: str = "") -> dict:
    checks = []
    def run(key, label, operation, failure):
        try:
            operation()
        except Exception:  # noqa: BLE001 - never echo git output or private paths
            checks.append({"key": key, "label": label, "state": "blocked", "detail": failure})
        else:
            checks.append({"key": key, "label": label, "state": "passed"})
    run("identity", "版本与发布文档", lambda: release_metadata.release_metadata(root, "v" + release_metadata.source_version(root)),
        "核对唯一版本、入口版本、CHANGELOG 与 Release Notes；不自动提升版本。")
    run("manifests", "源码载荷清单", lambda: check_manifests(root), "审阅并重新生成源码清单；不忽略新增或缺失文件。")
    def catalog():
        if previous_tag and previous_tag not in baselines.CATALOG:
            raise ValueError("previous stable baseline not reviewed")
        for tag, record in baselines.CATALOG.items():
            if baseline_metadata.entry(tag, record["commit"]) != record:
                raise ValueError("baseline mismatch")
    run("baselines", "受支持旧版固定基线", catalog,
        "核对完整 Git 历史和已审阅的原正式提交；缺失基线须人工核验，不能自动信任版本文本或任意 SHA。")
    run("helpers", "在线 helper 与本地候选一致性", lambda: check_helpers(root),
        "先公开并验证辅助提交 A，再在入口 B 固定 A；本地尚未发布的改动不能作为已可在线安装。")
    return {"scope": "local-static-preflight-only", "checks": checks,
            "local_checks_passed": all(item["state"] == "passed" for item in checks),
            "not_checked": ["remote-ci", "release-assets", "real-vps", "telegram-transfer", "production-restore"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="本地维护发布预检；只读，不提交、推送、改 pin 或发布")
    parser.add_argument("--previous-tag", default="", help="本次必须支持升级的旧正式版本，例如 v1.4.4")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = inspect(previous_tag=args.previous_tag)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for item in report["checks"]:
            print(item["label"] + "：" + ("通过" if item["state"] == "passed" else "发布前待处理"))
            if "detail" in item:
                print("  " + item["detail"])
        print("仅本地静态检查；不代表远端 CI、实机验收或正式发布完成。")
    return 0 if report["local_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
