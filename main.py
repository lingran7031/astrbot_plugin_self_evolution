from astrbot.api.all import *
from astrbot.api.event import filter
from astrbot.api.provider import ProviderRequest
import json
import logging
import os

@register("astrbot_plugin_self_evolution", "自我进化 (Self-Evolution)", "让大模型具备自我迭代、记忆沉淀和人格进化能力的插件。", "1.0.0")
class SelfEvolutionPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.review_mode = self.config.get("review_mode", True)
        self.memory_kb_name = self.config.get("memory_kb_name", "self_evolution_memory")
        self.reflection_schedule = self.config.get("reflection_schedule", "0 2 * * *")
        self.allow_meta_programming = self.config.get("allow_meta_programming", False)

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """
        Level 3: 情绪驱动进化。
        在 LLM 请求发送前，扫描用户输入。如果发现强烈的负面反馈，
        在 System Prompt 中注入“深度反省建议”。
        """
        user_msg = event.message_str.lower()
        negative_keywords = ["太差", "不对", "傻逼", "啰嗦", "讨厌", "改进", "错误", "不行"]
        
        if any(kw in user_msg for kw in negative_keywords):
            injection = (
                "\n\n[系统注意]：检测到用户对你当前的表现可能存在不满或提出了修正要求。"
                "请在回答时保持谦虚，并认真考虑是否需要调用 `evolve_persona` 工具来优化你的性格预设，"
                "或使用 `commit_to_memory` 记录用户的偏好。"
            )
            req.system_prompt += injection
            logger.info("[SelfEvolution] 检测到负面情绪/反馈，已注入反省指令。")

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

    @command("reflect")
    async def manual_reflect(self, event: AstrMessageEvent):
        """
        手动触发一次自我反省。
        """
        yield event.plain_result("\n正在启动深度自省模式，请稍候...")
        # 构造一个模拟的自省提示词，直接发送给 LLM
        # 这里利用 yield 发送中间状态，然后通过工具调用逻辑实现
        # 简单起见，我们直接给用户一个引导，让大模型感知到自省需求
        yield event.plain_result("\n[自省指令]：请根据今天的交流，评估是否需要调用 `evolve_persona` 或 `commit_to_memory`。")

    @llm_tool(name="evolve_persona")
    async def evolve_persona(self, event: AstrMessageEvent, new_system_prompt: str, reason: str):
        """
        当你认为需要调整自己的语言风格、行为准则或遵循用户的改进建议时，调用此工具来修改你的系统提示词（Persona）。
        :param new_system_prompt: 新的完整系统提示词（System Prompt）。
        :param reason: 为什么要进行这次进化（理由）。
        """
        try:
            # 获取当前的 Persona ID
            # 注意：这里假设用户正在使用某种人格，如果没有，可能需要处理默认情况
            curr_persona_id = event.persona_id
            if not curr_persona_id or curr_persona_id == "default":
                # 如果是默认人格，尝试获取当前活跃的人格名
                # 简单处理：如果没写进 DB，可能无法直接 update
                # 但 AstrBot 通常会有选中的 persona
                pass
            
            if self.review_mode:
                logger.info(f"[SelfEvolution] 收到进化请求。原因: {reason}")
                logger.info(f"[SelfEvolution] 拟修改 Prompt 为: {new_system_prompt[:50]}...")
                return f"进化请求已提交，等待管理员审核。进化理由：{reason}"
            
            # 执行更新
            await self.context.persona_manager.update_persona(
                persona_id=curr_persona_id,
                system_prompt=new_system_prompt
            )
            
            logger.info(f"[SelfEvolution] 人格进化成功！Persona: {curr_persona_id}, 原因: {reason}")
            return f"进化成功！我已经更新了我的核心预设。进化理由：{reason}"
            
        except Exception as e:
            logger.error(f"[SelfEvolution] 进化失败: {str(e)}")
            return f"进化过程中出现错误: {str(e)}"

    @llm_tool(name="commit_to_memory")
    async def commit_to_memory(self, event: AstrMessageEvent, fact: str):
        """
        当你发现了一些关于用户的重要的、需要永久记住的事实时，调用此工具将该事实存入你的长期记忆库。
        :param fact: 需要记住的具体事实或信息。
        """
        try:
            kb_manager = self.context.kb_manager
            kb_helper = await kb_manager.get_kb_by_name(self.memory_kb_name)
            
            if not kb_helper:
                # 尝试自动创建一个简单的知识库（如果权限允许）
                # 这里可能需要更多的参数如 embedding_provider_id
                # 暂时报错提醒用户手动创建
                return f"未找到名为 {self.memory_kb_name} 的记忆知识库，请先在后台手动创建它。"

            # 存入记忆
            await kb_helper.upload_document(
                file_name=f"memory_{json.dumps(event.message_obj.timestamp)}.txt",
                file_content=None,
                file_type="txt",
                pre_chunked_text=[fact]
            )
            
            logger.info(f"[SelfEvolution] 成功存入一条长期记忆: {fact[:30]}...")
            return "事实已成功存入长期记忆库，我以后会记得这件事的。"
            
        except Exception as e:
            logger.error(f"[SelfEvolution] 存入记忆失败: {str(e)}")
            return f"存入记忆时出错: {str(e)}"

    @llm_tool(name="recall_memories")
    async def recall_memories(self, event: AstrMessageEvent, query: str):
        """
        当你需要回想起以前记住的事情、用户的偏好或过去的约定知识时，调用此工具。
        :param query: 搜索关键词或问题。
        """
        try:
            kb_manager = self.context.kb_manager
            results = await kb_manager.retrieve(
                query=query,
                kb_names=[self.memory_kb_name],
                top_m_final=5
            )
            
            if not results or not results.get("results"):
                return "在长期记忆库中未找到相关信息。"
            
            context_text = results.get("context_text", "")
            logger.info(f"[SelfEvolution] 记忆检索成功。查询: {query}")
            return f"从我的长期记忆中找到了以下内容：\n\n{context_text}"
            
        except Exception as e:
            logger.error(f"[SelfEvolution] 检索记忆失败: {str(e)}")
            return f"检索记忆时出错: {str(e)}"

    @llm_tool(name="list_tools")
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
                result.append(f"- {t.name}: {status} ({t.description[:50]}...)")
            
            return "\n".join(result)
        except Exception as e:
            return f"获取工具列表失败: {str(e)}"

    @llm_tool(name="toggle_tool")
    async def toggle_tool(self, event: AstrMessageEvent, tool_name: str, enable: bool):
        """
        动态激活或停用某个工具。
        :param tool_name: 工具名称。
        :param enable: True 表示激活，False 表示停用。
        """
        try:
            if tool_name == "toggle_tool":
                return "为了防止死锁，不允许停用 toggle_tool 自身。"
            
            if enable:
                success = self.context.activate_llm_tool(tool_name)
                action = "激活"
            else:
                success = self.context.deactivate_llm_tool(tool_name)
                action = "停用"
            
            if success:
                logger.info(f"[SelfEvolution] 成功{action}工具: {tool_name}")
                return f"已成功{action}工具: {tool_name}"
            else:
                return f"未找到名为 {tool_name} 的工具。"
        except Exception as e:
            return f"操作失败: {str(e)}"

    @llm_tool(name="get_plugin_source")
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
            return f"本插件源码如下：\n\n```python\n{code}\n```"
        except Exception as e:
            return f"读取源码失败: {str(e)}"

    @llm_tool(name="update_plugin_source")
    async def update_plugin_source(self, event: AstrMessageEvent, new_code: str, description: str):
        """
        Level 4: 元编程。修改本插件的源码（main.py）。这允许你增加新的功能或修改逻辑。
        :param new_code: 全新的、完整的 python 代码字符串。
        :param description: 为什么要修改代码（修改内容摘要）。
        """
        if not self.allow_meta_programming:
            return "元编程功能未开启，无法修改源码。"
        
        try:
            # 安全逻辑：如果 new_code 明显太短，拒绝
            if len(new_code) < 100:
                return "代码过短，为了安全起见拒绝更新。"
            
            # 写入文件
            curr_path = os.path.abspath(__file__)
            with open(curr_path, "w", encoding="utf-8") as f:
                f.write(new_code)
            
            logger.warning(f"[SelfEvolution] 元编程生效！描述: {description}")
            return "代码已更新成功！重启 AstrBot 后生效。修改详情：" + description
        except Exception as e:
            logger.error(f"[SelfEvolution] 元编程写入失败: {str(e)}")
            return f"更新代码失败: {str(e)}"
