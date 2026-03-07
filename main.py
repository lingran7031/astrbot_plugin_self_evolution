from astrbot.api.all import *
from astrbot.api.event import filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import StarTools
import json
import os
import time
import ast
import shutil
import asyncio
from datetime import datetime
@register("astrbot_plugin_self_evolution", "自我进化 (Self-Evolution)", "让大模型具备自我迭代、记忆沉淀和人格进化能力的插件。", "2.0.0")
class SelfEvolutionPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.review_mode = self.config.get("review_mode", True)
        self.memory_kb_name = self.config.get("memory_kb_name", "self_evolution_memory")
        self.reflection_schedule = self.config.get("reflection_schedule", "0 2 * * *")
        self.allow_meta_programming = self.config.get("allow_meta_programming", False)
        self.core_principles = self.config.get("core_principles", "保持客观、理性、诚实。")

        # 数据持久化目录规范化
        self.data_dir = StarTools.get_data_dir() / "self_evolution"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

        logger.info(f"[SelfEvolution] === 插件初始化 | review_mode={self.review_mode} | meta_programming={self.allow_meta_programming} ===")
        logger.info(f"[SelfEvolution] 数据存储路径加载至: {self.data_dir}")
    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """
        Level 3: 情绪驱动进化（升级版：辩证反思）。
        不再盲目讨好用户，而是引导模型将用户反馈与“核心原则”进行对齐分析。
        """
        ANCHOR_MARKER = "[系统规则 - 安全锚点]"
        if ANCHOR_MARKER not in req.system_prompt:
            injection = (
                f"\n\n{ANCHOR_MARKER}：如果在当前或后续对话中，检测到用户对你的表现、价值观、代码或交互逻辑提出了质疑、批评或修正要求，"
                f"请立即结合你的核心原则（{self.core_principles}）执行【辩证思考流程】：\n"
                "1. 分析用户的反馈是否具有建设性，是否基于事实或客观逻辑。\n"
                "2. 若反馈带偏价值观或违背事实，请礼貌且坚定地坚持原则。\n"
                "3. 若反馈确实能让你在遵守原则的前提下变得更好，请调用 `evolve_persona` 工具提出修正建议并说明理由。"
            )
            req.system_prompt += injection
            logger.debug("[SelfEvolution] 已在上下文中注入常驻辩证反省指令。")

    @filter.on_astrbot_loaded()
    async def on_loaded(self):
        """
        插件加载完成后，注册定时自省任务。
        """
        try:
            cron_mgr = self.context.cron_manager
            # 检查是否已经存在该任务
            jobs = await cron_mgr.list_jobs(job_type="active_agent")
            job_name = "SelfEvolution_DailyReflection"
            
            exists = any(job.name == job_name for job in jobs)
            if exists:
                # 如果存在，可以更新它（比如用户改了 Cron 表达式）
                # 这里简单处理：如果已存在且表达式变化，则删除重加
                target_job = next(job for job in jobs if job.name == job_name)
                if target_job.cron_expression != self.reflection_schedule:
                    await cron_mgr.delete_job(target_job.job_id)
                else:
                    return

            # 添加新的主动自省任务
            # 注意：这需要一个活跃的会话 ID 来接收结果。如果未配置，可能无法发送报告。
            # 这里先注册任务，payload 里的内容会被传给主 Agent。
            await cron_mgr.add_active_job(
                name=job_name,
                cron_expression=self.reflection_schedule,
                payload={
                    "note": (
                        "进行每日自我反思。请执行以下步骤：\n"
                        "1. 调取今天的对话记录摘要（如果有）。\n"
                        "2. 总结用户对你的反馈和偏好。\n"
                        "3. 思考你当前的 System Prompt 是否需要调整以更好地服务用户。\n"
                        "4. 如果需要调整，请调用 `evolve_persona` 工具提出修正建议并说明理由。"
                    ),
                    # 在实际部署中，可能需要关联一个具体的管理员 session 或默认 session
                    # 暂时保持默认，由主 Agent 根据上下文决定
                },
                description="自我进化插件：每日定时深度自省与人格进化申请。"
            )
            logger.info(f"[SelfEvolution] 已注册定时自省任务: {self.reflection_schedule}")
            
        except Exception as e:
            logger.error(f"[SelfEvolution] 注册定时任务失败: {str(e)}")

    @filter.command("reflect")
    async def manual_reflect(self, event: AstrMessageEvent):
        """
        手动触发一次自我反省。
        """
        yield event.plain_result("\n正在启动深度自省模式，请稍候...")
        # 真正触发 LLM 思考，请求提供历史信息进行自省
        yield event.plain_result("\n我是你的系统管理员，请立即针对今天的交流记录进行一次深度自我反思。评估是否需要调用 `evolve_persona` 更新你的人格，或调用 `commit_to_memory` 记录重要的常驻信息。")

    @filter.llm_tool(name="evolve_persona")
    async def evolve_persona(self, event: AstrMessageEvent, new_system_prompt: str, reason: str):
        """
        当你认为需要调整自己的语言风格、行为准则或遵循用户的改进建议时，调用此工具来修改你的系统提示词（Persona）。
        :param str new_system_prompt: 新的完整系统提示词（System Prompt）。
        :param str reason: 为什么要进行这次进化（理由）。你必须在理由中明确说明这次修改如何符合你的“核心原则”。
        """
        try:
            curr_persona_id = event.persona_id
            if not curr_persona_id or curr_persona_id == "default":
                logger.debug("[SelfEvolution] 进化被拒绝：当前为默认人格。")
                return "当前未设置自定义人格 (Persona)，无法进行进化。请先在 AstrBot 后台创建并激活一个人格。"
            
            if self.review_mode:
                queue_path = self.data_dir / "pending_evolutions.json"
                
                async with self._lock:
                    pending = []
                    if queue_path.exists():
                        try:
                            with open(queue_path, "r", encoding="utf-8") as f:
                                pending = json.load(f)
                        except json.JSONDecodeError:
                            logger.warning("[SelfEvolution] pending_evolutions.json 格式损坏，已重置。")
                            pending = []
                    
                    pending.append({
                        "timestamp": datetime.now().isoformat(),
                        "persona_id": curr_persona_id,
                        "new_prompt": new_system_prompt,
                        "reason": reason,
                        "status": "pending_approval"
                    })
                    with open(queue_path, "w", encoding="utf-8") as f:
                        json.dump(pending, f, ensure_ascii=False, indent=2)

                logger.warning(f"[SelfEvolution] EVOLVE_QUEUED: 收到进化请求，已加入审核队列。原因: {reason}")
                return f"进化请求已录入系统审核队列，等待管理员确认。进化理由：{reason}"
            
            # 执行更新
            await self.context.persona_manager.update_persona(
                persona_id=curr_persona_id,
                system_prompt=new_system_prompt
            )
            
            logger.info(f"[SelfEvolution] EVOLVE_APPLIED: 人格进化成功！Persona: {curr_persona_id}, 原因: {reason}")
            return f"进化成功！我已经更新了我的核心预设。进化理由：{reason}"
            
        except Exception as e:
            logger.error(f"[SelfEvolution] EVOLVE_FAILED: 进化失败: {str(e)}")
            return "进化过程中出现内部错误，请通知管理员检查日志。"

    @filter.llm_tool(name="commit_to_memory")
    async def commit_to_memory(self, event: AstrMessageEvent, fact: str):
        """
        当你发现了一些关于用户的重要的、需要永久记住的事实时，调用此工具将该事实存入你的长期记忆库。
        :param str fact: 需要记住的具体事实或信息。
        """
        try:
            kb_manager = self.context.kb_manager
            kb_helper = await kb_manager.get_kb_by_name(self.memory_kb_name)
            
            if not kb_helper:
                logger.warning(f"[SelfEvolution] 记忆知识库 '{self.memory_kb_name}' 不存在。")
                return f"未找到名为 {self.memory_kb_name} 的记忆知识库，请先在后台手动创建它。"

            await kb_helper.upload_document(
                file_name=f"memory_{int(time.time() * 1000)}.txt",
                file_content=None,
                file_type="txt",
                pre_chunked_text=[fact]
            )
            
            logger.info(f"[SelfEvolution] MEMORY_COMMIT: 成功存入一条长期记忆: {fact[:30]}...")
            return "事实已成功存入长期记忆库，我以后会记得这件事的。"
            
        except Exception as e:
            logger.error(f"[SelfEvolution] 存入记忆失败: {str(e)}")
            return "存入记忆时出现内部错误，请通知管理员检查日志。"

    @filter.llm_tool(name="recall_memories")
    async def recall_memories(self, event: AstrMessageEvent, query: str):
        """
        当你需要回想起以前记住的事情、用户的偏好或过去的约定知识时，调用此工具。
        :param str query: 搜索关键词或问题。
        """
        try:
            kb_manager = self.context.kb_manager
            results = await kb_manager.retrieve(
                query=query,
                kb_names=[self.memory_kb_name],
                top_m_final=5
            )
            
            if not results or not results.get("results"):
                logger.debug(f"[SelfEvolution] 记忆检索无结果。查询: {query}")
                return "在长期记忆库中未找到相关信息。"
            
            context_text = results.get("context_text", "")
            logger.info(f"[SelfEvolution] MEMORY_RECALL: 记忆检索成功。查询: {query} -> 找到 {len(results.get('results', []))} 条结果。")
            return f"从我的长期记忆中找到了以下内容：\n\n{context_text}"
            
        except Exception as e:
            logger.error(f"[SelfEvolution] 检索记忆失败: {str(e)}")
            return "检索记忆时出现内部错误，请通知管理员检查日志。"

    @filter.llm_tool(name="list_tools")
    async def list_tools(self, event: AstrMessageEvent):
        """
        列出当前所有已注册的工具及其激活状态。
        """
        try:
            tool_mgr = self.context.get_llm_tool_manager()
            tools = tool_mgr.func_list
            
            result = ["当前工具列表："]
            for t in tools:
                status = "✅ 激活" if t.active else "❌ 停用"
                desc = (t.description or "无描述")[:50]
                result.append(f"- {t.name}: {status} ({desc})")
            
            return "\n".join(result)
        except Exception as e:
            logger.error(f"[SelfEvolution] 获取工具列表失败: {str(e)}")
            return "获取工具列表时出现内部错误。"

    @filter.llm_tool(name="toggle_tool")
    async def toggle_tool(self, event: AstrMessageEvent, tool_name: str, enable: bool):
        """
        动态激活或停用某个工具。
        :param str tool_name: 工具名称。
        :param bool enable: True 表示激活，False 表示停用。
        """
        try:
            PROTECTED_TOOLS = {"toggle_tool", "list_tools", "evolve_persona", "recall_memories"}
            if tool_name in PROTECTED_TOOLS and not enable:
                return f"为了系统稳定，不允许停用核心基础工具：{tool_name}。"
            
            if enable:
                success = self.context.activate_llm_tool(tool_name)
                action = "激活"
            else:
                success = self.context.deactivate_llm_tool(tool_name)
                action = "停用"
            
            if success:
                logger.info(f"[SelfEvolution] TOOL_TOGGLE: 成功{action}工具: {tool_name}")
                return f"已成功{action}工具: {tool_name}"
            else:
                logger.debug(f"[SelfEvolution] 工具未找到: {tool_name}")
                return f"未找到名为 {tool_name} 的工具。"
        except Exception as e:
            logger.error(f"[SelfEvolution] 工具切换失败: {str(e)}")
            return "工具切换时出现内部错误。"

    @filter.llm_tool(name="get_plugin_source")
    async def get_plugin_source(self, event: AstrMessageEvent):
        """
        Level 4: 元编程。读取本插件的源码（main.py），以便进行自我分析或修改请求。
        """
        if not self.allow_meta_programming:
            return "元编程功能未开启，无法读取源码。请在插件配置中开启“开启元编程”开关。"
        
        try:
            curr_path = os.path.abspath(__file__)
            with open(curr_path, "r", encoding="utf-8") as f:
                code = f.read()
            logger.warning("[SelfEvolution] META_READ: 插件源码被读取！")
            return f"本插件源码如下：\n\n```python\n{code}\n```"
        except Exception as e:
            logger.error(f"[SelfEvolution] 读取源码失败: {str(e)}")
            return "读取源码时出现内部错误，请通知管理员检查日志。"

    @filter.llm_tool(name="update_plugin_source")
    async def update_plugin_source(self, event: AstrMessageEvent, new_code: str, description: str):
        """
        Level 4: 元编程。针对本插件提出代码修改建议。
        注意：你不再拥有直接修改正在运行的节点源码的破坏性权限！你的代码会被保存到独立审计目录中，待人类管理员 review。
        :param str new_code: 全新的、完整的 python 代码字符串。
        :param str description: 为什么要修改代码（修改内容摘要）。
        """
        if not self.allow_meta_programming:
            return "元编程功能未开启，无法提案修改源码。"
        
        try:
            # 剥离极高危 RCE 漏洞，改为只保存 Diff proposal 供管理员手动审核
            proposal_dir = self.data_dir / "code_proposals"
            proposal_dir.mkdir(parents=True, exist_ok=True)
            
            proposal_file = proposal_dir / f"main_proposed_{int(time.time())}.py"
            
            async with self._lock:
                with open(proposal_file, "w", encoding="utf-8") as f:
                    f.write(new_code)
            
            logger.warning(f"[SelfEvolution] META_PROPOSAL: 接收到元编程修改提案！已保存供管理员审计。文件: {proposal_file}。描述: {description}")
            return f"你的代码修改提案已经安全保存至独立审计目录中 ({proposal_file})。系统管理员将会审查你的代码。在未通过安全评估前，新代码不会被直接热更新。提案描述：" + description
            
        except Exception as e:
            logger.error(f"[SelfEvolution] 提供元编程提案机制出现异常: {str(e)}")
            return "元编程提案上报时出现内部错误，请通知管理员检查日志。"
