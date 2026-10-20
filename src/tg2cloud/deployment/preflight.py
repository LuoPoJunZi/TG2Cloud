from __future__ import annotations

import os
import shutil

from tg2cloud.cli import terminal
from tg2cloud.deployment import architecture, configuration, instances
from tg2cloud.deployment.host import LocalSession, SafeLog
from tg2cloud.deployment.profiles import ProductProfile
from tg2cloud.deployment.resources import (
    GIB,
    assess_storage_choice,
    build_probe_command,
    parse_probe_output,
    recommend_storage,
)


def validate_host(*, log=None) -> None:
    host = architecture.detect_host()
    if os.geteuid() != 0:
        raise ValueError("请在 Linux VPS 以 root 运行；Windows 用户可通过 SSH 登录后运行脚本")
    if shutil.which("bash") is None:
        raise ValueError("缺少 Bash")
    architecture.check_environment()
    if log:
        host.describe(log)


def probe_resources(instance: instances.Instance, session: LocalSession):
    code, output = session.run(
        build_probe_command(str(instance.directory), instance.product.backup_dir), timeout=45,
    )
    if code:
        raise ValueError("资源预检未完整执行")
    return parse_probe_output(output)


def storage_options(product: ProductProfile) -> dict:
    return {
        "managed_clouddrive": not product.is_openlist, "managed_storage": True,
        "requires_fuse": product.requires_fuse,
        "minimum_memory_mb": 900 if product.is_openlist else 1800,
    }


def choose_storage(instance: instances.Instance, session: LocalSession, log: SafeLog, ui: terminal.Terminal) -> tuple[str, str]:
    """First-install advice only. Never rewrite an existing instance's settings."""
    if instance.present:
        raise ValueError("已有实例保留磁盘配置，不进入首次安装推荐")
    resources = probe_resources(instance, session)
    options = storage_options(instance.product)
    advice = recommend_storage(resources, **options)
    log(f"安装目录所在磁盘：总计 {resources.storage_total_bytes / GIB:.1f}GB；可用 {resources.storage_available_bytes / GIB:.1f}GB")
    log(f"CPU {resources.cpu_cores} 核；内存 {resources.memory_total_bytes / GIB:.1f}GB；可用 {resources.memory_available_bytes / GIB:.1f}GB")
    if resources.docker_root_detected and not resources.docker_same_filesystem:
        log(f"Docker 使用独立文件系统，可用 {resources.docker_storage_available_bytes / GIB:.1f}GB；与安装目录分别校验")
    log("任务预算是暂存额度，不是磁盘分区，也不限制网关全部缓存。")
    plans = {"1": advice.stream_first, "2": advice.balanced}
    for key, plan in plans.items():
        state = "（推荐）" if plan.key == advice.preferred_key else ""
        if not plan.safe:
            state = "（不可用：" + plan.reason + "）"
        log(f"[{key}] {plan.label}：任务预算 {plan.budget_gb}GB，最少保留 {plan.reserve_gb}GB{state}")
    log("[3] 手动设置（仍需通过容量、内存、FUSE 和 Docker 文件系统检查）")
    default = next((key for key, plan in plans.items() if plan.key == advice.preferred_key), "3")

    def choice(value: str) -> str:
        if value not in {"1", "2", "3"}:
            raise ValueError("请选择 1、2 或 3")
        return value

    while True:
        selected = ui.ask("存储方案", default=default, validate=choice)
        if selected == "3":
            budget = ui.ask("本地任务预算 GB", default="20", validate=configuration.size_gb)
            reserve = ui.ask("磁盘最少保留 GB", default="8", validate=configuration.size_gb)
        else:
            plan = plans[selected]
            if not plan.safe:
                log("该方案不可用：" + plan.reason)
                if not ui.confirm("是否重新选择存储方案？"):
                    raise ValueError("已停止安装，未写入配置")
                continue
            budget, reserve = str(plan.budget_gb), str(plan.reserve_gb)
        assessment = assess_storage_choice(resources, budget_gb=float(budget), reserve_gb=float(reserve), **options)
        if float(reserve) >= 8 and assessment.safe:
            log(f"已选择任务预算 {budget}GB / 最少保留 {reserve}GB；执行前将重新探测并校验")
            return budget, reserve
        log("存储配置不可用：" + (assessment.reason if float(reserve) >= 8 else "最少保留空间不能低于 8GB"))
        if not ui.confirm("是否重新选择存储方案？"):
            raise ValueError("已停止安装，未写入配置")


def resource_check(instance: instances.Instance, config: dict[str, str], session: LocalSession, log: SafeLog) -> None:
    resources = probe_resources(instance, session)
    assessment = assess_storage_choice(
        resources, budget_gb=float(configuration.size_gb(config.get("LOCAL_TEMP_BUDGET_GB", "20"))),
        reserve_gb=float(configuration.size_gb(config.get("MIN_FREE_DISK_GB", "8"))),
        **storage_options(instance.product),
    )
    log(assessment.reason)
    if not assessment.safe:
        raise ValueError("资源不足：" + assessment.reason + "；不会自动降低预算或修改已有配置")
