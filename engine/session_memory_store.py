import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger("astrbot")

PRIVATE_SCOPE_PREFIX = "private_"


class SessionMemoryStore:
    def __init__(self, plugin):
        self.plugin = plugin

    def _is_private_scope(self, scope_id: str) -> bool:
        return scope_id.startswith(PRIVATE_SCOPE_PREFIX)

    def _get_private_scope_user_id(self, scope_id: str) -> str:
        if self._is_private_scope(scope_id):
            return scope_id[len(PRIVATE_SCOPE_PREFIX) :]
        return ""

    def _get_scope_kb_name(self, scope_id: str) -> str:
        memory_kb_name = getattr(self.plugin.cfg, "memory_kb_name", "self_evolution_memory")
        if self._is_private_scope(scope_id):
            return f"{memory_kb_name}__scope__p_{self._get_private_scope_user_id(scope_id)}"
        return f"{memory_kb_name}__scope__g_{scope_id}"

    async def _ensure_scope_kb(self, scope_id: str):
        """确保 scope 对应的知识库存在并绑定"""
        try:
            kb_manager = getattr(self.plugin.context, "kb_manager", None)
            if not kb_manager:
                return None

            scope_kb_name = self._get_scope_kb_name(scope_id)

            try:
                kb_helper = await asyncio.wait_for(kb_manager.get_kb_by_name(scope_kb_name), timeout=5.0)
                if kb_helper:
                    return kb_helper
            except Exception:
                pass

            umo = None
            try:
                platform = self.plugin.context.platform_manager.platform_insts[0]
                bot = platform.bot
                login_info = await bot.call_action("get_login_info")
                umo = str(login_info.get("user_id", ""))
            except Exception:
                pass

            try:
                await kb_manager.create_kb_if_not_exists(
                    kb_name=scope_kb_name,
                    kb_description=f"会话记忆 scope={scope_id}",
                    umo=umo,
                )
                kb_helper = await asyncio.wait_for(kb_manager.get_kb_by_name(scope_kb_name), timeout=5.0)
                return kb_helper
            except Exception as e:
                logger.warning(f"[Memory] 创建知识库失败: {e}")
                return None

        except Exception as e:
            logger.warning(f"[Memory] _ensure_scope_kb 出错: {e}")
            return None

    async def sync_scope_kb_binding(self, scope_id: str, umo: str | None):
        """同步 scope 与知识库的绑定关系"""
        try:
            kb_manager = getattr(self.plugin.context, "kb_manager", None)
            if not kb_manager:
                return

            scope_kb_name = self._get_scope_kb_name(scope_id)

            try:
                kb_helper = await asyncio.wait_for(kb_manager.get_kb_by_name(scope_kb_name), timeout=5.0)
                if kb_helper:
                    return
            except Exception:
                pass

            try:
                await kb_manager.create_kb_if_not_exists(
                    kb_name=scope_kb_name,
                    kb_description=f"会话记忆 scope={scope_id}",
                    umo=umo,
                )
            except Exception as e:
                logger.debug(f"[Memory] sync_scope_kb_binding: {e}")

        except Exception as e:
            logger.debug(f"[Memory] sync_scope_kb_binding 出错: {e}")

    async def save_daily_summary(
        self,
        scope_id: str,
        memory: str,
        summary_date: str,
    ) -> str:
        """保存每日总结到知识库"""
        try:
            kb_helper = await asyncio.wait_for(self._ensure_scope_kb(scope_id), timeout=10.0)
            if not kb_helper:
                return f"知识库不可用，无法保存总结"

            file_name = f"summary_{scope_id}_{summary_date}_{int(time.time() * 1000)}.txt"

            scope_label = (
                f"用户ID: {self._get_private_scope_user_id(scope_id)}"
                if self._is_private_scope(scope_id)
                else f"群号: {scope_id}"
            )

            content = f"【每日会话总结】\n日期: {summary_date}\n范围: {scope_label}\n---\n{memory}"

            await kb_helper.upload_document(
                file_name=file_name,
                file_content=b"",
                file_type="txt",
                pre_chunked_text=[content],
            )
            logger.debug(f"[Memory] 总结已保存: scope={scope_id}, date={summary_date}")
            return f"总结已保存: {summary_date}"

        except Exception as e:
            logger.warning(f"[Memory] 保存总结失败: {e}")
            return f"保存总结失败: {e}"

    async def save_session_event(
        self,
        scope_id: str,
        session_event: dict,
    ) -> bool:
        """保存 session_event 到知识库"""
        try:
            kb_helper = await asyncio.wait_for(self._ensure_scope_kb(scope_id), timeout=10.0)
            if not kb_helper:
                logger.warning(f"[Memory] 会话 {scope_id} 的隔离知识库不可用")
                return False

            date = session_event.get("date", datetime.now().strftime("%Y-%m-%d"))
            file_prefix = f"event_{scope_id}_{date}_"

            scope_label = (
                f"用户ID: {self._get_private_scope_user_id(scope_id)}"
                if self._is_private_scope(scope_id)
                else f"群号: {scope_id}"
            )

            content = session_event.get("content", "")
            chunks = [
                f"【会话事件】\n"
                f"类型: session_event\n"
                f"范围ID: {scope_id}\n"
                f"{scope_label}\n"
                f"日期: {date}\n"
                f"来源: {session_event.get('source', 'unknown')}\n"
                f"内容: {content}",
            ]

            await kb_helper.upload_document(
                file_name=f"{file_prefix}{int(time.time() * 1000)}.txt",
                file_content=b"",
                file_type="txt",
                pre_chunked_text=chunks,
            )
            return True

        except Exception as e:
            logger.warning(f"[Memory] save_session_event failed: {e}")
            return False

    async def get_summary_by_date(self, scope_id: str, summary_date: str) -> str:
        """按日期精确获取某天的会话总结"""
        from datetime import datetime, timedelta

        try:
            resolved_date = summary_date.strip().lower()
            if resolved_date == "today":
                resolved_date = datetime.now().strftime("%Y-%m-%d")
            elif resolved_date == "yesterday":
                resolved_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                try:
                    datetime.strptime(resolved_date, "%Y-%m-%d")
                except ValueError:
                    return ""

            kb_manager = getattr(self.plugin.context, "kb_manager", None)
            if not kb_manager:
                return ""

            scope_kb_name = self._get_scope_kb_name(scope_id)

            try:
                kb_helper = await asyncio.wait_for(kb_manager.get_kb_by_name(scope_kb_name), timeout=5.0)
            except Exception:
                return ""

            if not kb_helper:
                return ""

            try:
                if hasattr(kb_helper, "list_documents"):
                    docs = await kb_helper.list_documents()
                else:
                    return ""
            except Exception:
                return ""

            target_prefix = f"summary_{scope_id}_{resolved_date}_"
            matching = [d for d in docs if isinstance(d, str) and d.startswith(target_prefix)]

            if not matching:
                return ""

            try:
                doc_content = await kb_helper.get_document(matching[0])
                if isinstance(doc_content, dict):
                    return doc_content.get("content", "")
                return str(doc_content)
            except Exception:
                return ""

        except Exception as e:
            logger.warning(f"[Memory] get_summary_by_date failed: {e}")
            return ""

    async def retrieve_events(
        self,
        scope_id: str,
        query: str,
        max_results: int = 3,
    ) -> list[str]:
        """检索 session_event 类型的记忆"""
        try:
            kb_manager = getattr(self.plugin.context, "kb_manager", None)
            if not kb_manager:
                return []

            scope_kb_name = self._get_scope_kb_name(scope_id)

            try:
                kb_helper = await asyncio.wait_for(kb_manager.get_kb_by_name(scope_kb_name), timeout=5.0)
            except Exception:
                return []

            if not kb_helper:
                return []

            try:
                results = await asyncio.wait_for(
                    kb_manager.retrieve(
                        query=query,
                        kb_names=[scope_kb_name],
                        top_m_final=max_results,
                    ),
                    timeout=5.0,
                )
            except Exception:
                if hasattr(kb_helper, "retrieve"):
                    results = await asyncio.wait_for(
                        kb_helper.retrieve(query=query, top_k=max_results),
                        timeout=5.0,
                    )
                else:
                    return []

            if not results:
                return []

            events = []
            for r in results:
                content = ""
                if isinstance(r, dict):
                    content = r.get("content", "") or r.get("text", "")
                elif isinstance(r, str):
                    content = r
                if content and "session_event" in content.lower():
                    events.append(content)

            return events[:max_results]

        except Exception as e:
            logger.warning(f"[Memory] retrieve_events failed: {e}")
            return []

    async def retrieve_summary(
        self,
        scope_id: str,
        query: str,
        max_results: int = 3,
    ) -> str:
        """检索总结类记忆"""
        try:
            kb_manager = getattr(self.plugin.context, "kb_manager", None)
            if not kb_manager:
                return ""

            scope_kb_name = self._get_scope_kb_name(scope_id)

            try:
                kb_helper = await asyncio.wait_for(kb_manager.get_kb_by_name(scope_kb_name), timeout=5.0)
            except Exception:
                return ""

            if not kb_helper:
                return ""

            try:
                results = await asyncio.wait_for(
                    kb_manager.retrieve(
                        query=query,
                        kb_names=[scope_kb_name],
                        top_m_final=max_results,
                    ),
                    timeout=5.0,
                )
            except Exception:
                if hasattr(kb_helper, "retrieve"):
                    results = await asyncio.wait_for(
                        kb_helper.retrieve(query=query, top_k=max_results),
                        timeout=5.0,
                    )
                else:
                    return ""

            if not results:
                return ""

            parts = []
            for r in results:
                content = ""
                if isinstance(r, dict):
                    content = r.get("content", "") or r.get("text", "")
                elif isinstance(r, str):
                    content = r
                if content:
                    parts.append(content)

            return "\n\n".join(parts)

        except Exception as e:
            logger.warning(f"[Memory] retrieve_summary failed: {e}")
            return ""

    async def clear_summary(self, scope_id: str, confirm: bool = False) -> str:
        """清空指定 scope 的所有总结"""
        if not confirm:
            return "操作已取消"

        try:
            kb_manager = getattr(self.plugin.context, "kb_manager", None)
            if not kb_manager:
                return "知识库管理器不可用"

            scope_kb_name = self._get_scope_kb_name(scope_id)

            try:
                kb_helper = await asyncio.wait_for(kb_manager.get_kb_by_name(scope_kb_name), timeout=5.0)
            except Exception:
                return "知识库不存在"

            if not kb_helper:
                return "知识库不存在"

            if hasattr(kb_helper, "delete_all_documents"):
                await kb_helper.delete_all_documents()
                return f"已清空 scope={scope_id} 的所有总结"
            elif hasattr(kb_helper, "list_documents"):
                docs = await kb_helper.list_documents()
                deleted = 0
                for doc in docs:
                    if isinstance(doc, str) and doc.startswith(f"summary_{scope_id}_"):
                        try:
                            await kb_helper.delete_document(doc)
                            deleted += 1
                        except Exception:
                            pass
                return f"已删除 {deleted} 份总结"
            else:
                return "知识库不支持清空操作"

        except Exception as e:
            logger.warning(f"[Memory] clear_summary failed: {e}")
            return f"清空失败: {e}"
