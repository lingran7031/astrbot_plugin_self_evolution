from typing import Optional

from astrbot.api import logger

from .memory_types import MemoryQueryIntent, MemoryQueryRequest, MemoryQueryResult


class MemoryQueryService:
    def __init__(self, plugin):
        self.plugin = plugin

    async def query(self, request: MemoryQueryRequest) -> MemoryQueryResult:
        """统一查询入口，根据 intent 分派到具体 retrieval 策略"""
        if request.intent == MemoryQueryIntent.RECENT_CONTEXT:
            return await self._query_recent_context(request)
        elif request.intent == MemoryQueryIntent.DAILY_SUMMARY:
            return await self._query_daily_summary(request)
        elif request.intent == MemoryQueryIntent.SESSION_EVENT:
            return await self._query_session_event(request)
        elif request.intent == MemoryQueryIntent.USER_PROFILE:
            return await self._query_user_profile(request)
        elif request.intent == MemoryQueryIntent.USER_MESSAGE_HISTORY:
            return await self._query_user_message_history(request)
        elif request.intent == MemoryQueryIntent.FALLBACK_KB:
            return await self._query_fallback_kb(request)
        else:
            return MemoryQueryResult(
                intent=request.intent,
                text="",
                source="unknown",
                hit_count=0,
            )

    async def _query_recent_context(self, request: MemoryQueryRequest) -> MemoryQueryResult:
        """查询最近群上下文 - 走 NapCat 历史消息，不查 KB"""
        try:
            group_id = request.scope_id
            if not group_id or group_id.startswith("private_"):
                return MemoryQueryResult(
                    intent=request.intent,
                    text="",
                    source="recent_context",
                    hit_count=0,
                )

            from .context_injection import get_group_history

            messages = await get_group_history(
                group_id,
                self.plugin.context.platform_manager,
                count=10,
            )
            if not messages:
                return MemoryQueryResult(
                    intent=request.intent,
                    text="",
                    source="recent_context",
                    hit_count=0,
                )

            lines = []
            for msg in messages[-10:]:
                sender = msg.get("sender_nickname", "unknown")
                text = msg.get("text", "")
                if text:
                    lines.append(f"{sender}: {text}")

            text = "\n".join(lines) if lines else ""
            return MemoryQueryResult(
                intent=request.intent,
                text=text,
                source="recent_context",
                hit_count=len(lines),
            )
        except Exception as e:
            logger.warning(f"[MemoryQuery] RECENT_CONTEXT failed: {e}")
            return MemoryQueryResult(
                intent=request.intent,
                text="",
                source="recent_context",
                hit_count=0,
            )

    async def _query_daily_summary(self, request: MemoryQueryRequest) -> MemoryQueryResult:
        """查询某天总结 - 走 SessionMemoryStore.get_summary_by_date"""
        try:
            scope_id = request.scope_id
            date = request.date or "yesterday"

            if not hasattr(self.plugin, "memory"):
                return MemoryQueryResult(
                    intent=request.intent,
                    text="",
                    source="daily_summary",
                    hit_count=0,
                )

            summary = await self.plugin.memory.get_summary_by_date(scope_id, date)
            return MemoryQueryResult(
                intent=request.intent,
                text=summary,
                source="daily_summary",
                hit_count=1 if summary else 0,
            )
        except Exception as e:
            logger.warning(f"[MemoryQuery] DAILY_SUMMARY failed: {e}")
            return MemoryQueryResult(
                intent=request.intent,
                text="",
                source="daily_summary",
                hit_count=0,
            )

    async def _query_session_event(self, request: MemoryQueryRequest) -> MemoryQueryResult:
        """查询事件 - 走 SessionMemoryStore.retrieve_events"""
        try:
            scope_id = request.scope_id
            query = request.query
            limit = request.limit

            if not hasattr(self.plugin, "memory"):
                return MemoryQueryResult(
                    intent=request.intent,
                    text="",
                    source="session_event",
                    hit_count=0,
                )

            events = await self.plugin.memory.retrieve_events(scope_id, query, limit)
            if not events:
                return MemoryQueryResult(
                    intent=request.intent,
                    text="",
                    source="session_event",
                    hit_count=0,
                )

            lines = [f"- {e}" for e in events]
            text = "\n".join(lines)
            return MemoryQueryResult(
                intent=request.intent,
                text=text,
                source="session_event",
                hit_count=len(events),
            )
        except Exception as e:
            logger.warning(f"[MemoryQuery] SESSION_EVENT failed: {e}")
            return MemoryQueryResult(
                intent=request.intent,
                text="",
                source="session_event",
                hit_count=0,
            )

    async def _query_user_profile(self, request: MemoryQueryRequest) -> MemoryQueryResult:
        """查询用户画像 - 走 ProfileSummaryService.get_structured_summary"""
        try:
            scope_id = request.scope_id
            user_id = request.user_id

            if not hasattr(self.plugin, "profile"):
                return MemoryQueryResult(
                    intent=request.intent,
                    text="",
                    source="user_profile",
                    hit_count=0,
                )

            summary = await self.plugin.profile.get_structured_summary(scope_id, user_id, max_items=8)
            return MemoryQueryResult(
                intent=request.intent,
                text=summary,
                source="user_profile",
                hit_count=1 if summary else 0,
            )
        except Exception as e:
            logger.warning(f"[MemoryQuery] USER_PROFILE failed: {e}")
            return MemoryQueryResult(
                intent=request.intent,
                text="",
                source="user_profile",
                hit_count=0,
            )

    async def _query_user_message_history(self, request: MemoryQueryRequest) -> MemoryQueryResult:
        """查询用户历史消息 - 走 NapCat 单用户消息抓取"""
        try:
            user_id = request.user_id
            scope_id = request.scope_id
            limit = request.limit

            if not hasattr(self.plugin, "get_user_messages_for_tool"):
                return MemoryQueryResult(
                    intent=request.intent,
                    text="",
                    source="user_message_history",
                    hit_count=0,
                )

            messages = await self.plugin.get_user_messages_for_tool(
                user_id=user_id,
                group_id=scope_id,
                fetch_limit=limit,
            )
            if not messages:
                return MemoryQueryResult(
                    intent=request.intent,
                    text="",
                    source="user_message_history",
                    hit_count=0,
                )

            lines = [f"- {m.get('text', '')}" for m in messages if m.get("text")]
            text = "\n".join(lines)
            return MemoryQueryResult(
                intent=request.intent,
                text=text,
                source="user_message_history",
                hit_count=len(messages),
            )
        except Exception as e:
            logger.warning(f"[MemoryQuery] USER_MESSAGE_HISTORY failed: {e}")
            return MemoryQueryResult(
                intent=request.intent,
                text="",
                source="user_message_history",
                hit_count=0,
            )

    async def _query_fallback_kb(self, request: MemoryQueryRequest) -> MemoryQueryResult:
        """兜底 KB 检索 - 走通用 smart_retrieve"""
        try:
            scope_id = request.scope_id
            query = request.query
            max_results = request.limit

            if not hasattr(self.plugin, "memory"):
                return MemoryQueryResult(
                    intent=request.intent,
                    text="",
                    source="fallback_kb",
                    hit_count=0,
                )

            text = await self.plugin.memory.smart_retrieve(scope_id, query, max_results)
            return MemoryQueryResult(
                intent=request.intent,
                text=text,
                source="fallback_kb",
                hit_count=1 if text else 0,
            )
        except Exception as e:
            logger.warning(f"[MemoryQuery] FALLBACK_KB failed: {e}")
            return MemoryQueryResult(
                intent=request.intent,
                text="",
                source="fallback_kb",
                hit_count=0,
            )
