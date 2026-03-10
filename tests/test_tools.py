import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.asyncio
async def test_get_user_messages(mock_context, profile_manager):
    """测试获取用户历史消息工具"""
    from engine.profile import ProfileManager

    mock_event = MagicMock()
    mock_event.get_sender_id = MagicMock(return_value="123456")

    result = await profile_manager.load_profile("test_user")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_update_user_profile_tool(profile_manager):
    """测试更新用户画像工具"""
    mock_event = MagicMock()
    mock_event.get_sender_id = MagicMock(return_value="123456")

    result = await profile_manager.save_profile("test_user_001", "测试内容")
    # 保存不返回结果，直接写文件
    assert result is None

    loaded = await profile_manager.load_profile("test_user_001")
    assert loaded == "测试内容"


@pytest.mark.asyncio
async def test_get_user_profile_tool(profile_manager):
    """测试获取用户画像工具"""
    await profile_manager.save_profile("test_user_002", "# 用户印象\n喜欢编程")

    result = await profile_manager.load_profile("test_user_002")
    assert "喜欢编程" in result
