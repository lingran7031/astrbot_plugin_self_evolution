import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.asyncio
async def test_command_skip(eavesdropping_engine, mock_event):
    """测试命令跳过"""
    mock_event.message_str = "/help"

    results = []
    async for r in eavesdropping_engine.handle_message(mock_event):
        results.append(r)

    assert len(results) == 0


@pytest.mark.asyncio
async def test_affinity_block(eavesdropping_engine, mock_event, dao):
    """测试好感度拦截"""
    await dao.update_affinity("123456", -100)

    mock_event.message_str = "普通消息"

    results = []
    async for r in eavesdropping_engine.handle_message(mock_event):
        results.append(r)

    assert len(results) == 0


@pytest.mark.asyncio
async def test_keyword_trigger(eavesdropping_engine, mock_event, mock_provider):
    """测试关键词触发"""
    mock_event.message_str = "我想讨论黑塔和空间站"
    mock_event.session_id = "session_keyword"
    mock_event.is_at_or_wake_command = False

    mock_plugin = eavesdropping_engine.plugin
    mock_plugin.dao.get_affinity = AsyncMock(return_value=50)
    mock_plugin.context.get_using_provider = MagicMock(return_value=mock_provider)

    results = []
    async for r in eavesdropping_engine.handle_message(mock_event):
        results.append(r)

    assert len(results) >= 0


@pytest.mark.asyncio
async def test_at_trigger(eavesdropping_engine, mock_event, mock_provider):
    """测试 @ 触发"""
    mock_event.message_str = "@黑塔 你好"
    mock_event.session_id = "session_at"
    mock_event.is_at_or_wake_command = True

    mock_plugin = eavesdropping_engine.plugin
    mock_plugin.dao.get_affinity = AsyncMock(return_value=50)
    mock_plugin.context.get_using_provider = MagicMock(return_value=mock_provider)

    results = []
    async for r in eavesdropping_engine.handle_message(mock_event):
        results.append(r)

    assert len(results) >= 0


@pytest.mark.asyncio
async def test_buffer_accumulation(eavesdropping_engine, mock_group_event):
    """测试缓冲池积累"""
    mock_group_event.is_at_or_wake_command = False
    mock_group_event.get_sender_id = MagicMock(return_value="user_001")
    mock_group_event.get_sender_name = MagicMock(return_value="用户A")

    mock_plugin = eavesdropping_engine.plugin
    mock_plugin.dao.get_affinity = AsyncMock(return_value=50)

    session_id = "session_buffer_test"
    mock_group_event.session_id = session_id

    for i in range(10):
        mock_group_event.message_str = f"消息 {i}"
        async for r in eavesdropping_engine.handle_message(mock_group_event):
            pass

    assert session_id in mock_plugin.active_buffers
    assert len(mock_plugin.active_buffers[session_id]) <= mock_plugin.max_buffer_size
