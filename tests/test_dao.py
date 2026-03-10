import pytest
import pytest_asyncio


@pytest.mark.asyncio
async def test_get_affinity_default(dao):
    """测试默认好感度为 50"""
    score = await dao.get_affinity("new_user_123")
    assert score == 50


@pytest.mark.asyncio
async def test_update_affinity(dao):
    """测试好感度增减"""
    await dao.update_affinity("test_user", 10)
    score = await dao.get_affinity("test_user")
    assert score == 60


@pytest.mark.asyncio
async def test_affinity_clamp(dao):
    """测试好感度边界 (0-100)"""
    await dao.update_affinity("test_user_clamp", 100)
    score = await dao.get_affinity("test_user_clamp")
    assert score == 100

    await dao.update_affinity("test_user_clamp", -200)
    score = await dao.get_affinity("test_user_clamp")
    assert score == 0


@pytest.mark.asyncio
async def test_pending_evolutions(dao):
    """测试进化请求队列"""
    await dao.add_pending_evolution(
        persona_id="test_persona", new_prompt="新的系统提示词", reason="测试进化"
    )

    rows = await dao.get_pending_evolutions(limit=10, offset=0)
    assert len(rows) == 1
    assert rows[0]["persona_id"] == "test_persona"
    assert rows[0]["reason"] == "测试进化"


@pytest.mark.asyncio
async def test_approve_evolution(dao):
    """测试批准进化"""
    await dao.add_pending_evolution(
        persona_id="test_persona_approve", new_prompt="批准的提示词", reason="测试批准"
    )

    rows = await dao.get_pending_evolutions(limit=10, offset=0)
    request_id = rows[0]["id"]

    await dao.update_evolution_status(request_id, "approved")

    updated_rows = await dao.get_pending_evolutions(limit=10, offset=0)
    assert len(updated_rows) == 0


@pytest.mark.asyncio
async def test_recover_all_affinity(dao):
    """测试大赦天下功能"""
    await dao.update_affinity("negative_user", -30)
    score = await dao.get_affinity("negative_user")
    assert score == 20

    await dao.recover_all_affinity(recovery_amount=5)

    score_after = await dao.get_affinity("negative_user")
    assert score_after == 25


@pytest.mark.asyncio
async def test_set_pending_reflection(dao):
    """测试设置待反思标记"""
    await dao.set_pending_reflection("session_123", True)
    result = await dao.pop_pending_reflection("session_123")
    assert result is True

    result_again = await dao.pop_pending_reflection("session_123")
    assert result_again is False


@pytest.mark.asyncio
async def test_clear_pending_evolutions(dao):
    """测试清空进化队列"""
    await dao.add_pending_evolution("p1", "prompt1", "reason1")
    await dao.add_pending_evolution("p2", "prompt2", "reason2")

    await dao.clear_pending_evolutions()

    rows = await dao.get_pending_evolutions(limit=10, offset=0)
    assert len(rows) == 0
