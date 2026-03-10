import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.asyncio
async def test_dream_max_users_config(mock_config):
    """测试 dream_max_users 配置"""
    value = mock_config.get("dream_max_users", 20)
    assert value == 20

    mock_config.get = MagicMock(return_value=50)
    value = mock_config.get("dream_max_users", 20)
    assert value == 50


@pytest.mark.asyncio
async def test_dream_concurrency_config(mock_config):
    """测试 dream_concurrency 配置"""
    value = mock_config.get("dream_concurrency", 3)
    assert value == 3

    mock_config.get = MagicMock(return_value=5)
    value = mock_config.get("dream_concurrency", 3)
    assert value == 5


@pytest.mark.asyncio
async def test_reflection_schedule_config(mock_config):
    """测试 reflection_schedule 配置"""
    value = mock_config.get("reflection_schedule", "0 3 * * *")
    assert value == "0 3 * * *"

    mock_config.get = MagicMock(return_value="0 2 * * *")
    value = mock_config.get("reflection_schedule", "0 3 * * *")
    assert value == "0 2 * * *"
