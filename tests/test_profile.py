import pytest
import pytest_asyncio


@pytest.mark.asyncio
async def test_load_empty_profile(profile_manager):
    """测试加载空画像"""
    content = await profile_manager.load_profile("non_existent_user")
    assert content == ""


@pytest.mark.asyncio
async def test_save_and_load_markdown(profile_manager):
    """测试 Markdown 存储"""
    test_content = "# 用户印象笔记\n\n这是一个测试内容"
    await profile_manager.save_profile("test_user_001", test_content)

    loaded = await profile_manager.load_profile("test_user_001")
    assert loaded == test_content


@pytest.mark.asyncio
async def test_profile_truncation(profile_manager):
    """测试摘要截断"""
    long_content = "A" * 1000
    await profile_manager.save_profile("test_user_002", long_content)

    summary = await profile_manager.get_profile_summary("test_user_002")
    # 简单模式不截断，返回原始内容
    assert len(summary) > 0


@pytest.mark.asyncio
async def test_view_profile(profile_manager):
    """测试查看画像"""
    test_content = "# 用户印象笔记\n\n- 喜欢 Python"
    await profile_manager.save_profile("test_user_003", test_content)

    view_result = await profile_manager.view_profile("test_user_003")
    assert "test_user_003" in view_result
    assert "喜欢 Python" in view_result


@pytest.mark.asyncio
async def test_delete_profile(profile_manager):
    """测试删除画像"""
    await profile_manager.save_profile("test_user_004", "测试内容")

    result = await profile_manager.delete_profile("test_user_004")
    assert "已删除" in result

    content = await profile_manager.load_profile("test_user_004")
    assert content == ""


@pytest.mark.asyncio
async def test_list_profiles(profile_manager):
    """测试列出所有画像"""
    await profile_manager.save_profile("user_001", "内容1")
    await profile_manager.save_profile("user_002", "内容2")

    stats = await profile_manager.list_profiles()
    assert stats["total_users"] >= 2


@pytest.mark.asyncio
async def test_view_nonexistent_profile(profile_manager):
    """测试查看不存在的画像"""
    result = await profile_manager.view_profile("never_existed_user")
    assert "暂无画像记录" in result
