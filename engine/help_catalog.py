"""Unified command display data for text help."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CommandGroup = Literal[
    "base",
    "social",
    "meal",
    "profile",
    "sticker",
    "evolution",
    "database",
    "persona",
]


@dataclass
class HelpCommand:
    group: CommandGroup
    command: str
    desc: str
    admin_only: bool = False


HELP_CATALOG_VERSION = 4

GROUP_ORDER: list[CommandGroup] = [
    "base",
    "social",
    "meal",
    "profile",
    "sticker",
    "evolution",
    "database",
    "persona",
]

GROUP_NAMES: dict[CommandGroup, str] = {
    "base": "基础",
    "social": "互动",
    "meal": "群菜单",
    "profile": "画像",
    "sticker": "表情包",
    "evolution": "进化",
    "database": "数据库",
    "persona": "Persona",
}


_FULL_CATALOG: list[HelpCommand] = [
    HelpCommand("base", "/system help", "查看图片版总帮助"),
    HelpCommand("base", "/system help text", "查看纯文本帮助"),
    HelpCommand("base", "/system version", "查看插件版本"),
    HelpCommand("base", "/reflect", "手动触发一次反思"),
    HelpCommand("base", "/今日老婆", "查看今日老婆"),
    HelpCommand("social", "/affinity show", "查看当前好感度"),
    HelpCommand("social", "/san show", "查看当前 SAN 状态"),
    HelpCommand("social", "/affinity debug <用户ID>", "查看详细好感度", admin_only=True),
    HelpCommand("social", "/set_affinity @用户 <分数>", "强制设置好感度", admin_only=True),
    HelpCommand("social", "/san set [值]", "查看或设置 SAN", admin_only=True),
    HelpCommand("social", "/shut [分钟]", "让 AI 暂时闭嘴", admin_only=True),
    HelpCommand("meal", "/addmeal <菜名>", "添加群菜单菜品"),
    HelpCommand("meal", "/delmeal <菜名>", "删除指定菜品"),
    HelpCommand("meal", "/banuseraddmeal @用户", "禁止某人加菜", admin_only=True),
    HelpCommand("meal", "/unbanuseraddmeal @用户", "解除加菜限制", admin_only=True),
    HelpCommand("profile", "/profile view [用户ID]", "查看用户画像"),
    HelpCommand("profile", "/profile create [用户ID]", "创建画像"),
    HelpCommand("profile", "/profile update [用户ID]", "更新画像"),
    HelpCommand("profile", "/profile delete <用户ID>", "删除画像", admin_only=True),
    HelpCommand("profile", "/profile stats", "查看画像统计", admin_only=True),
    HelpCommand("sticker", "/sticker list [页码]", "查看表情包列表", admin_only=True),
    HelpCommand("sticker", "/sticker preview <UUID>", "预览指定表情包", admin_only=True),
    HelpCommand("sticker", "/sticker delete <UUID>", "删除指定表情包", admin_only=True),
    HelpCommand("sticker", "/sticker disable <UUID>", "禁用指定表情包", admin_only=True),
    HelpCommand("sticker", "/sticker enable <UUID>", "启用指定表情包", admin_only=True),
    HelpCommand("sticker", "/sticker clear", "清空全部表情包", admin_only=True),
    HelpCommand("sticker", "/sticker stats", "查看表情包统计", admin_only=True),
    HelpCommand("sticker", "/sticker sync", "同步本地表情包文件", admin_only=True),
    HelpCommand("sticker", "/sticker add", "把刚发送的图片加入表情包", admin_only=True),
    HelpCommand("sticker", "/sticker migrate", "迁移旧表情包数据", admin_only=True),
    HelpCommand("evolution", "/evolution review [页码]", "查看待审核进化", admin_only=True),
    HelpCommand("evolution", "/evolution approve <ID>", "批准指定进化", admin_only=True),
    HelpCommand("evolution", "/evolution reject <ID>", "拒绝指定进化", admin_only=True),
    HelpCommand("evolution", "/evolution clear", "清空待审核队列", admin_only=True),
    HelpCommand("evolution", "/evolution stats [scope_id]", "查看进化统计", admin_only=True),
    HelpCommand("database", "/db show", "查看数据库统计", admin_only=True),
    HelpCommand("database", "/db reset", "清空插件数据", admin_only=True),
    HelpCommand("database", "/db rebuild", "删除并重建数据库", admin_only=True),
    HelpCommand("database", "/db confirm", "确认执行危险操作", admin_only=True),
    HelpCommand("persona", "/personasim state [scope]", "只读当前人格状态", admin_only=True),
    HelpCommand("persona", "/personasim status [scope]", "推进后查看人格快照", admin_only=True),
    HelpCommand("persona", "/personasim tick [scope] [quality]", "手动推进人格时间", admin_only=True),
    HelpCommand("persona", "/personasim todo [scope]", "查看当前脑内待办", admin_only=True),
    HelpCommand("persona", "/personasim effects [scope]", "查看当前状态效果", admin_only=True),
    HelpCommand(
        "persona",
        "/personasim apply [q] [scope]",
        "应用一次互动影响（q: bad/awkward/normal/good/relief/brief）",
        admin_only=True,
    ),
    HelpCommand("persona", "/personasim today [scope]", "查看今日人格摘要", admin_only=True),
    HelpCommand("persona", "/personasim consolidate [scope] [date]", "执行人格日结", admin_only=True),
    HelpCommand("persona", "/personasim think [scope]", "手动触发 LLM 生成内心独白", admin_only=True),
]


def get_user_commands() -> list[HelpCommand]:
    return [cmd for cmd in _FULL_CATALOG if not cmd.admin_only]


def get_admin_commands() -> list[HelpCommand]:
    return _FULL_CATALOG


def get_commands_by_group(include_admin: bool = True) -> dict[CommandGroup, list[HelpCommand]]:
    source = _FULL_CATALOG if include_admin else get_user_commands()
    groups: dict[CommandGroup, list[HelpCommand]] = {group: [] for group in GROUP_ORDER}
    for cmd in source:
        groups[cmd.group].append(cmd)
    return groups


def format_text_help(is_admin: bool = False) -> str:
    groups = get_commands_by_group(include_admin=is_admin)
    lines = ["【Self-Evolution 指令帮助】", ""]

    for group in GROUP_ORDER:
        cmds = groups.get(group, [])
        if not cmds:
            continue
        lines.append(f"【{GROUP_NAMES[group]}】")
        for cmd in cmds:
            lines.append(f"{cmd.command:<42} - {cmd.desc}")
        lines.append("")

    lines.append("发送 /system help 查看图片版帮助")
    return "\n".join(lines).strip()
