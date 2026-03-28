# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from tests._helpers import load_engine_module

MetaInfra = load_engine_module("meta_infra").MetaInfra


class MetaInfraTests(IsolatedAsyncioTestCase):
    async def test_run_debate_uses_umo_for_provider_lookup(self):
        provider = SimpleNamespace(text_chat=AsyncMock(return_value=SimpleNamespace(completion_text="[PASS] ok")))
        get_using_provider = MagicMock(return_value=provider)
        plugin = SimpleNamespace(
            context=SimpleNamespace(get_using_provider=get_using_provider),
            cfg=SimpleNamespace(
                debate_rounds=1,
                debate_criteria="quality",
                debate_agents=[{"name": "Reviewer", "system_prompt": "review strictly"}],
                debate_system_prompt="review strictly",
            ),
        )
        meta = MetaInfra(plugin)

        result = await meta._run_debate("print('ok')", "desc", "main.py", umo="qq:group:meta-1")

        get_using_provider.assert_called_once_with(umo="qq:group:meta-1")
        self.assertTrue(result["passed"])

    async def test_update_plugin_source_no_lock_attribute(self):
        plugin = SimpleNamespace(
            allow_meta_programming=True,
            cfg=SimpleNamespace(debate_enabled=False),
            data_dir=Path("/tmp/test"),
        )
        meta = MetaInfra(plugin)

        with patch("builtins.open", MagicMock()), patch("os.chmod"):
            result = await meta.update_plugin_source("print('test')", "test desc", "main.py")
        self.assertTrue("saved" in result.lower() or "proposal" in result.lower())

    async def test_get_plugin_source_rejects_when_meta_programming_disabled(self):
        plugin = SimpleNamespace(allow_meta_programming=False)
        meta = MetaInfra(plugin)

        result = await meta.get_plugin_source("main")
        self.assertNotIn("def ", result)

    async def test_update_plugin_source_rejects_when_meta_programming_disabled(self):
        plugin = SimpleNamespace(
            allow_meta_programming=False,
            cfg=SimpleNamespace(debate_enabled=False),
        )
        meta = MetaInfra(plugin)

        result = await meta.update_plugin_source("print('test')", "test desc", "main.py")
        self.assertNotIn("saved", result.lower()) and self.assertNotIn("proposal", result.lower())

    async def test_run_debate_fails_when_provider_missing(self):
        get_using_provider = MagicMock(return_value=None)
        plugin = SimpleNamespace(
            context=SimpleNamespace(get_using_provider=get_using_provider),
            cfg=SimpleNamespace(
                debate_rounds=1,
                debate_criteria="quality",
                debate_agents=[{"name": "Reviewer", "system_prompt": "review strictly"}],
                debate_system_prompt="review strictly",
            ),
        )
        meta = MetaInfra(plugin)

        result = await meta._run_debate("print('ok')", "desc", "main.py")

        self.assertFalse(result["passed"])

    async def test_run_debate_fails_when_debate_agents_invalid_json(self):
        provider = SimpleNamespace(text_chat=AsyncMock(return_value=SimpleNamespace(completion_text="[PASS]")))
        get_using_provider = MagicMock(return_value=provider)
        plugin = SimpleNamespace(
            context=SimpleNamespace(get_using_provider=get_using_provider),
            cfg=SimpleNamespace(
                debate_rounds=1,
                debate_criteria="quality",
                debate_agents="invalid json {[}",
                debate_system_prompt="review strictly",
            ),
        )
        meta = MetaInfra(plugin)

        result = await meta._run_debate("print('ok')", "desc", "main.py")

        self.assertFalse(result["passed"])

    async def test_run_debate_fails_when_all_reviewers_exception(self):
        provider = SimpleNamespace(text_chat=AsyncMock(side_effect=Exception("provider error")))
        get_using_provider = MagicMock(return_value=provider)
        plugin = SimpleNamespace(
            context=SimpleNamespace(get_using_provider=get_using_provider),
            cfg=SimpleNamespace(
                debate_rounds=1,
                debate_criteria="quality",
                debate_agents=[{"name": "Reviewer", "system_prompt": "review strictly"}],
                debate_system_prompt="review strictly",
            ),
        )
        meta = MetaInfra(plugin)

        result = await meta._run_debate("print('ok')", "desc", "main.py")

        self.assertFalse(result["passed"])

    async def test_run_debate_passes_when_reviewer_returns_pass(self):
        provider = SimpleNamespace(
            text_chat=AsyncMock(return_value=SimpleNamespace(completion_text="[PASS] looks good"))
        )
        get_using_provider = MagicMock(return_value=provider)
        plugin = SimpleNamespace(
            context=SimpleNamespace(get_using_provider=get_using_provider),
            cfg=SimpleNamespace(
                debate_rounds=1,
                debate_criteria="quality",
                debate_agents=[{"name": "Reviewer", "system_prompt": "review strictly"}],
                debate_system_prompt="review strictly",
            ),
        )
        meta = MetaInfra(plugin)

        result = await meta._run_debate("print('ok')", "desc", "main.py")

        self.assertTrue(result["passed"])
