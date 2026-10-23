"""A member sees only their own accounting, never other members or system data."""
from tg2cloud.telegram.views import format_bytes


def format_quota(value: dict) -> str:
    def limit(key):
        return str(value[key]) if value[key] else "不限"
    return ("👤 个人配额\n\n📦 每日额度：" + (format_bytes(value["daily_bytes"]) if value["daily_bytes"] else "不限")
            + "\n📊 今日已完成：" + format_bytes(value["completed_bytes"])
            + "\n💾 未完成预留：" + format_bytes(value["reserved_bytes"])
            + "\n💾 可用额度：" + (format_bytes(value["available_bytes"]) if value["available_bytes"] is not None else "不限")
            + f"\n⏳ 排队任务：{value['queued']}/" + limit("max_queued")
            + f"\n⬇️ 当前传输：{value['active']}/" + limit("max_active")
            + "\n按配置时区的日历日计量；预留跨天保留。WebDAV 大小复验后计量一次。")
