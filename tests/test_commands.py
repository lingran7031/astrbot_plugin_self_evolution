import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_set_affinity_command(dao):
    """测试设置好感度指令"""
    from engine.persona import PersonaManager

    mock_plugin = MagicMock()
    mock_plugin.dao = dao
    mock_plugin.config = MagicMock()
    mock_plugin.config.get = MagicMock(return_value=["admin"])

    mock_context = MagicMock()
    mock_plugin.context = mock_context

    persona_mgr = PersonaManager(mock_plugin)

    mock_event = MagicMock()
    mock_event.is_admin = MagicMock(return_value=True)
    mock_event.get_sender_id = MagicMock(return_value="admin")

    result = await persona_mgr.set_affinity(mock_event, "target_user", 80)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_reset_affinity_command(dao):
    """测试重置好感度指令"""
    await dao.update_affinity("test_reset_user", 20)

    result = await dao.reset_affinity("test_reset_user", 50)
    assert result is None

    score = await dao.get_affinity("test_reset_user")
    assert score == 50


@pytest.mark.asyncio
async def test_profile_stats_command():
    """测试画像统计指令"""
    from engine.profile import ProfileManager

    mock_plugin = MagicMock()
    mock_plugin.config = MagicMock()
    mock_plugin.data_dir = MagicMock()

    profile_mgr = ProfileManager(mock_plugin)

    stats = await profile_mgr.list_profiles()
    assert "total_users" in stats
    assert "total_tags" in stats
    assert "total_traits" in stats


@pytest.mark.asyncio
async def test_delete_profile_command():
    """测试删除画像指令"""
    from engine.profile import ProfileManager

    mock_plugin = MagicMock()
    mock_plugin.config = MagicMock()
    mock_plugin.data_dir = MagicMock()

    profile_mgr = ProfileManager(mock_plugin)

    result = await profile_mgr.delete_profile("nonexistent_user")
    assert "不存在" in result or "已删除" in result
