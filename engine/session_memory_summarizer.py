import asyncio
import json
import logging
import time
from datetime import datetime, timedelta

from astrbot.api import logger

from .session_memory_store import SessionMemoryStore

SUMMARY_CHUNK_CHAR_LIMIT = 12000
SUMMARY_CHUNK_MAX_MESSAGES = 200

SESSION_MEMORY_PROMPT = """你是会话记忆分析师。请分析以下 {summary_date} 的聊天记录，提取结构化的记忆信息。

请以JSON格式输出：
{{
    "overview": "一段200-500字的总结，描述当日主要话题、氛围和重要事件",
    "key_facts": ["关键事实1", "关键事实2", "关键事实3", ...],
    "key_entities": ["重要人物或对象1", "重要人物或对象2", ...],
    "tags": ["标签1", "标签2", ...]
}}

规则：
- key_facts 至少3条，最多8条，每条不超过50字
- key_entities 列出当日活跃人物、重要讨论对象、群规、约定、项目名等
- tags 用简洁的词或短语标注主题，最多5个
- 只输出JSON，不要其他内容

消息列表：
{messages}
"""

PARTIAL_MEMORY_PROMPT = """你是会话记忆分析师。以下是 {summary_date} 的聊天记录分段（第 {index}/{total} 段）。

请提取这一段中的关键信息，输出JSON：
{{
    "overview": "这一段的主要话题（1-2句）",
    "key_facts": ["事实1", "事实2", ...],
    "key_entities": ["人物或对象1", "人物或对象2", ...],
    "tags": ["标签1", "标签2"]
}}

消息列表：
{messages}
"""

MERGE_MEMORY_PROMPT = """你是会话记忆分析师。以下是 {summary_date} 的分段记忆分析，请整合成最终的结构化JSON。

整合要求：
1. 合并重复信息
2. overview 整合成一段200-500字的完整总结
3. key_facts 控制在3-8条，每条不超过50字
4. key_entities 合并，去重
5. tags 不超过5个
6. 只输出JSON
"""


