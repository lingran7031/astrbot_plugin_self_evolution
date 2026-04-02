"""
Help Catalog - Unified command display data.

This module maintains a unified command catalog that serves as the single source
of truth for both text and image help displays.

Each command entry contains:
- group: base/user/admin/persona
- command: full display string
- desc: brief description
- admin_only: whether only admins can see this command
"""

from dataclasses import dataclass
from typing import Literal

CommandGroup = Literal["base", "user", "admin", "persona"]


@dataclass
class HelpCommand:
    group: CommandGroup
    command: str
    desc: str
    admin_only: bool = False


HELP_CATALOG_VERSION = 1


def get_user_commands() -> list[HelpCommand]:
    """Returns commands visible to regular users (excludes admin and persona group commands)."""
    return [cmd for cmd in _FULL_CATALOG if cmd.group in ("base", "user")]


def get_admin_commands() -> list[HelpCommand]:
    """Returns all commands including admin-only ones."""
    return _FULL_CATALOG


def get_commands_by_group(include_admin: bool = True) -> dict[CommandGroup, list[HelpCommand]]:
    """Returns commands grouped, optionally filtering admin commands."""
    commands = _FULL_CATALOG if include_admin else get_user_commands()
    groups: dict[CommandGroup, list[HelpCommand]] = {
        "base": [],
        "user": [],
        "admin": [],
        "persona": [],
    }
    for cmd in commands:
        groups[cmd.group].append(cmd)
    return groups


_FULL_CATALOG: list[HelpCommand] = [
    # base group
    HelpCommand("base", "/system help", "查看帮助"),
    HelpCommand("base", "/system help text", "查看文本帮助"),
    HelpCommand("base", "/system version", "查看插件版本"),
    HelpCommand("base", "/reflect", "手动触发自我反省"),
    # user group
    HelpCommand("user", "/affinity show", "查看好感度评分"),
    HelpCommand("user", "/san show", "查看 SAN 状态"),
    HelpCommand("user", "/今日老婆", "查看今日老婆"),
    HelpCommand("user", "/addmeal <菜名>", "添加菜品（仅群聊）"),
    HelpCommand("user", "/delmeal <菜名>", "删除菜品"),
    HelpCommand("user", "/profile view [用户ID]", "查看用户画像"),
    HelpCommand("user", "/profile create [用户ID]", "创建画像"),
    HelpCommand("user", "/profile update [用户ID]", "更新画像"),
    # admin group
    HelpCommand("admin", "/banuseraddmeal @用户", "禁止用户添加菜品"),
    HelpCommand("admin", "/unbanuseraddmeal @用户", "解禁用户"),
    HelpCommand("admin", "/set_affinity @用户 <分数>", "强制设置好感度"),
    HelpCommand("admin", "/affinity debug <用户ID>", "查看好感度详情"),
    HelpCommand("admin", "/san set [值]", "设置 SAN 值"),
    HelpCommand("admin", "/profile delete <用户ID>", "删除用户画像"),
    HelpCommand("admin", "/profile stats", "画像统计"),
    HelpCommand("admin", "/sticker list [页码]", "查看表情包列表"),
    HelpCommand("admin", "/sticker preview <UUID>", "预览表情包"),
    HelpCommand("admin", "/sticker delete <UUID>", "删除表情包"),
    HelpCommand("admin", "/sticker disable <UUID>", "禁用表情包"),
    HelpCommand("admin", "/sticker enable <UUID>", "启用表情包"),
    HelpCommand("admin", "/sticker clear", "清空表情包"),
    HelpCommand("admin", "/sticker stats", "表情包统计"),
    HelpCommand("admin", "/sticker sync", "同步表情包文件"),
    HelpCommand("admin", "/sticker add", "添加表情包"),
    HelpCommand("admin", "/sticker migrate", "迁移表情包"),
    HelpCommand("admin", "/evolution review [页码]", "待审人格进化"),
    HelpCommand("admin", "/evolution approve <ID>", "批准人格进化"),
    HelpCommand("admin", "/evolution reject <ID>", "拒绝人格进化"),
    HelpCommand("admin", "/evolution clear", "清空待审进化"),
    HelpCommand("admin", "/evolution stats [scope_id]", "查看进化统计"),
    HelpCommand("admin", "/shut [分钟]", "让 AI 闭嘴（0 取消）"),
    HelpCommand("admin", "/db show", "查看数据库统计"),
    HelpCommand("admin", "/db reset", "清空所有数据"),
    HelpCommand("admin", "/db rebuild", "重建数据库"),
    HelpCommand("admin", "/db confirm", "确认数据库操作"),
    # persona group
    HelpCommand("persona", "/persona state [scope]", "查看人格状态"),
    HelpCommand("persona", "/persona status [scope]", "查看人格状态快照"),
    HelpCommand("persona", "/persona tick [scope] [quality]", "手动推进人格时间"),
    HelpCommand("persona", "/persona todo [scope]", "查看待办事项"),
    HelpCommand("persona", "/persona effects [scope]", "查看当前效果"),
    HelpCommand("persona", "/persona apply [scope] [quality]", "应用人格效果"),
    HelpCommand("persona", "/persona today [scope]", "查看今日摘要"),
    HelpCommand("persona", "/persona consolidate [scope] [date]", "执行人格日结"),
]


def format_text_help(is_admin: bool = False) -> str:
    """Format the catalog as plain text help."""
    groups = get_commands_by_group(include_admin=is_admin)
    lines = ["【Self-Evolution 指令帮助】", ""]

    group_names = {
        "base": "基础",
        "user": "用户",
        "admin": "管理",
        "persona": "Persona",
    }

    for group_key, group_name in group_names.items():
        cmds = groups.get(group_key, [])
        if not cmds:
            continue
        if group_key == "admin" and not is_admin:
            continue
        lines.append(f"【{group_name}】")
        for cmd in cmds:
            lines.append(f"{cmd.command:<40} - {cmd.desc}")
        lines.append("")

    if is_admin:
        lines.append("发送 /system help text 查看文本版")
        lines.append("管理员可使用 /system help bg ... 自定义背景")
    else:
        lines.append("发送 /system help text 查看文本版")

    return "\n".join(lines).strip()
