import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

logger = logging.getLogger("astrbot")


class ProfileManager:
    """用户画像管理器 - Markdown 文本格式存储"""

    def __init__(self, plugin):
        self.plugin = plugin
        self.profile_dir = plugin.data_dir / "profiles"
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.locks = defaultdict(asyncio.Lock)

    @property
    def precision_mode(self):
        return self.plugin.config.get("profile_precision_mode", "simple")

    def _get_profile_path(self, user_id: str) -> Path:
        return self.profile_dir / f"user_{user_id}.md"

    async def load_profile(self, user_id: str) -> str:
        """读取用户画像（Markdown 文本），无则返回空"""
        path = self._get_profile_path(user_id)
        if path.exists():
            try:
                return path.read_text(encoding="utf-8").strip()
            except IOError as e:
                logger.warning(f"[Profile] 读取画像失败 {user_id}: {e}")
        return ""

    async def save_profile(self, user_id: str, content: str):
        """保存用户画像（Markdown 文本）"""
        path = self._get_profile_path(user_id)
        path.write_text(content, encoding="utf-8")
        logger.info(f"[Profile] 已保存用户画像: {user_id}")

    async def get_profile_summary(self, user_id: str) -> str:
        """获取画像摘要（用于注入 LLM）- 直接返回 Markdown 内容"""
        content = await self.load_profile(user_id)
        if not content:
            return ""

        # 简单模式：直接返回 Markdown 前几行
        lines = content.split("\n")
        preview = "\n".join(lines[:10])
        if len(content) > 500:
            preview += "\n..."
        return preview

    async def cleanup_expired_profiles(self):
        """清理过期画像 - Markdown 模式下只需检查文件修改时间"""
        pass

    async def view_profile(self, user_id: str) -> str:
        """查看用户画像"""
        content = await self.load_profile(user_id)
        if not content:
            return f"用户 {user_id} 暂无画像记录。"
        return f"用户ID: {user_id}\n\n{content}"

    async def delete_profile(self, user_id: str) -> str:
        """删除用户画像"""
        path = self._get_profile_path(user_id)
        if path.exists():
            path.unlink()
            logger.info(f"[Profile] 已删除用户画像: {user_id}")
            return f"已删除用户 {user_id} 的画像。"
        return f"用户 {user_id} 不存在画像记录。"

    async def list_profiles(self) -> dict:
        """列出所有画像统计"""
        files = list(self.profile_dir.glob("user_*.md"))
        return {
            "total_users": len(files),
            "total_tags": 0,
            "total_traits": 0,
        }