class SessionMemorySummarizer:
    def __init__(self, plugin):
        self.plugin = plugin
        self.store = SessionMemoryStore(plugin)

    def _is_private_scope(self, scope_id: str) -> bool:
        return scope_id.startswith("private_")

    def _get_private_scope_user_id(self, scope_id: str) -> str:
        if self._is_private_scope(scope_id):
            return scope_id[len("private_") :]
        return ""

    async def _fetch_scope_messages(self, scope_id: str, msg_count: int = 500):
        """从 NapCat 拉取指定 scope 的消息"""
        try:
            if not self.plugin.context.platform_manager.platform_insts:
                return []

            platform = self.plugin.context.platform_manager.platform_insts[0]
            if not hasattr(platform, "get_client"):
                return []

            client = platform.get_client()
            if not client:
                return []

            bot = client
            group_id = None if self._is_private_scope(scope_id) else scope_id
            user_id = self._get_private_scope_user_id(scope_id) if self._is_private_scope(scope_id) else None

            all_messages = []
            latest_seq = None
            retry_count = 0
            max_retries = 3

            while len(all_messages) < msg_count and retry_count < max_retries:
                try:
                    params = {"group_id": int(group_id)} if group_id else {"user_id": int(user_id)}
                    if latest_seq:
                        params["self_id"] = int(user_id) if user_id else 0

                    result = await bot.call_action("get_group_msg_history", **params)
                    if not result or not isinstance(result, dict):
                        break

                    messages = result.get("messages", [])
                    if not messages:
                        break

                    for msg in messages:
                        sender_id = str(msg.get("sender", {}).get("user_id", ""))
                        if sender_id == str(user_id) or not user_id:
                            all_messages.append(msg)

                    if len(messages) < 50:
                        break

                    latest_seq = messages[0].get("seq", None) if messages else None
                    if not latest_seq:
                        break

                except Exception as e:
                    logger.debug(f"[NapCat] 获取消息失败: {e}")
                    retry_count += 1
                    await asyncio.sleep(0.5)

            all_messages.sort(key=lambda m: m.get("time", 0), reverse=True)
            return all_messages[:msg_count]

        except Exception as e:
            logger.warning(f"[Memory] _fetch_scope_messages failed: {e}")
            return []

    def _format_scope_messages(self, messages: list[dict]) -> str:
        """将消息列表格式化为文本"""
        lines = []
        for msg in messages:
            try:
                sender = msg.get("sender_nickname", msg.get("sender", {}).get("nickname", "未知"))
                time_str = datetime.fromtimestamp(msg.get("time", 0)).strftime("%H:%M")
                text_parts = []
                for seg in msg.get("message", []):
                    if isinstance(seg, dict):
                        if seg.get("type") == "text":
                            text_parts.append(seg.get("data", {}).get("text", ""))
                text = "".join(text_parts).strip()
                if text:
                    lines.append(f"[{time_str}] {sender}: {text}")
            except Exception:
                pass
        return "\n".join(lines)

    def _split_messages_for_summary(self, messages: list[dict], summary_date: str) -> list[dict]:
        """将消息分块用于总结"""
        chunks = []
        current_chunk = []
        current_char_count = 0

        for msg in messages:
            msg_text = self._format_single_message(msg)
            msg_len = len(msg_text)

            if current_char_count + msg_len > SUMMARY_CHUNK_CHAR_LIMIT and current_chunk:
                chunks.append(
                    {
                        "index": len(chunks) + 1,
                        "total": len(chunks) + 1,
                        "date": summary_date,
                        "messages": "\n".join(current_chunk),
                    }
                )
                current_chunk = []
                current_char_count = 0

            current_chunk.append(msg_text)
            current_char_count += msg_len

        if current_chunk:
            chunks.append(
                {
                    "index": len(chunks) + 1,
                    "total": len(chunks),
                    "date": summary_date,
                    "messages": "\n".join(current_chunk),
                }
            )

        for i, chunk in enumerate(chunks):
            chunk["total"] = len(chunks)

        return chunks

    def _format_single_message(self, msg: dict) -> str:
        sender = msg.get("sender_nickname", msg.get("sender", {}).get("nickname", "未知"))
        time_str = datetime.fromtimestamp(msg.get("time", 0)).strftime("%H:%M")
        text_parts = []
        for seg in msg.get("message", []):
            if isinstance(seg, dict) and seg.get("type") == "text":
                text_parts.append(seg.get("data", {}).get("text", ""))
        text = "".join(text_parts).strip()
        return f"[{time_str}] {sender}: {text}" if text else ""

    async def _request_summary(self, prompt: str, umo: str) -> str:
        """调用 LLM 生成总结"""
        try:
            llm_provider = self.plugin.context.get_using_provider(umo=umo)
            res = await llm_provider.text_chat(prompt=prompt, contexts=[])
            return res.completion_text.strip() if hasattr(res, "completion_text") else str(res).strip()
        except Exception as e:
            logger.warning(f"[Memory] _request_summary failed: {e}")
            return ""

    async def _summarize_scope(self, scope_id: str, reference_dt: datetime | None = None) -> str:
        """对指定 scope 执行每日总结"""
        try:
            now = reference_dt or datetime.now()
            end_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start_dt = end_dt - timedelta(days=1)
            summary_date = start_dt.strftime("%Y-%m-%d")

            messages = await self._fetch_scope_messages(scope_id, msg_count=500)
            if not messages:
                return ""

            formatted = self._format_scope_messages(messages)
            if not formatted.strip():
                return ""

            chunks = self._split_messages_for_summary(messages, summary_date)

            if len(chunks) <= 1:
                prompt = SESSION_MEMORY_PROMPT.format(
                    summary_date=summary_date,
                    messages=formatted,
                )
                return await self._request_summary(prompt, umo="")

            partial_results = []
            for chunk in chunks:
                prompt = PARTIAL_MEMORY_PROMPT.format(
                    summary_date=chunk["date"],
                    index=chunk["index"],
                    total=chunk["total"],
                    messages=chunk["messages"],
                )
                result = await self._request_summary(prompt, umo="")
                if result:
                    try:
                        partial_results.append(json.loads(result))
                    except Exception:
                        pass

            if not partial_results:
                prompt = SESSION_MEMORY_PROMPT.format(
                    summary_date=summary_date,
                    messages=formatted[:SUMMARY_CHUNK_CHAR_LIMIT],
                )
                return await self._request_summary(prompt, umo="")

            merged_overview = " ".join([p.get("overview", "") for p in partial_results])
            merged_facts = []
            for p in partial_results:
                merged_facts.extend(p.get("key_facts", []))
            merged_entities = []
            for p in partial_results:
                merged_entities.extend(p.get("key_entities", []))
            merged_tags = []
            for p in partial_results:
                merged_tags.extend(p.get("tags", []))

            merged = {
                "overview": merged_overview[:500],
                "key_facts": list(dict.fromkeys(merged_facts))[:8],
                "key_entities": list(dict.fromkeys(merged_entities))[:10],
                "tags": list(dict.fromkeys(merged_tags))[:5],
            }

            merge_prompt = MERGE_MEMORY_PROMPT.format(
                summary_date=summary_date,
                partials=json.dumps(merged, ensure_ascii=False),
            )
            final_result = await self._request_summary(merge_prompt, umo="")
            if final_result:
                try:
                    parsed = json.loads(final_result)
                    return json.dumps(parsed, ensure_ascii=False)
                except Exception:
                    return final_result

            return json.dumps(merged, ensure_ascii=False)

        except Exception as e:
            logger.warning(f"[Memory] _summarize_scope failed: {e}")
            return ""

    async def daily_summary(self, reference_dt: datetime | None = None) -> dict:
        """执行每日总结主流程"""
        result = {
            "success_scopes": [],
            "failed_scopes": [],
            "skipped_scopes": [],
        }

        private_scopes = []
        if hasattr(self.plugin.dao, "list_known_scopes"):
            try:
                private_scopes = await self.plugin.dao.list_known_scopes(scope_type="private")
            except Exception:
                pass

        all_scopes = list(private_scopes)

        try:
            if self.plugin.context.platform_manager.platform_insts:
                platform = self.plugin.context.platform_manager.platform_insts[0]
                if hasattr(platform, "get_client"):
                    bot = platform.get_client()
                    if bot:
                        try:
                            group_list_result = await bot.call_action("get_group_list")
                            if group_list_result and isinstance(group_list_result, list):
                                for group in group_list_result:
                                    group_id = str(group.get("group_id", ""))
                                    if group_id:
                                        all_scopes.append(group_id)
                        except Exception:
                            pass
        except Exception:
            pass

        all_scopes = list(dict.fromkeys(all_scopes))

        for scope_id in all_scopes:
            try:
                logger.debug(f"[Memory] 正在总结 scope={scope_id}")
                memory = await self._summarize_scope(scope_id, reference_dt)
                if not memory:
                    result["skipped_scopes"].append(scope_id)
                    continue

                now = reference_dt or datetime.now()
                end_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
                start_dt = end_dt - timedelta(days=1)
                summary_date = start_dt.strftime("%Y-%m-%d")

                save_result = await self.store.save_daily_summary(scope_id, memory, summary_date)
                if "失败" in save_result or "不可用" in save_result:
                    result["failed_scopes"].append(scope_id)
                else:
                    result["success_scopes"].append(scope_id)

                await asyncio.sleep(0.5)

            except Exception as e:
                logger.warning(f"[Memory] scope={scope_id} 总结失败: {e}")
                result["failed_scopes"].append(scope_id)

        return result
