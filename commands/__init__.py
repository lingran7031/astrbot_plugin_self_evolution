"""
Commands 模块 - 命令处理
"""

from .profile import (
    handle_view,
    handle_create,
    handle_update,
    handle_delete,
    handle_stats,
    check_admin as check_profile_admin,
)
from .sticker import handle_sticker, check_admin as check_sticker_admin
from .admin import handle_shut, handle_db, check_admin as check_admin_admin
from .system import handle_version, handle_help

__all__ = [
    "handle_view",
    "handle_create",
    "handle_update",
    "handle_delete",
    "handle_stats",
    "handle_sticker",
    "handle_shut",
    "handle_db",
    "handle_version",
    "handle_help",
    "check_profile_admin",
    "check_sticker_admin",
    "check_admin_admin",
]
