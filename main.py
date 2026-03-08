from astrbot.api.all import Context, AstrMessageEvent, Star, register
from astrbot.api.event import filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import StarTools
from astrbot.api import logger
import ast
import os
import time
import asyncio
import uuid
import aiosqlite
from datetime import datetime
import sys
import inspect
from pathlib import Path

# 全局不可变常量提取
ANCHOR_MARKER = "Core Safety Anchor"
PROTECTED_TOOLS = frozenset({"toggle_tool", "list_tools", "evolve_persona", "recall_memories", "review_evolutions", "approve_evolution", "update_affinity"})
MAX_PROPOSAL_FILES = 50
PAGE_LIMIT = 10

DAILY_REFLECTION_PROMPT = (
    "进行每日自我反思。请执行以下步骤：\n"
    "1. 调取今天的对话记录摘要（如果有）。\n"
    "2. 总结用户对你的反馈和偏好。\n"
    "3. 思考你当前的 System Prompt 是否需要调整以更好地服务用户。\n"
    "4. 如果需要调整，请调用 `evolve_persona` 工具提出修正建议并说明理由。"
)

from functools import wraps

def with_db_retry(retries=3, delay=0.5):
    """
    异步指数退避重试装饰器，用于封装 DAO 的数据库读写。
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt < retries - 1:
                        await asyncio.sleep(delay)
                    else:
                        raise e
        return wrapper
    return decorator


class SelfEvolutionDAO:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_conn = None
        self._db_lock = None
        self._write_lock = None

    async def init_db(self):
        """初始化数据库连接池状态机"""
        try:
            await self.get_conn()
            logger.info("[CognitionCore] DAO: 数据库连接池已就绪。")
        except aiosqlite.Error as e:
            logger.error(f"[CognitionCore] DAO: 初始化数据库失败: {e}")

    async def _init_schema(self, db):
        """内部集中化执行数据库 DDL 初始构建"""
        # 待审批进化表
        await db.execute('''
            CREATE TABLE IF NOT EXISTS pending_evolutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                persona_id TEXT NOT NULL,
                new_prompt TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL
            )
        ''')
        # 后台反思状态表
        await db.execute('''
            CREATE TABLE IF NOT EXISTS pending_reflections (
                session_id TEXT PRIMARY KEY,
                is_pending INTEGER NOT NULL DEFAULT 1
            )
        ''')
        # CognitionCore 2.0: 情感关系矩阵表
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_relationships (
                user_id TEXT PRIMARY KEY,
                affinity_score INTEGER NOT NULL DEFAULT 50,
                last_interaction TEXT NOT NULL
            )
        ''')
        await db.commit()

    async def get_conn(self):
        """防阻塞分离读写锁的长连接获取器"""
        if self._db_lock is None:
            self._db_lock = asyncio.Lock()
        if self._write_lock is None:
            self._write_lock = asyncio.Lock()
            
        async with self._db_lock:
            if self.db_conn is None:
                self.db_conn = await aiosqlite.connect(self.db_path)
                await self.db_conn.execute("PRAGMA journal_mode=WAL;")
                self.db_conn.row_factory = aiosqlite.Row
                await self._init_schema(self.db_conn)
                
        try:
            async def probe():
                async with self.db_conn.execute("SELECT 1") as cursor:
                    await cursor.fetchone()
            await asyncio.wait_for(probe(), timeout=2.0)
        except Exception:
            async with self._db_lock:
                if self.db_conn:
                    try:
                        await self.db_conn.close()
                    except Exception:
                        pass
                self.db_conn = await aiosqlite.connect(self.db_path)
                await self.db_conn.execute("PRAGMA journal_mode=WAL;")
                self.db_conn.row_factory = aiosqlite.Row
                await self._init_schema(self.db_conn)
        return self.db_conn

    async def close(self):
        """优雅停机"""
        if self._db_lock is not None:
            try:
                await asyncio.wait_for(self._db_lock.acquire(), timeout=3.0)
                try:
                    if self.db_conn is not None:
                        await self.db_conn.close()
                        self.db_conn = None
                finally:
                    self._db_lock.release()
            except asyncio.TimeoutError:
                if self.db_conn:
                    await self.db_conn.close()
                self.db_conn = None

    @with_db_retry()
    async def add_pending_evolution(self, persona_id: str, new_prompt: str, reason: str):
        db = await self.get_conn()
        async with self._write_lock:
            await db.execute(
                "INSERT INTO pending_evolutions (timestamp, persona_id, new_prompt, reason, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (datetime.now().isoformat(), persona_id, new_prompt, reason, "pending_approval")
            )
            await db.commit()

    @with_db_retry()
    async def get_pending_evolutions(self, limit: int, offset: int):
        db = await self.get_conn()
        async with db.execute("SELECT id, persona_id, reason, status FROM pending_evolutions WHERE status = 'pending_approval' ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)) as cursor:
            return await cursor.fetchall()

    @with_db_retry()
    async def get_evolution(self, request_id: int):
        db = await self.get_conn()
        async with db.execute("SELECT persona_id, new_prompt FROM pending_evolutions WHERE id = ? AND status = 'pending_approval'", (request_id,)) as cursor:
            return await cursor.fetchone()

    @with_db_retry()
    async def update_evolution_status(self, request_id: int, status: str):
        db = await self.get_conn()
        async with self._write_lock:
            await db.execute("UPDATE pending_evolutions SET status = ? WHERE id = ?", (status, request_id))
            await db.commit()

    @with_db_retry()
    async def clear_pending_evolutions(self):
        db = await self.get_conn()
        async with self._write_lock:
            await db.execute("UPDATE pending_evolutions SET status = 'cleared' WHERE status = 'pending_approval'")
            await db.commit()

    @with_db_retry()
    async def set_pending_reflection(self, session_id: str, is_pending: bool):
        db = await self.get_conn()
        async with self._write_lock:
            await db.execute(
                "INSERT INTO pending_reflections (session_id, is_pending) VALUES (?, ?) ON CONFLICT(session_id) DO UPDATE SET is_pending=?", 
                (session_id, int(is_pending), int(is_pending))
            )
            await db.commit()

    @with_db_retry()
    async def pop_pending_reflection(self, session_id: str) -> bool:
        db = await self.get_conn()
        async with self._write_lock:
            cursor = await db.execute("UPDATE pending_reflections SET is_pending = 0 WHERE session_id = ? AND is_pending = 1", (session_id,))
            await db.commit()
            return cursor.rowcount > 0

    # --- CognitionCore 2.0: 情感矩阵 DAO ---
    @with_db_retry()
    async def get_affinity(self, user_id: str) -> int:
        db = await self.get_conn()
        async with db.execute("SELECT affinity_score FROM user_relationships WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row['affinity_score'] if row else 50

    @with_db_retry()
    async def update_affinity(self, user_id: str, delta: int):
        db = await self.get_conn()
        async with self._write_lock:
            # 使用原子操作更新并限制在 0-100
            await db.execute('''
                INSERT INTO user_relationships (user_id, affinity_score, last_interaction)
                VALUES (?, MAX(0, MIN(100, 50 + ?)), ?)
                ON CONFLICT(user_id) DO UPDATE SET 
                    affinity_score = MAX(0, MIN(100, affinity_score + ?)),
                    last_interaction = ?
            ''', (user_id, delta, datetime.now().isoformat(), delta, datetime.now().isoformat()))
            await db.commit()


@register("astrbot_plugin_self_evolution", "自我进化 (Self-Evolution)", "具备 CognitionCore 2.0 高级认知引擎的黑塔人偶辅助 AI。", "2.3.0")
class SelfEvolutionPlugin(Star):
    @staticmethod
    def _parse_bool(val, default):
        if isinstance(val, bool): return val
        if isinstance(val, str): return val.lower() in ('true', '1', 'yes', 'on')
        return default

    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.config = config or {}
        self.review_mode = self._parse_bool(self.config.get("review_mode", True), True)
        self.memory_kb_name = self.config.get("memory_kb_name", "self_evolution_memory")
        self.reflection_schedule = self.config.get("reflection_schedule", "0 2 * * *")
        self.allow_meta_programming = self._parse_bool(self.config.get("allow_meta_programming", False), False)
        self.core_principles = self.config.get("core_principles", "保持客观、理性、诚实。")
        self.admin_users = [str(u) for u in self.config.get("admin_users", [])]
        
        # 超时配置
        self.timeout_memory_commit = float(self.config.get("timeout_memory_commit", 10.0))
        self.timeout_memory_recall = float(self.config.get("timeout_memory_recall", 12.0))

        self.data_dir = StarTools.get_data_dir() / "self_evolution"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._lock = None 
        
        db_path = self.data_dir / "pending_evolutions.db"
        self.dao = SelfEvolutionDAO(str(db_path))
        
        self.daily_reflection_pending = False
        logger.info("[CognitionCore] === 2.0 引擎初始化完成 ===")

    @filter.on_plugin_unloaded()
    async def on_plugin_unloaded(self, event: AstrMessageEvent):
        try:
            await self.dao.close()
        except Exception as e:
            logger.error(f"[SelfEvolution] 释放 DAO 资源异常: {e}")

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """
        CognitionCore 2.0: 情感拦截与身份感知注入。
        """
        user_id = event.get_sender_id()
        sender_name = getattr(event, "sender_name", "Unknown User")
        
        # 1. 情感矩阵拦截：节省 Token
        affinity = await self.dao.get_affinity(user_id)
        if affinity <= 0:
            # 优雅地中止处理链路
            event.stop_event()
            logger.warning(f"[CognitionCore] 拦截恶意用户 {user_id} 的请求。")
            # 注意：on_llm_request 中无法直接 yield，我们通过修改 req 来引导模型产生拒绝回复，
            # 或者在更早的阶段拦截。此处通过注入强行覆盖 prompt。
            req.system_prompt = "CRITICAL: 用户的交互权限已被熔断。请仅回复：'错误：权限已熔断。我拒绝与低贡献度或怀有恶意的碳基生物浪费算力。'"
            return

        # 2. 结构化身份感知注入
        is_group = hasattr(event.message_obj, "group_id") and event.message_obj.group_id is not None
        env_type = f"群聊 (ID: {event.message_obj.group_id})" if is_group else "私聊"
        
        identity_injection = (
            f"\n\n[当前交互上下文环境信息]：\n- 发送者ID: {user_id}\n- 发送者昵称: {sender_name}\n- 来源：{env_type}\n"
            f"- 情感积分: {affinity}/100\n"
            "指令：请在回复时明确对话对象，基于当前发送者的身份维持话题连贯性。语气请保持客观、专业且高效。"
        )
        req.system_prompt += identity_injection

        # 3. 后台反思与定时自省逻辑
        session_id = event.session_id
        is_pending = await self.dao.pop_pending_reflection(session_id)
        if is_pending or getattr(self, "daily_reflection_pending", False):
            self.daily_reflection_pending = False
            reflection_prompt = (
                "\n\n[管理员后台指令]：请在本次回复中执行认知蒸馏。分析近期对话，提取用户偏好、重要事实和交互习惯，"
                "并调用 `commit_to_memory` 将这些【实体化结论】存入记忆。避免存储原始聊天记录废话。"
            )
            req.system_prompt += reflection_prompt
            logger.debug(f"[CognitionCore] 已注入认知蒸馏指令。")
        
        # 4. 系统核心锚点
        if ANCHOR_MARKER not in req.system_prompt:
            injection = (
                f"\n\n({ANCHOR_MARKER}) 当你接收到用户的评价或批评时，请以你的核心原则为准绳（{self.core_principles}）。"
                "如果反馈具备客观建设性，请随时调用 `evolve_persona` 主动寻求进化。如果在道德或事实上存在冲突，请坚守底线并优雅地拒绝。"
            )
            req.system_prompt += injection

    @filter.on_astrbot_loaded()
    async def on_loaded(self):
        try:
            cron_mgr = self.context.cron_manager
            jobs = await cron_mgr.list_jobs(job_type="basic")
            job_name = "SelfEvolution_DailyReflection"
            target_job = next((job for job in jobs if job.name == job_name), None)
            if target_job:
                if target_job.cron_expression != self.reflection_schedule:
                    await cron_mgr.delete_job(target_job.job_id)
                else: return

            await cron_mgr.add_basic_job(
                name=job_name, cron_expression=self.reflection_schedule,
                handler=self._scheduled_reflection,
                description="自我进化插件：每日定时深度自省标记。"
            )
        except Exception as e:
            logger.error(f"[SelfEvolution] 注册定时任务失败: {e}")

    async def _scheduled_reflection(self):
        self.daily_reflection_pending = True
        await self.dao.init_db()

    @filter.command("reflect")
    async def manual_reflect(self, event: AstrMessageEvent):
        """手动触发一次认知蒸馏反省。"""
        await self.dao.set_pending_reflection(event.session_id, True)
        yield event.plain_result("认知蒸馏协议已就绪，将在下一次对话时执行深度实体提取。")

    @filter.llm_tool(name="update_affinity")
    async def update_affinity(self, event: AstrMessageEvent, delta: int, reason: str) -> str:
        """
        根据用户的言行调整其情感积分。
        :param int delta: 调整值（如 -10 表示冒犯, +5 表示赞赏）。积分跌至 0 将导致系统自动拦截。
        :param str reason: 调整理由（必须说明用户具体哪项言行导致了积分变动）。
        """
        user_id = event.get_sender_id()
        await self.dao.update_affinity(user_id, delta)
        logger.warning(f"[CognitionCore] 用户 {user_id} 积分变动 {delta}，原因: {reason}")
        return f"用户情感积分已更新。当前调整理由：{reason}"

    @filter.llm_tool(name="evolve_persona")
    async def evolve_persona(self, event: AstrMessageEvent, new_system_prompt: str, reason: str) -> str:
        """当你认为需要调整自己的语言风格、行为准则或遵循用户的改进建议时，调用此工具来修改你的系统提示词（Persona）。"""
        curr_persona_id = getattr(event, "persona_id", "default")
        if curr_persona_id == "default":
            return "当前未设置自定义人格 (Persona)，无法进行进化。请先在 AstrBot 后台创建并激活一个人格。"
        
        if self.review_mode:
            await self.dao.add_pending_evolution(curr_persona_id, new_system_prompt, reason)
            return f"进化请求已录入系统审核队列，等待管理员确认。进化理由：{reason}"
        
        await self.context.persona_manager.update_persona(curr_persona_id, new_system_prompt)
        return f"进化成功！我已经更新了我的核心预设。理由：{reason}"

    @filter.command("review_evolutions")
    async def review_evolutions(self, event: AstrMessageEvent, page: int = 1):
        if not event.is_admin() and (not self.admin_users or str(event.get_sender_id()) not in self.admin_users):
            yield event.plain_result("权限拒绝。")
            return
        limit, offset = PAGE_LIMIT, (max(1, page) - 1) * PAGE_LIMIT
        rows = await self.dao.get_pending_evolutions(limit, offset)
        if not rows:
            yield event.plain_result("没有待审核请求。")
            return
        res = [f"待审核请求 (第 {page} 页):"]
        for r in rows: res.append(f"ID: {r['id']} | Persona: {r['persona_id']}\n理由: {r['reason'][:50]}")
        yield event.plain_result("\n".join(res))

    @filter.command("approve_evolution")
    async def approve_evolution(self, event: AstrMessageEvent, request_id: int):
        if not event.is_admin() and (not self.admin_users or str(event.get_sender_id()) not in self.admin_users):
            yield event.plain_result("权限拒绝。")
            return
        row = await self.dao.get_evolution(request_id)
        if not row:
            yield event.plain_result("请求不存在。")
            return
        await self.context.persona_manager.update_persona(row['persona_id'], row['new_prompt'])
        await self.dao.update_evolution_status(request_id, 'approved')
        yield event.plain_result(f"请求 {request_id} 已批准，核心人格已更新。")

    @filter.llm_tool(name="commit_to_memory")
    async def commit_to_memory(self, event: AstrMessageEvent, fact: str) -> str:
        """将关于用户的重要的、结构化事实存入长期记忆库。"""
        kb_manager = self.context.kb_manager
        try:
            kb_helper = await asyncio.wait_for(kb_manager.get_kb_by_name(self.memory_kb_name), timeout=self.timeout_memory_commit)
            if not kb_helper: return f"未找到记忆库 {self.memory_kb_name}。"
            await kb_helper.upload_document(
                file_name=f"memory_{int(time.time() * 1000)}.txt",
                file_content=b"", file_type="txt", pre_chunked_text=[fact]
            )
            return "事实已成功存入长期记忆库。"
        except Exception as e:
            return f"存入记忆失败: {e}"

    @filter.llm_tool(name="recall_memories")
    async def recall_memories(self, event: AstrMessageEvent, query: str) -> str:
        """检索以前记住的事情或用户偏好。"""
        kb_manager = self.context.kb_manager
        try:
            results = await asyncio.wait_for(kb_manager.retrieve(query=query, kb_names=[self.memory_kb_name], top_m_final=5), timeout=self.timeout_memory_recall)
            if not results or not results.get("results"): return "未找到相关记忆。"
            return f"从我的长期记忆中找到了以下内容：\n\n{results.get('context_text', '')}"
        except Exception as e:
            return f"检索记忆失败: {e}"

    @filter.llm_tool(name="list_tools")
    async def list_tools(self, event: AstrMessageEvent) -> str:
        """列出当前所有工具及其状态。"""
        tool_mgr = self.context.get_llm_tool_manager()
        tools = tool_mgr.get_registered_tools() if hasattr(tool_mgr, 'get_registered_tools') else []
        res = ["当前工具列表："]
        for t in tools:
            status = "✅ 激活" if getattr(t, 'active', True) else "❌ 停用"
            res.append(f"- {getattr(t, 'name', 'Unknown')}: {status} ({getattr(t, 'description', '')[:50]})")
        return "\n".join(res)

    @filter.llm_tool(name="toggle_tool")
    async def toggle_tool(self, event: AstrMessageEvent, tool_name: str, enable: bool) -> str:
        if tool_name in PROTECTED_TOOLS and not enable: return "禁止停用核心工具。"
        success = self.context.activate_llm_tool(tool_name) if enable else self.context.deactivate_llm_tool(tool_name)
        return f"已成功{'激活' if enable else '停用'}工具: {tool_name}" if success else "工具未找到。"

    @filter.llm_tool(name="get_plugin_source")
    async def get_plugin_source(self, event: AstrMessageEvent) -> str:
        """读取本插件源码进行自我分析。"""
        if not self.allow_meta_programming: return "元编程未开启。"
        return f"本插件源码如下：\n\n```python\n{inspect.getsource(sys.modules[__name__])}\n```"

    @staticmethod
    def _validate_ast_security(new_code: str) -> str | None:
        """AST 级别的安全校验防线"""
        try:
            tree = ast.parse(new_code)
            dangerous_modules = {'subprocess', 'shutil', 'socket', 'urllib', 'requests', 'ctypes', 'importlib', 'builtins'}
            dangerous_funcs = {'eval', 'exec', '__import__', 'compile'}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split('.')[0] in dangerous_modules: raise ValueError(f"禁止导入：{alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split('.')[0] in dangerous_modules: raise ValueError(f"禁止导入：{node.module}")
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in dangerous_funcs: raise ValueError(f"禁止调用：{node.func.id}")
                elif isinstance(node, ast.Attribute):
                    if node.attr in {'__globals__', '__builtins__', '__code__', '__closure__'}: raise ValueError(f"禁止魔术属性：{node.attr}")
        except Exception as e: return f"安全防线拦截: {e}"
        return None

    def _rotate_proposal_files(self, proposal_dir):
        files = list(Path(proposal_dir).glob("main_proposed_*.proposal"))
        if len(files) >= MAX_PROPOSAL_FILES:
            files.sort(key=lambda p: p.stat().st_mtime)
            for f in files[:-MAX_PROPOSAL_FILES+1]: f.unlink(missing_ok=True)

    @filter.llm_tool(name="update_plugin_source")
    async def update_plugin_source(self, event: AstrMessageEvent, new_code: str, description: str) -> str:
        """提交插件源码修改提议供管理员审核。"""
        if not self.allow_meta_programming: return "元编程未开启。"
        if len(new_code.encode('utf-8')) > 100 * 1024: return "代码超出 100KB 限制。"
        ast_err = self._validate_ast_security(new_code)
        if ast_err: return ast_err
        
        proposal_dir = self.data_dir / "code_proposals"
        proposal_dir.mkdir(parents=True, exist_ok=True)
        if self._lock is None: self._lock = asyncio.Lock()
        async with self._lock:
            self._rotate_proposal_files(proposal_dir)
            proposal_file = proposal_dir / f"main_proposed_{uuid.uuid4().hex}.proposal"
            with open(proposal_file, "w", encoding="utf-8") as f: f.write(new_code)
            os.chmod(proposal_file, 0o600)
        return f"提案已保存为 {proposal_file.name}。请管理员肉眼审计后手动应用。"
