import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_evolution_review_mode(persona_manager, dao):
    """测试审核模式"""
    mock_event = MagicMock()
    mock_event.get_sender_id = MagicMock(return_value="123456")
    mock_event.unified_msg_origin = "qq"
    mock_event.get_platform_name = MagicMock(return_value="qq")

    persona_manager.plugin.config.get = MagicMock(
        side_effect=lambda key, default=None: {
            "review_mode": True,
        }.get(key, default)
    )

    mock_persona_manager = MagicMock()
    mock_persona_manager.resolve_selected_persona = AsyncMock(
        return_value=("test_persona", "", "", "")
    )
    persona_manager.plugin.context.persona_manager = mock_persona_manager

    result = await persona_manager.evolve_persona(
        mock_event, "新的系统提示词", "测试进化"
    )
    assert "审核" in result or "队列" in result


@pytest.mark.asyncio
async def test_evolution_auto_approve(persona_manager, dao):
    """测试自动批准"""
    mock_event = MagicMock()
    mock_event.get_sender_id = MagicMock(return_value="123456")
    mock_event.unified_msg_origin = "qq"
    mock_event.get_platform_name = MagicMock(return_value="qq")

    persona_manager.plugin.config.get = MagicMock(
        side_effect=lambda key, default=None: {
            "review_mode": False,
        }.get(key, default)
    )

    mock_persona_manager = MagicMock()
    mock_persona_manager.update_persona = AsyncMock()
    mock_persona_manager.resolve_selected_persona = AsyncMock(
        return_value=("test_persona", "", "", "")
    )
    persona_manager.plugin.context.persona_manager = mock_persona_manager

    result = await persona_manager.evolve_persona(
        mock_event, "新的系统提示词", "测试进化"
    )
    assert "成功" in result or "更新" in result


@pytest.mark.asyncio
async def test_reject_evolution(persona_manager, dao):
    """测试拒绝进化"""
    await dao.add_pending_evolution("persona_reject", "prompt", "reason")
    rows = await dao.get_pending_evolutions(limit=10, offset=0)
    request_id = rows[0]["id"]

    mock_event = MagicMock()
    mock_event.is_admin = MagicMock(return_value=True)
    mock_event.get_sender_id = MagicMock(return_value="admin")

    result = await persona_manager.reject_evolution(mock_event, request_id)
    assert "拒绝" in result or "成功" in result


@pytest.mark.asyncio
async def test_review_evolutions(persona_manager, dao):
    """测试查看进化请求"""
    await dao.add_pending_evolution("persona_review", "prompt1", "reason1")
    await dao.add_pending_evolution("persona_review2", "prompt2", "reason2")

    mock_event = MagicMock()
    mock_event.is_admin = MagicMock(return_value=True)
    mock_event.get_sender_id = MagicMock(return_value="admin")

    result = await persona_manager.review_evolutions(mock_event)
    assert "待审核" in result or "ID:" in result
