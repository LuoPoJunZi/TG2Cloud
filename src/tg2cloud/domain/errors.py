"""Small shared recovery policies; no remote mutations or backend assumptions."""

from __future__ import annotations

from tg2cloud.domain.models import STAGING_PATTERN, StagingScan

__all__ = ["STAGING_PATTERN", "RemoteReviewRequired", "StagingScan", "failure_kind", "needs_review", "redact_text", "safe_failure"]

import re
from urllib.parse import quote


class RemoteReviewRequired(RuntimeError):
    """The recorded object must be kept until the owner chooses a recovery action."""

def failure_kind(error: BaseException | str) -> str:
    text = str(error)
    if isinstance(error, RemoteReviewRequired) or text.startswith(("REMOTE_REVIEW:", "MOVE_UNCERTAIN:")):
        return "remote_conflict"
    for pattern, kind in (
        (r"\b401\b|unauthorized", "authentication"),
        (r"\b403\b|forbidden", "permission"),
        (r"\b429\b|too many requests", "rate_limited"),
        (r"\b5\d\d\b", "server"),
        (r"\b409\b|\b412\b|immutable|already exists", "remote_conflict"),
    ):
        if re.search(pattern, text, re.IGNORECASE):
            return kind
    if isinstance(error, FileNotFoundError):
        return "local_missing"
    return "network"

FAILURE_MESSAGES = {
    "authentication": "WebDAV 认证失败（401）；请核对凭据后手动重试",
    "permission": "WebDAV 权限不足（403）；请核对目录和用户权限",
    "rate_limited": "WebDAV 请求受限（429）；暂停自动重试，等待服务端解除限流",
    "server": "存储服务暂时异常（5xx）；已保留任务信息",
    "remote_conflict": "远端文件不完整或结果不确定；保留远端和本地文件，请核对后选择换名重传",
    "local_missing": "本地文件不可访问；请检查磁盘和挂载状态",
    "network": "传输连接或验证失败；已保留任务信息供重试",
}

def safe_failure(error: BaseException | str) -> str:
    """Never persist/forward external stderr, URLs, tokens or passwords."""
    kind = failure_kind(error)
    prefix = "REMOTE_REVIEW: " if kind == "remote_conflict" else ""
    return prefix + FAILURE_MESSAGES[kind]

def needs_review(task: dict) -> bool:
    return task.get("failure_kind") == "remote_conflict" or str(task.get("error") or "").startswith(
        ("REMOTE_REVIEW:", "MOVE_UNCERTAIN:")
    )

def redact_text(text: str, settings) -> str:
    # Mask labelled values before exact replacement can obscure the label itself.
    text = re.sub(r"https?://[^\s\"'<>]+", "[URL]", text)
    text = re.sub(r"(?i)(authorization|token|password|cookie)([=:]\s*)[^\s,;]+",
                  r"\1\2[REDACTED]", text)
    for key in ("bot_token", "api_hash", "cd2_password"):
        value = getattr(settings, key, "")
        if isinstance(value, str) and value:
            for variant in (value, quote(value, safe="")):
                text = text.replace(variant, "[REDACTED]")
    return text
