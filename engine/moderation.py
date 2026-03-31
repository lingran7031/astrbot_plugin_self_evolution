"""
群聊内容治理模块（Moderation）

职责：
- 监听群图片消息
- 调用已有图片理解模型进行内容审核（NSFW / 宣传引流）
- 高置信度内容自动撤回
- 梯度处罚（警告 / 禁言 / 踢出）
- 违规记录持久化

不涉及：
- 本地 OCR / NSFW 模型
- 聊天主链路人格逻辑
"""

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from astrbot.api import logger


class ViolationType(Enum):
    NSFW = "nsfw"
    PROMO = "promo"


class RiskLevel(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SuggestedAction(Enum):
    DELETE = "delete"
    REVIEW = "review"
    IGNORE = "ignore"


@dataclass
class ModerationResult:
    category: str
    confidence: float
    risk_level: str
    reasons: list
    suggested_action: str

    @classmethod
    def uncertain(cls) -> "ModerationResult":
        return cls(
            category="uncertain",
            confidence=0.0,
            risk_level="low",
            reasons=["模型响应解析失败或非 JSON"],
            suggested_action="ignore",
        )


@dataclass
class ModerationEvidence:
    group_id: str
    user_id: str
    message_id: str
    image_url: str
    category: str
    confidence: float
    risk_level: str
    reasons: list
    suggested_action: str
    provider_id: str
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "group_id": self.group_id,
            "user_id": self.user_id,
            "message_id": self.message_id,
            "image_url": self.image_url,
            "category": self.category,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "reasons": self.reasons,
            "suggested_action": self.suggested_action,
            "provider_id": self.provider_id,
            "created_at": self.created_at,
        }


