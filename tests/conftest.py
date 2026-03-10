import pytest
import pytest_asyncio
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime


@pytest.fixture
def temp_dir():
    """创建临时目录用于测试"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config():
    """创建模拟的配置"""
    config = MagicMock()
    config.get = MagicMock(
        side_effect=lambda key, default=None: {
            "persona_name": "黑塔",
            "persona_title": "人偶负责人",
            "persona_style": "理性、犀利且专业",
            "interjection_desire": 5,
            "critical_keywords": "黑塔|空间站|人偶|天才|模拟宇宙",
            "review_mode": True,
            "allow_meta_programming": False,
            "memory_kb_name": "self_evolution_memory",
            "reflection_schedule": "0 3 * * *",
            "core_principles": "保持客观、理性",
            "admin_users": [],
            "buffer_threshold": 8,
            "max_buffer_size": 20,
            "max_memory_entries": 100,
            "enable_profile_update": True,
            "enable_context_recall": True,
            "profile_precision_mode": "simple",
            "dream_enabled": True,
            "dream_schedule": "0 3 * * *",
            "dream_max_users": 20,
            "dream_concurrency": 3,
        }.get(key, default)
    )
    return config


@pytest.fixture
def mock_context(mock_config):
    """创建模拟的 AstrBot Context"""
    context = MagicMock()
    context.config = mock_config
    context.get_config = MagicMock(return_value=mock_config)

    mock_kb_manager = MagicMock()
    mock_kb = MagicMock()
    mock_kb_manager.get_kb_by_name = AsyncMock(return_value=mock_kb)
    mock_kb_manager.retrieve = AsyncMock(return_value={"results": []})
    context.kb_manager = mock_kb_manager

    mock_history_mgr = MagicMock()
    mock_history_mgr.get = AsyncMock(return_value=[])
    context.message_history_manager = mock_history_mgr

    mock_cron_mgr = MagicMock()
    mock_cron_mgr.add_basic_job = AsyncMock()
    mock_cron_mgr.list_jobs = AsyncMock(return_value=[])
    mock_cron_mgr.delete_job = AsyncMock()
    context.cron_manager = mock_cron_mgr

    mock_persona_mgr = MagicMock()
    mock_persona_mgr.update_persona = AsyncMock()
    mock_persona_mgr.resolve_selected_persona = AsyncMock(
        return_value=("default", "", "", "")
    )
    context.persona_manager = mock_persona_mgr

    mock_conv_mgr = MagicMock()
    mock_conv_mgr.get_curr_conversation_id = AsyncMock(return_value=None)
    context.conversation_manager = mock_conv_mgr

    mock_tool_mgr = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = "test_tool"
    mock_tool.active = True
    mock_tool_mgr.func_list = [mock_tool]
    context.get_llm_tool_manager = MagicMock(return_value=mock_tool_mgr)

    return context


@pytest.fixture
def mock_provider():
    """创建模拟的 LLM Provider"""
    provider = MagicMock()
    provider.provider_config = {
        "id": "test-provider",
        "type": "openai_chat_completion",
        "model": "gpt-4o-mini",
    }
    provider.get_model = MagicMock(return_value="gpt-4o-mini")

    mock_response = MagicMock()
    mock_response.completion_text = "测试回复"
    provider.text_chat = AsyncMock(return_value=mock_response)
    provider.text_chat_stream = AsyncMock(return_value=mock_response)
    provider.terminate = AsyncMock()

    return provider


@pytest.fixture
def mock_event():
    """创建模拟的 AstrMessageEvent"""
    event = MagicMock()
    event.unified_msg_origin = "test_umo"
    event.session_id = "test_session"
    event.message_str = "测试消息"
    event.message_obj = MagicMock()
    event.message_obj.message = []
    event.message_obj.sender = MagicMock()
    event.message_obj.sender.user_id = "123456"
    event.message_obj.sender.nickname = "测试用户"
    event.message_obj.group_id = None
    event.get_platform_name = MagicMock(return_value="test_platform")
    event.get_platform_id = MagicMock(return_value="test_platform")
    event.get_group_id = MagicMock(return_value=None)
    event.get_sender_id = MagicMock(return_value="123456")
    event.get_sender_name = MagicMock(return_value="测试用户")
    event.get_messages = MagicMock(return_value=[])
    event.is_at_or_wake_command = False
    event.is_admin = MagicMock(return_value=False)
    event.plain_result = MagicMock(return_value="测试回复")
    event.stop_event = MagicMock()
    event.get_extra = MagicMock(return_value=None)
    event.set_extra = MagicMock()
    return event


@pytest.fixture
def mock_group_event(mock_event):
    """创建模拟的群消息事件"""
    mock_event.get_group_id = MagicMock(return_value="987654321")
    mock_event.message_str = "群消息测试"
    return mock_event


@pytest_asyncio.fixture
async def dao(temp_dir):
    """创建 DAO 实例"""
    from dao import SelfEvolutionDAO

    db_path = temp_dir / "test.db"
    dao = SelfEvolutionDAO(str(db_path))
    await dao.init_db()
    yield dao
    await dao.close()


@pytest_asyncio.fixture
async def profile_manager(mock_context, temp_dir):
    """创建画像管理器实例"""
    from engine.profile import ProfileManager

    mock_plugin = MagicMock()
    mock_plugin.config = mock_context.config
    mock_plugin.data_dir = temp_dir

    profile_mgr = ProfileManager(mock_plugin)
    yield profile_mgr


@pytest_asyncio.fixture
async def memory_manager(mock_context):
    """创建记忆管理器实例"""
    from engine.memory import MemoryManager

    mock_plugin = MagicMock()
    mock_plugin.config = mock_context.config
    mock_plugin.context = mock_context

    memory_mgr = MemoryManager(mock_plugin)
    yield memory_mgr


@pytest_asyncio.fixture
async def eavesdropping_engine(mock_context):
    """创建插嘴引擎实例"""
    from engine.eavesdropping import EavesdroppingEngine

    mock_plugin = MagicMock()
    mock_plugin.config = mock_context.config
    mock_plugin.context = mock_context
    mock_plugin.active_buffers = {}
    mock_plugin.processing_sessions = set()
    mock_plugin._session_speakers = {}
    mock_plugin.critical_keywords = "黑塔|空间站|人偶"
    mock_plugin.persona_name = "黑塔"
    mock_plugin.persona_title = "人偶负责人"
    mock_plugin.persona_style = "理性"
    mock_plugin.interjection_desire = 5
    mock_plugin.buffer_threshold = 8
    mock_plugin.max_buffer_size = 20

    engine = EavesdroppingEngine(mock_plugin)
    yield engine


@pytest_asyncio.fixture
async def persona_manager(mock_context, dao):
    """创建人格管理器实例"""
    from engine.persona import PersonaManager

    mock_plugin = MagicMock()
    mock_plugin.config = mock_context.config
    mock_plugin.context = mock_context
    mock_plugin.dao = dao

    persona_mgr = PersonaManager(mock_plugin)
    yield persona_mgr


@pytest_asyncio.fixture
async def meta_infra(mock_context, temp_dir):
    """创建元编程基础设施实例"""
    from engine.meta_infra import MetaInfra

    mock_plugin = MagicMock()
    mock_plugin.config = mock_context.config
    mock_plugin.allow_meta_programming = False
    mock_plugin.data_dir = temp_dir
    mock_plugin._lock = None

    meta = MetaInfra(mock_plugin)
    yield meta
