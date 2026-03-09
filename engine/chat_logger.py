import json
import asyncio
import aiofiles
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import uuid
import logging

logger = logging.getLogger("astrbot")


class ChatLogger:
    """群聊日志记录器 - 异步非阻塞写入"""

    def __init__(self, plugin):
        self.plugin = plugin
        self.log_dir = plugin.data_dir / "chat_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._write_lock = asyncio.Lock()
        self._pending_writes = defaultdict(list)

    def _get_today_log_path(self) -> Path:
        """获取今天的日志文件路径"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"chat_{today}.jsonl"

    async def _cleanup_old_logs(self):
        """清理超过7天的日志文件"""
        try:
            cutoff = datetime.now() - timedelta(days=7)
            for f in self.log_dir.glob("chat_*.jsonl"):
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if mtime < cutoff:
                        f.unlink()
                        logger.info(f"[ChatLogger] 已删除过期日志: {f.name}")
                except Exception as e:
                    logger.warning(f"[ChatLogger] 删除日志失败 {f.name}: {e}")
        except Exception as e:
            logger.warning(f"[ChatLogger] 清理旧日志失败: {e}")

    async def log_message(
        self,
        session_id: str,
        sender_id: str,
        sender_name: str,
        content: str,
        is_ai: bool = False,
    ):
        """记录消息到日志（异步非阻塞）"""
        try:
            msg_uuid = uuid.uuid4().hex[:8]
            msg_time = datetime.now().strftime("%H:%M:%S")

            record = {
                "uuid": msg_uuid,
                "time": msg_time,
                "sender_id": str(sender_id),
                "sender_name": sender_name,
                "content": content,
                "is_ai": is_ai,
                "session_id": session_id,
            }

            # 异步写入（不阻塞主循环）
            asyncio.create_task(self._async_write(record))

            return msg_uuid

        except Exception as e:
            logger.warning(f"[ChatLogger] 生成日志记录失败: {e}")
            return None

    async def _async_write(self, record: dict):
        """异步写入日志文件"""
        try:
            log_path = self._get_today_log_path()
            line = json.dumps(record, ensure_ascii=False) + "\n"

            async with aiofiles.open(log_path, mode="a", encoding="utf-8") as f:
                await f.write(line)

            # 偶尔触发清理检查
            import random

            if random.random() < 0.01:  # 1% 概率
                await self._cleanup_old_logs()

        except Exception as e:
            logger.warning(f"[ChatLogger] 写入日志失败: {e}")

    async def get_message_by_uuid(self, msg_uuid: str) -> dict | None:
        """根据 UUID 查找消息"""
        try:
            # 搜索最近几天的日志文件
            for i in range(7):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                log_path = self.log_dir / f"chat_{date}.jsonl"

                if not log_path.exists():
                    continue

                try:
                    async with aiofiles.open(log_path, mode="r", encoding="utf-8") as f:
                        async for line in f:
                            try:
                                record = json.loads(line.strip())
                                if record.get("uuid") == msg_uuid:
                                    return record
                            except json.JSONDecodeError:
                                continue
                except Exception:
                    continue

            return None
        except Exception as e:
            logger.warning(f"[ChatLogger] 查找消息失败: {e}")
            return None

    async def get_messages_by_sender(
        self, session_id: str, sender_id: str, limit: int = 10
    ) -> list:
        """获取指定发送者的最近消息"""
        results = []

        try:
            for i in range(7):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                log_path = self.log_dir / f"chat_{date}.jsonl"

                if not log_path.exists():
                    continue

                try:
                    async with aiofiles.open(log_path, mode="r", encoding="utf-8") as f:
                        lines = await f.readlines()

                    for line in reversed(lines[-50:]):
                        try:
                            record = json.loads(line.strip())
                            if record.get("session_id") == session_id and record.get(
                                "sender_id"
                            ) == str(sender_id):
                                results.append(record)
                                if len(results) >= limit:
                                    break
                        except json.JSONDecodeError:
                            continue

                    if results:
                        break
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"[ChatLogger] 获取发送者消息失败: {e}")

        return results

    async def get_ai_reply_for_context(
        self, session_id: str, target_session_id: str = None
    ) -> list:
        """获取 AI 在当前或指定会话的回复"""
        results = []

        try:
            for i in range(7):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                log_path = self.log_dir / f"chat_{date}.jsonl"

                if not log_path.exists():
                    continue

                try:
                    async with aiofiles.open(log_path, mode="r", encoding="utf-8") as f:
                        lines = await f.readlines()

                    for line in reversed(lines[-100:]):
                        try:
                            record = json.loads(line.strip())
                            session = target_session_id or session_id
                            if record.get("session_id") == session and record.get(
                                "is_ai"
                            ):
                                results.append(record)
                                if len(results) >= 5:
                                    break
                        except json.JSONDecodeError:
                            continue

                    if results:
                        break
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"[ChatLogger] 获取 AI 回复失败: {e}")

        return results
