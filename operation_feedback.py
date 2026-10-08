"""Small, deterministic presentation helpers; no network or deployment actions."""

from __future__ import annotations

import re

STAGES = {
    "SSH": ("连接 VPS", "请检查 SSH 地址、端口、登录方式及主机身份提示。"),
    "ENVIRONMENT": ("检查基础环境", "请核对资源预检、磁盘空间与用户权限。"),
    "UPLOAD": ("上传部署资源", "请核对 SSH/SFTP 连通性和 VPS 临时目录权限。"),
    "INSTALL": ("准备运行环境", "请查看安装日志；不要直接删除已有配置或运行数据。"),
    "GATEWAY": ("启动存储服务", "请查看网关容器日志及镜像拉取结果。"),
    "BOT": ("构建并启动 Bot", "请查看容器构建日志和必填配置检查结果。"),
    "HEALTH": ("检查基础服务", "请查看健康检查结果；基础服务通过不代表 WebDAV 可写。"),
    "HTTPS_ENV": ("检查 HTTPS 环境", "请核对 DNS、80/443 归属及回环管理端口。"),
    "ACME": ("准备 ACME 验证", "请查看 Nginx 配置与安全 HTTP 引导日志。"),
    "CERTIFICATE": ("申请或复用证书", "请依据 Certbot 日志核对 DNS、公网 80 和签发频率；不要反复签发。"),
    "HTTPS_VERIFY": ("验收 HTTPS", "请查看失败的自检项目；公网连通仍需从外部网络检查。"),
    "PROXY_BACKUP": ("备份共享代理", "请检查备份目录权限、可用空间与完整性检查结果。"),
    "RENEW_DRY_RUN": ("演练证书续期", "请检查 ACME 公网连通性；dry-run 不替换正式证书。"),
}


def stage_from_log(text: str) -> str:
    match = re.fullmatch(r"TG2CLOUD_STAGE=([A-Z_]+)", text.strip())
    return match[1] if match and match[1] in STAGES else ""


def failure_details(error: object, stage: str) -> str:
    """Explain the known stage, never infer a root cause from an unknown error."""
    if stage not in STAGES or getattr(error, "user_cancelled", False):
        return str(error)
    title, advice = STAGES[stage]
    return f"失败阶段：{title}\n\n{error}\n\n建议：{advice}"


def version_summary(local: str, remote: str, *, installed: bool = True) -> str:
    pattern = r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    match = re.fullmatch(pattern, remote)
    version = remote if match else "未获取"
    if not installed:
        version, note = "未安装", "尚未安装当前 Edition 的 Bot。"
    elif not match:
        note = "无法确认 VPS Bot 版本；未把部署器版本当作服务器版本。"
    elif remote == local:
        note = "版本一致；未校验构建来源，不会自动更新 VPS。"
    elif tuple(map(int, match.groups())) < tuple(map(int, local.split("."))):
        note = "VPS Bot 版本较旧；下载新部署器不会自动更新 VPS，请使用现有更新流程。"
    else:
        note = "VPS Bot 版本较新；请核对部署器版本，不要自动降级。"
    return f"部署器版本：v{local}\nVPS Bot 版本：{'v' if match and installed else ''}{version}\n{note}"
