from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from tests._helpers import install_aiosqlite_stub, load_engine_module

install_aiosqlite_stub()


class ModerationResultParsingTests(IsolatedAsyncioTestCase):
    """Moderation result parsing and merge logic tests."""

    def setUp(self):
        m = load_engine_module("moderation")
        self.ModerationEngine = m.ModerationEngine
        self.ModerationResult = m.ModerationResult
        self.ViolationType = m.ViolationType

        class FakeDAO:
            def __init__(self):
                self._captions = {}

            async def get_moderation_caption(self, image_url):
                entry = self._captions.get(image_url)
                if entry:
                    return entry
                return None

            async def upsert_moderation_caption(self, image_url, caption, provider_id, source, ttl_seconds=3600):
                self._captions[image_url] = {
                    "caption": caption,
                    "provider_id": provider_id,
                    "source": source,
                    "created_at": datetime.now().isoformat(),
                    "expires_at": (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat(),
                }

        class FakePlugin:
            cfg = SimpleNamespace(
                moderation_warn_threshold=1,
                moderation_ban_threshold=2,
                moderation_kick_threshold=3,
                moderation_promo_warn_threshold=1,
                moderation_promo_ban_threshold=2,
                moderation_promo_kick_threshold=3,
                moderation_nsfw_delete_confidence=0.85,
                moderation_promo_delete_confidence=0.85,
                moderation_nsfw_enabled=True,
                moderation_promo_enabled=False,
                moderation_prefer_caption_reuse=True,
            )

        self.plugin = FakePlugin()
        self.plugin.dao = FakeDAO()
        self.engine = self.ModerationEngine(self.plugin)

    def test_parse_valid_json_nsfw(self):
        raw = '{"category": "nsfw", "confidence": 0.92, "risk_level": "high", "reasons": ["裸露"], "suggested_action": "delete"}'
        result = self.engine._parse_result(raw)
        self.assertEqual(result.category, "nsfw")
        self.assertEqual(result.confidence, 0.92)
        self.assertEqual(result.risk_level, "high")
        self.assertEqual(result.suggested_action, "delete")
        self.assertEqual(result.reasons, ["裸露"])

    def test_parse_valid_json_promo(self):
        raw = '{"category": "promo", "confidence": 0.88, "risk_level": "high", "reasons": ["二维码", "加群文案"], "suggested_action": "delete"}'
        result = self.engine._parse_result(raw)
        self.assertEqual(result.category, "promo")
        self.assertEqual(result.risk_level, "high")

    def test_parse_malformed_json_returns_uncertain(self):
        result = self.engine._parse_result("这不是 JSON")
        self.assertEqual(result.category, "uncertain")
        self.assertEqual(result.confidence, 0.0)

    def test_parse_partial_json_extracts_object(self):
        raw = '好的，我来描述一下这张图片。{"category": "nsfw", "confidence": 0.85, "risk_level": "high", "reasons": ["明显暴露"], "suggested_action": "delete"}  以上就是图片内容。'
        result = self.engine._parse_result(raw)
        self.assertEqual(result.category, "nsfw")
        self.assertEqual(result.confidence, 0.85)

    def test_merge_prefers_higher_risk(self):
        nsfw = self.ModerationResult(
            category="nsfw", confidence=0.9, risk_level="high", reasons=[], suggested_action="delete"
        )
        promo = self.ModerationResult(
            category="promo", confidence=0.7, risk_level="medium", reasons=[], suggested_action="delete"
        )
        merged = self.engine._merge_results(nsfw, promo)
        self.assertEqual(merged.category, "nsfw")

    def test_merge_promo_higher_when_nscore_lower(self):
        nsfw = self.ModerationResult(
            category="nsfw", confidence=0.5, risk_level="low", reasons=[], suggested_action="ignore"
        )
        promo = self.ModerationResult(
            category="promo", confidence=0.9, risk_level="high", reasons=[], suggested_action="delete"
        )
        merged = self.engine._merge_results(nsfw, promo)
        self.assertEqual(merged.category, "promo")

    def test_merge_uncertain_falls_back_to_valid(self):
        nsfw = self.ModerationResult.uncertain()
        promo = self.ModerationResult(
            category="promo", confidence=0.6, risk_level="medium", reasons=[], suggested_action="review"
        )
        merged = self.engine._merge_results(nsfw, promo)
        self.assertEqual(merged.category, "promo")

    def test_merge_both_uncertain_returns_uncertain(self):
        merged = self.engine._merge_results(None, None)
        self.assertEqual(merged.category, "uncertain")

    def test_is_high_confidence_delete_nsfw_high(self):
        r = self.ModerationResult(
            category="nsfw", confidence=0.90, risk_level="high", reasons=[], suggested_action="delete"
        )
        self.assertTrue(self.engine._is_high_confidence_delete(r))

    def test_is_high_confidence_delete_nsfw_medium_below_threshold(self):
        r = self.ModerationResult(
            category="nsfw", confidence=0.88, risk_level="medium", reasons=[], suggested_action="delete"
        )
        self.assertFalse(self.engine._is_high_confidence_delete(r))

    def test_is_high_confidence_delete_promo_high(self):
        r = self.ModerationResult(
            category="promo", confidence=0.85, risk_level="high", reasons=[], suggested_action="delete"
        )
        self.assertTrue(self.engine._is_high_confidence_delete(r))

    def test_should_escalate_warn(self):
        action, param = self.engine._should_escalate("nsfw", 1)
        self.assertEqual(action, "warn")

    def test_should_escalate_ban(self):
        action, param = self.engine._should_escalate("nsfw", 2)
        self.assertEqual(action, "ban")
        self.assertEqual(param, 300)

    def test_should_escalate_kick(self):
        action, param = self.engine._should_escalate("nsfw", 3)
        self.assertEqual(action, "kick")

    def test_should_escalate_promo_longer_ban(self):
        action, param = self.engine._should_escalate("promo", 2)
        self.assertEqual(action, "ban")
        self.assertEqual(param, 600)

    def test_should_escalate_record_below_threshold(self):
        action, param = self.engine._should_escalate("nsfw", 0)
        self.assertEqual(action, "record")

    def test_should_escalate_promo_qr_plus_text_direct_kick(self):
        result = self.engine._direct_kick("promo", "high", 0.90, ["二维码", "加群文案"])
        self.assertTrue(result)

    def test_should_escalate_promo_high_conf_direct_kick(self):
        result = self.engine._direct_kick("promo", "high", 0.92, ["二维码"])
        self.assertTrue(result)

    def test_should_escalate_nsfw_high_conf_direct_kick(self):
        result = self.engine._direct_kick("nsfw", "high", 0.91, ["裸露"])
        self.assertTrue(result)
        result = self.engine._direct_kick("nsfw", "medium", 0.5, ["裸露"])
        self.assertFalse(result)

    def test_should_escalate_record_below_threshold(self):
        action, param = self.engine._should_escalate("nsfw", 0)
        self.assertEqual(action, "record")


class ModerationEvidenceTests(IsolatedAsyncioTestCase):
    def test_evidence_to_dict(self):
        m = load_engine_module("moderation")
        ev = m.ModerationEvidence(
            group_id="5001",
            user_id="10001",
            message_id="msg123",
            image_url="http://example.com/img.jpg",
            category="nsfw",
            confidence=0.92,
            risk_level="high",
            reasons=["裸露"],
            suggested_action="delete",
            provider_id="openai",
        )
        d = ev.to_dict()
        self.assertEqual(d["group_id"], "5001")
        self.assertEqual(d["category"], "nsfw")
        self.assertEqual(d["confidence"], 0.92)
        self.assertIn("created_at", d)
        json_str = json.dumps(d)
        self.assertIn("5001", json_str)


class ModerationCaptionCacheTests(IsolatedAsyncioTestCase):
    """Caption cache hit/reuse/fallback tests."""

    def setUp(self):
        m = load_engine_module("moderation")
        self.ModerationEngine = m.ModerationEngine
        self.ModerationResult = m.ModerationResult

        class FakeDAO:
            def __init__(self):
                self._captions = {}

            async def get_moderation_caption(self, image_url):
                return self._captions.get(image_url)

            async def upsert_moderation_caption(self, image_url, caption, provider_id, source, ttl_seconds=3600):
                from datetime import datetime, timedelta

                self._captions[image_url] = {
                    "caption": caption,
                    "provider_id": provider_id,
                    "source": source,
                    "created_at": datetime.now().isoformat(),
                    "expires_at": (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat(),
                }

        class FakePlugin:
            cfg = SimpleNamespace(
                moderation_warn_threshold=1,
                moderation_ban_threshold=2,
                moderation_kick_threshold=3,
                moderation_promo_warn_threshold=1,
                moderation_promo_ban_threshold=2,
                moderation_promo_kick_threshold=3,
                moderation_nsfw_delete_confidence=0.85,
                moderation_promo_delete_confidence=0.85,
                moderation_nsfw_enabled=True,
                moderation_promo_enabled=False,
                moderation_prefer_caption_reuse=True,
            )

        self.plugin = FakePlugin()
        self.plugin.dao = FakeDAO()
        self.engine = self.ModerationEngine(self.plugin)

    async def asyncSetUp(self):
        pass

    def test_cache_hit_skips_provider_call(self):
        """Cache hit 时不再调用 provider。"""
        url = "http://example.com/cached.jpg"
        self.engine._caption_cache[url] = {
            "caption": '{"category":"nsfw","confidence":0.9,"risk_level":"high","reasons":[],"suggested_action":"delete"}',
            "provider_id": "openai",
            "source": "fallback",
            "expires_at": time.time() + 3600,
        }
        resolve_called = []

        orig_resolve = self.engine._resolve_provider

        def track_resolve(pid):
            resolve_called.append(pid)
            return orig_resolve(pid)

        self.engine._resolve_provider = track_resolve

        async def run():
            return await self.engine.caption_image(url, "nsfw prompt", "openai")

        result = asyncio.run(run())
        self.assertEqual(resolve_called, [])
        self.assertIn("nsfw", result)

    def test_cache_miss_writes_to_memory_and_db(self):
        """Cache 未命中时调用 provider 并写入 memory + DB。"""
        url = "http://example.com/new.jpg"
        self.engine._caption_cache.clear()
        self.plugin.dao._captions.clear()

        class FakeProv:
            async def text_chat(self, prompt, session_id, image_urls, persist=False):
                class R:
                    completion_text = '{"category":"nsfw","confidence":0.92,"risk_level":"high","reasons":["裸露"],"suggested_action":"delete"}'

                return R()

        self.engine._resolve_provider = lambda pid: FakeProv()

        async def run():
            return await self.engine.caption_image(url, "nsfw prompt", "openai")

        result = asyncio.run(run())
        self.assertIn("nsfw", result)
        self.assertIn(url, self.engine._caption_cache)
        self.assertEqual(self.plugin.dao._captions[url]["source"], "fallback")

    def test_both_channels_enabled_skips_cache(self):
        """NSFW+Promo 同时启用时不走缓存（避免结果混淆）。"""
        self.plugin.cfg.moderation_nsfw_enabled = True
        self.plugin.cfg.moderation_promo_enabled = True
        self.engine._caption_cache.clear()
        self.plugin.dao._captions.clear()
        text_chat_called = []

        class FakeProv:
            async def text_chat(self, prompt, session_id, image_urls, persist=False):
                text_chat_called.append(prompt)

                class R:
                    completion_text = '{"category":"nsfw","confidence":0.9,"risk_level":"high","reasons":[],"suggested_action":"delete"}'

                return R()

        self.engine._resolve_provider = lambda pid: FakeProv()

        async def run():
            return await self.engine.caption_image("http://ex.com/img.jpg", "nsfw prompt", "openai")

        asyncio.run(run())
        self.assertEqual(len(text_chat_called), 1)
        self.assertNotIn("http://ex.com/img.jpg", self.engine._caption_cache)

    def test_db_cached_caption_reused_via_memory(self):
        """DB 中已有 caption 时，写入 memory 并复用，不再调 provider。"""
        url = "http://example.com/reuse.jpg"
        self.engine._caption_cache.clear()
        self.plugin.dao._captions[url] = {
            "caption": '{"category":"nsfw","confidence":0.8,"risk_level":"medium","reasons":[],"suggested_action":"review"}',
            "provider_id": "openai",
            "source": "framework",
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(seconds=3600)).isoformat(),
        }
        resolve_called = []

        orig = self.engine._resolve_provider

        def track(pid):
            resolve_called.append(pid)
            return orig(pid)

        self.engine._resolve_provider = track

        async def run():
            return await self.engine.caption_image(url, "nsfw prompt", "openai")

        result = asyncio.run(run())
        self.assertEqual(resolve_called, [])
        self.assertIn("nsfw", result)
        self.assertEqual(self.engine._caption_cache[url]["source"], "framework")