class ModerationEngine:
    NSFW_PROMPT = """你是一个严格的内容安全审核助手。请仔细分析这张图片，判断其是否包含以下内容：

1. 裸露或性暗示（任何年龄层的裸露身体、蕾丝情节、性暗示姿势、暴露穿着等）
2. 色情广告（带有性暗示的产品推广、服务宣传等）
3. 擦边内容（刻意展示身体敏感部位、挑逗性姿态等）

请严格按以下 JSON 格式输出，不要输出任何其他内容：

{
  "category": "nsfw",
  "confidence": 0.0到1.0之间的数字,
  "risk_level": "high或medium或low",
  "reasons": ["具体证据描述1", "具体证据描述2"],
  "suggested_action": "delete或review或ignore"
}

判断标准：
- confidence >= 0.85 且 risk_level = high 时，suggested_action 必须为 delete
- confidence >= 0.60 或有任何明显证据时，risk_level 至少为 medium
- 不确定时优先返回 uncertain"""

    PROMO_PROMPT = """你是一个严格的反引流审核助手。请仔细分析这张图片，判断其是否包含以下内容：

1. 二维码（任何二维码，包括群二维码、个人二维码、收款二维码等）
2. 群号或拉群信息（"加群"、"入群"、"群号XXX"等）
3. 联系方式（微信号、手机号、QQ号等）
4. 引流文案（"加我"、"私信"、"联系我"、"扫码"等）
5. 博彩/兼职/黄网导流（赌博网站、刷单兼职、成人内容导流等）
6. 宣传海报（活动宣传、返利宣传、裂变海报等）

请严格按以下 JSON 格式输出，不要输出任何其他内容：

{
  "category": "promo",
  "confidence": 0.0到1.0之间的数字,
  "risk_level": "high或medium或low",
  "reasons": ["具体证据描述1", "具体证据描述2"],
  "suggested_action": "delete或review或ignore"
}

判断标准：
- 出现二维码 + 引流文案 同时存在 → risk_level 必须为 high，confidence >= 0.90
- 任何明确的联系方式或博彩/黄网内容 → risk_level 必须为 high
- 仅二维码但无明确引流意图 → confidence 可适当降低
- 不确定时优先返回 uncertain"""

    def __init__(self, plugin):
        self.plugin = plugin
        self.cfg = plugin.cfg
        self._caption_cache = {}
        self._caption_cache_ttl = 3600

    def _get_image_caption_config(self) -> tuple[Optional[str], Optional[str]]:
        """解析图片理解 provider 配置。

        优先级：
        1. provider_ltm_settings.image_caption_provider_id（群聊专用）
        2. provider_settings.default_image_caption_provider_id（全局默认）

        Returns:
            (provider_id, caption_prompt) 或 (None, None) 表示未配置
        """
        try:
            umo = None
            cfg = self.plugin.context.get_config(umo=umo)

            prov_id = cfg.get("provider_ltm_settings", {}).get("image_caption_provider_id", "")
            if not prov_id:
                prov_id = cfg.get("provider_settings", {}).get("default_image_caption_provider_id", "")

            if not prov_id:
                logger.debug("[Moderation] 未配置图片理解模型，治理功能不可用")
                return None, None

            prompt = cfg.get("provider_settings", {}).get("image_caption_prompt", "")
            return prov_id, prompt
        except Exception as e:
            logger.warning(f"[Moderation] 获取图片理解配置失败: {e}")
            return None, None

    def _resolve_provider(self, provider_id: str):
        """根据 ID 解析 provider，找不到则用默认 provider。"""
        try:
            if provider_id:
                prov = self.plugin.context.get_provider_by_id(provider_id)
                if prov:
                    return prov
            prov = self.plugin.context.get_using_provider()
            if prov:
                return prov
        except Exception as e:
            logger.warning(f"[Moderation] 解析 provider 失败: {e}")
        return None

    async def caption_image(self, image_url: str, governance_prompt: str, provider_id: str) -> str:
        """调用图片理解模型获取描述，优先走 caption cache。

        Caption 复用顺序（不论双通道是否同时启用）：
        1. memory cache hit → 直接返回
        2. DB cache hit (framework caption) → 写入 memory 并返回
        3. 都未命中 → 调用 provider 独立识图
           - 单路模式：写回 memory + DB（避免 NSFW/Promo 结果互相污染）
           - 双通道模式：不缓存，每次独立识图
        """
        import time

        if self.cfg.moderation_prefer_caption_reuse:
            now = time.time()
            cached = self._caption_cache.get(image_url)
            if cached and cached.get("expires_at", 0) > now:
                logger.info(f"[Moderation] Caption cache hit (memory): {image_url[:50]}")
                return cached["caption"]

            db_cached = await self.plugin.dao.get_moderation_caption(image_url)
            if db_cached:
                db_cached["expires_at"] = now + self._caption_cache_ttl
                self._caption_cache[image_url] = db_cached
                logger.info(f"[Moderation] Caption reuse ({db_cached['source']}): {image_url[:50]}")
                return db_cached["caption"]

        prov = self._resolve_provider(provider_id)
        if not prov:
            raise RuntimeError("无可用的图片理解 provider")

        try:
            response = await prov.text_chat(
                prompt=governance_prompt,
                session_id="moderation",
                image_urls=[image_url],
                persist=False,
            )
            caption = response.completion_text

            if self.cfg.moderation_prefer_caption_reuse and not (
                self.cfg.moderation_nsfw_enabled and self.cfg.moderation_promo_enabled
            ):
                source = "fallback"
                expires_at = time.time() + self._caption_cache_ttl
                cache_entry = {
                    "caption": caption,
                    "provider_id": provider_id,
                    "source": source,
                    "expires_at": expires_at,
                }
                self._caption_cache[image_url] = cache_entry
                await self.plugin.dao.upsert_moderation_caption(
                    image_url=image_url,
                    caption=caption,
                    provider_id=provider_id,
                    source=source,
                    ttl_seconds=self._caption_cache_ttl,
                )
                logger.info(f"[Moderation] Fallback caption: {image_url[:50]} source={source}")

            return caption
        except Exception as e:
            logger.warning(f"[Moderation] 图片理解调用失败: {e}")
            raise

    def _parse_result(self, raw_text: str) -> ModerationResult:
        """从模型输出中解析 JSON。失败返回 uncertain。"""
        try:
            text = raw_text.strip()
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return ModerationResult.uncertain()
            data = json.loads(match.group(0))
            return ModerationResult(
                category=str(data.get("category", "uncertain")),
                confidence=float(data.get("confidence", 0.0)),
                risk_level=str(data.get("risk_level", "low")),
                reasons=list(data.get("reasons", [])),
                suggested_action=str(data.get("suggested_action", "ignore")),
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.debug(f"[Moderation] JSON 解析失败: {e}, raw={raw_text[:100]}")
            return ModerationResult.uncertain()

    async def moderate(
        self,
        image_url: str,
        group_id: str,
        user_id: str,
        message_id: str,
    ) -> ModerationEvidence:
        """对单张图片执行治理审核，按子开关分流。"""
        prov_id, _ = self._get_image_caption_config()
        if not prov_id:
            raise RuntimeError("未配置图片理解模型，治理功能不可用")

        logger.info(f"[Moderation] 开始审核: group={group_id} user={user_id} msg={message_id} url={image_url[:50]}")

        nsfw_result, promo_result = None, None

        if self.cfg.moderation_nsfw_enabled:
            try:
                nsfw_raw = await self.caption_image(image_url, self.NSFW_PROMPT, prov_id)
                nsfw_result = self._parse_result(nsfw_raw)
                logger.debug(
                    f"[Moderation] NSFW结果: cat={nsfw_result.category} conf={nsfw_result.confidence} "
                    f"risk={nsfw_result.risk_level} action={nsfw_result.suggested_action}"
                )
            except Exception as e:
                logger.warning(f"[Moderation] NSFW 审核异常: {e}")

        if self.cfg.moderation_promo_enabled:
            try:
                promo_raw = await self.caption_image(image_url, self.PROMO_PROMPT, prov_id)
                promo_result = self._parse_result(promo_raw)
                logger.debug(
                    f"[Moderation] Promo结果: cat={promo_result.category} conf={promo_result.confidence} "
                    f"risk={promo_result.risk_level} action={promo_result.suggested_action}"
                )
            except Exception as e:
                logger.warning(f"[Moderation] Promo 审核异常: {e}")

        if not nsfw_result and not promo_result:
            logger.warning("[Moderation] 所有审核通道均未启用或全部失败，返回 uncertain")
            final = ModerationResult.uncertain()
        else:
            final = self._merge_results(nsfw_result, promo_result)

        logger.info(
            f"[Moderation] 最终结果: cat={final.category} conf={final.confidence} "
            f"risk={final.risk_level} reasons={final.reasons}"
        )

        return ModerationEvidence(
            group_id=group_id,
            user_id=user_id,
            message_id=message_id,
            image_url=image_url,
            category=final.category,
            confidence=final.confidence,
            risk_level=final.risk_level,
            reasons=final.reasons,
            suggested_action=final.suggested_action,
            provider_id=prov_id,
        )

    def _merge_results(self, nsfw: Optional[ModerationResult], promo: Optional[ModerationResult]) -> ModerationResult:
        """取风险更高的一侧作为最终结果。"""

        def risk_score(r: Optional[ModerationResult]) -> float:
            if not r or r.category == "uncertain":
                return -1.0
            level_map = {"high": 3.0, "medium": 2.0, "low": 1.0}
            return level_map.get(r.risk_level, 0.0) * r.confidence

        nscore = risk_score(nsfw)
        pscore = risk_score(promo)

        if nscore >= pscore and nsfw and nsfw.category != "uncertain":
            return nsfw
        if promo and promo.category != "uncertain":
            return promo
        return ModerationResult.uncertain()

    def _risk_score_for_escalate(self, evidence: ModerationEvidence) -> float:
        """计算evidence的风险分数，用于确定最严重结果。"""
        if evidence.category == "uncertain":
            return -1.0
        level_map = {"high": 3.0, "medium": 2.0, "low": 1.0}
        return level_map.get(evidence.risk_level, 0.0) * evidence.confidence

    async def delete_message(self, group_id: str, message_id: str) -> bool:
        """调用 NapCat delete_msg 撤回消息。"""
        try:
            platform = self.plugin.context.platform_manager.platform_insts[0]
            bot = platform.get_client()
            await bot.call_action("delete_msg", message_id=int(message_id))
            logger.info(f"[Moderation] 撤回成功: msg={message_id}")
            return True
        except Exception as e:
            logger.warning(f"[Moderation] 撤回失败: msg={message_id}, error={e}")
            return False

    async def set_group_ban(self, group_id: str, user_id: str, duration_seconds: int) -> bool:
        """调用 NapCat set_group_ban 禁言用户。"""
        try:
            platform = self.plugin.context.platform_manager.platform_insts[0]
            bot = platform.get_client()
            await bot.call_action(
                "set_group_ban",
                group_id=int(group_id),
                user_id=int(user_id),
                duration=duration_seconds,
            )
            logger.info(f"[Moderation] 禁言成功: group={group_id} user={user_id} duration={duration_seconds}s")
            return True
        except Exception as e:
            logger.warning(f"[Moderation] 禁言失败: group={group_id} user={user_id}, error={e}")
            return False

    async def set_group_kick(self, group_id: str, user_id: str) -> bool:
        """调用 NapCat set_group_kick 踢出用户。"""
        try:
            platform = self.plugin.context.platform_manager.platform_insts[0]
            bot = platform.get_client()
            await bot.call_action(
                "set_group_kick",
                group_id=int(group_id),
                user_id=int(user_id),
            )
            logger.info(f"[Moderation] 踢出成功: group={group_id} user={user_id}")
            return True
        except Exception as e:
            logger.warning(f"[Moderation] 踢出失败: group={group_id} user={user_id}, error={e}")
            return False

    def _is_high_confidence_delete(self, result: ModerationResult) -> bool:
        """判断是否达到自动删除阈值，按 category 使用各自配置的置信度阈值。"""
        if result.category == "uncertain":
            return False
        threshold = (
            self.cfg.moderation_nsfw_delete_confidence
            if result.category == "nsfw"
            else self.cfg.moderation_promo_delete_confidence
        )
        if result.risk_level == "high" and result.confidence >= threshold:
            return True
        if result.risk_level == "medium" and result.confidence >= threshold + 0.05:
            return True
        return False

    def _direct_kick(self, violation_type: str, risk_level: str, confidence: float, reasons: list) -> bool:
        """判断是否直接踢出（不看24h累计次数）。"""
        reasons = reasons or []
        qr_and_promo = "二维码" in reasons and any(
            kw in "".join(reasons) for kw in ("加群", "入群", "联系", "扫码", "兼职", "博彩", "黄网")
        )
        threshold = (
            self.cfg.moderation_nsfw_delete_confidence
            if violation_type == ViolationType.NSFW.value
            else self.cfg.moderation_promo_delete_confidence
        )
        if violation_type == ViolationType.PROMO.value and (
            qr_and_promo or (risk_level == "high" and confidence >= threshold)
        ):
            return True
        if violation_type == ViolationType.NSFW.value and risk_level == "high" and confidence >= threshold:
            return True
        return False

    def _should_escalate(
        self,
        violation_type: str,
        count_24h: int,
        risk_level: str = "low",
        confidence: float = 0.0,
        reasons: list = None,
    ) -> tuple[str, Optional[int]]:
        """根据违规类型、24h窗口次数决定处罚等级（累计阈值）。

        直接升级（不看次数）由 _direct_kick() 判断。

        Returns:
            (action_name, action_param) action_name ∈ {warn, ban, kick, record}
        """
        reasons = reasons or []

        thresholds = {
            ViolationType.NSFW.value: (
                self.cfg.moderation_warn_threshold,
                self.cfg.moderation_ban_threshold,
                self.cfg.moderation_kick_threshold,
            ),
            ViolationType.PROMO.value: (
                self.cfg.moderation_promo_warn_threshold,
                self.cfg.moderation_promo_ban_threshold,
                self.cfg.moderation_promo_kick_threshold,
            ),
        }
        t = thresholds.get(violation_type, (1, 2, 3))
        if count_24h >= t[2]:
            return "kick", None
        if count_24h >= t[1]:
            ban_durations = {
                ViolationType.NSFW.value: 300,
                ViolationType.PROMO.value: 600,
            }
            return "ban", ban_durations.get(violation_type, 300)
        if count_24h >= t[0]:
            return "warn", None
        return "record", None
