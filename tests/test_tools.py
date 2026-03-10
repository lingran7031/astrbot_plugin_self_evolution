import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_get_user_messages(mock_context):
    """测试获取用户历史消息工具"""
    from main import SelfEvolutionPlugin

    mock_event = MagicMock()
    mock_event.get_sender_id = MagicMock(return_value="123456")

    mock_plugin = MagicMock()
    mock_plugin.context = mock_context
    mock_plugin.profile = MagicMock()
    mock_plugin.profile.load_profile = AsyncMock(return_value="测试画像内容")

    class TestPlugin(SelfEvolutionPlugin):
        def __init__(self):
            self.context = mock_context
            self.profile = mock_plugin.profile

    plugin = TestPlugin()
    result = await plugin.get_user_messages(mock_event, target_user_id="654321")

    mock_context.message_history_manager.get.assert_called_once()


@pytest.mark.asyncio
async def test_update_user_profile_tool(mock_context):
    """测试更新用户画像工具"""
    from main import SelfEvolutionPlugin

    mock_event = MagicMock()
    mock_event.get_sender_id = MagicMock(return_value="123456")

    mock_plugin = MagicMock()
    mock_plugin.context = mock_context
    mock_plugin.profile = MagicMock()
    mock_plugin.profile.load_profile = AsyncMock(return_value="")
    mock_plugin.profile.save_profile = AsyncMock()

    class TestPlugin(SelfEvolutionPlugin):
        def __init__(self):
            self.context = mock_context
            self.profile = mock_plugin.profile

    plugin = TestPlugin()
    result = await plugin.update_user_profile(
        mock_event, target_user_id="654321", content="这个用户喜欢 Python"
    )

    mock_plugin.profile.save_profile.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_profile_tool(mock_context):
    """测试获取用户画像工具"""
    from main import SelfEvolutionPlugin

    mock_event = MagicMock()
    mock_event.get_sender_id = MagicMock(return_value="123456")

    mock_plugin = MagicMock()
    mock_plugin.context = mock_context
    mock_plugin.profile = MagicMock()
    mock_plugin.profile.load_profile = AsyncMock(return_value="# 用户印象\n喜欢编程")

    class TestPlugin(SelfEvolutionPlugin):
        def __init__(self):
            self.context = mock_context
            self.profile = mock_plugin.profile

    plugin = TestPlugin()
    result = await plugin.get_user_profile(mock_event)

    assert "喜欢编程" in result
