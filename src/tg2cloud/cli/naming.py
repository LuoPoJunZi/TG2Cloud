"""Local naming preview; no Telegram, database, download, upload or renaming."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tg2cloud.domain.naming import caption_candidate, explain_media_name

REASONS = {"meaningful_original": "原名具有可读语义，保留原名",
           "promotional_affixes_removed": "清理明确的推广前后缀，保留有效原名",
           "promotion_without_title": "纯推广原名没有可靠标题，使用安全兜底名",
           "no_caption": "没有说明文字，沿用原名／默认名",
           "no_valid_title": "说明中没有可靠标题，回退原命名",
           "caption_replaced_weak_name": "以清理后的说明替换数字／默认／推广原名",
           "safe_fallback": "候选未通过后缀安全检查，回退原命名"}


def preview(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) - {"file_name", "caption", "fallback", "media_extension"}:
        raise ValueError("只接受 file_name、caption、fallback、media_extension 字段")
    limits = {"file_name": 4096, "caption": 8192, "fallback": 4096, "media_extension": 24}
    for key, limit in limits.items():
        field = value.get(key, "")
        if not isinstance(field, str) or len(field) > limit:
            raise ValueError("命名预览字段类型或长度不正确")
    decision = explain_media_name(value.get("file_name", ""), value.get("caption", ""),
                                  value.get("fallback", "telegram-preview.mp4"),
                                  media_extension=value.get("media_extension", ""))
    _, score = caption_candidate(value.get("caption", ""))
    return {**decision, "reason_text": REASONS[decision["reason"]], "caption_score": score,
            "scope": "single-media-text-only", "writes": False}


def interactive(ui, emit=print):
    value = {"file_name": ui.ask("原文件名（留空模拟默认名）"),
             "media_extension": ui.ask("真实媒体扩展名，例如 .mp4（可留空）")}
    emit("粘贴说明文字，单独一行 . 结束；最多 64 行／8192 字。不读取评论、媒体组或隐藏链接实体。")
    lines = []
    for _ in range(64):
        line = ui.ask("说明", validate=lambda text: text)
        if line == ".":
            break
        lines.append(line)
        if sum(len(part) + 1 for part in lines) > 8192:
            raise ValueError("说明过长，预览停止；未修改任何文件")
    value["caption"] = "\n".join(lines)
    show(preview(value), emit)


def show(result, emit):
    emit("预览文件名：" + result["file_name"])
    emit("选择原因：" + result["reason_text"])
    emit("说明规则评分：" + str(result["caption_score"]) + "（不是 AI 置信度）")
    emit("仅本地预览；不校验远端重名，不修改已登记任务或云端文件。")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="读取本地 JSON 样例；不把说明或秘密放入命令行参数")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出单媒体文字预览结果")
    args = parser.parse_args(argv)
    ui = None
    try:
        if args.input:
            if args.input.is_symlink() or not args.input.is_file():
                raise ValueError("样例须为普通 JSON 文件")
            with args.input.open("rb") as source:
                body = source.read(65537)
            if len(body) > 65536:
                raise ValueError("样例超过 64 KiB")
            result = preview(json.loads(body))
            if args.json:
                print(json.dumps(result, ensure_ascii=True))
            else:
                show(result, print)
        else:
            if args.json:
                raise ValueError("--json 需搭配 --input")
            from .terminal import Terminal
            ui = Terminal()
            interactive(ui)
        return 0
    except (OSError, ValueError, EOFError):
        print("命名预览失败：请核对 JSON 字段、长度和终端；不输出原始输入或异常内容。")
        return 1
    finally:
        if ui is not None:
            ui.close()
