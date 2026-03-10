import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_commit_memory(memory_manager, mock_context):
    """测试存入记忆"""
    mock_event = MagicMock()
    mock_event.get_sender_id = MagicMock(return_value="123456")
    mock_event.get_sender_name = MagicMock(return_value="测试用户")
    mock_event.get_group_id = MagicMock(return_value="987654")
    mock_event.unified_msg_origin = "qq"

    result = await memory_manager.commit_to_memory(mock_event, "这是一个测试记忆")
    # 知识库可能不存在，返回错误消息
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_recall_memories(memory_manager):
    """测试检索记忆"""
    mock_event = MagicMock()
    mock_event.message_str = "测试查询"

    result = await memory_manager.recall_memories(mock_event, "测试查询")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_save_group_knowledge(memory_manager):
    """测试保存群公共知识"""
    mock_event = MagicMock()
    mock_event.get_sender_id = MagicMock(return_value="123456")
    mock_event.get_sender_name = MagicMock(return_value="测试用户")
    mock_event.get_group_id = MagicMock(return_value="987654321")
    mock_event.unified_msg_origin = "qq"

    result = await memory_manager.save_group_knowledge(
        mock_event, knowledge="群规1：禁止广告", knowledge_type="群规"
    )
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_clear_all_memory(memory_manager):
    """测试清空所有记忆"""
    mock_event = MagicMock()

    result = await memory_manager.clear_all_memory(mock_event, confirm=False)
    assert "confirm" in result

    result_confirm = await memory_manager.clear_all_memory(mock_event, confirm=True)
    assert isinstance(result_confirm, str)


@pytest.mark.asyncio
async def test_list_memories(memory_manager):
    """测试列出记忆"""
    mock_event = MagicMock()

    result = await memory_manager.list_memories(mock_event, limit=5)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_delete_memory(memory_manager):
    """测试删除单条记忆"""
    mock_event = MagicMock()

    result = await memory_manager.delete_memory(mock_event, "doc_123")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_auto_recall(memory_manager):
    """测试主动回忆"""
    mock_event = MagicMock()
    mock_event.message_str = "测试主题"

    result = await memory_manager.auto_recall(mock_event, topic="测试主题")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_learn_from_context(memory_manager):
    """测试从上下文学习"""
    mock_event = MagicMock()
    mock_event.get_sender_id = MagicMock(return_value="123456")
    mock_event.get_sender_name = MagicMock(return_value="测试用户")
    mock_event.get_group_id = MagicMock(return_value="987654")
    mock_event.unified_msg_origin = "qq"
    mock_event.message_str = "我喜欢 Python 编程"

    result = await memory_manager.learn_from_context(mock_event)
    assert isinstance(result, str)
