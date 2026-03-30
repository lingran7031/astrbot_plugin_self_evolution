import time
from dataclasses import dataclass

from astrbot.api import logger
from astrbot.api.all import AstrMessageEvent

from .engagement_planner import EngagementPlanner
from .engagement_executor import EngagementExecutor
from .reply_recorder import ReplyRecorder
from .reply_state import BotMessageKind, ConversationMomentum
from .social_state import EngagementLevel, GroupSocialState, SceneType
from .event_context import extract_interaction_context


_ACTIVE_WINDOW_SECONDS = 30.0
_MESSAGE_WINDOW_SECONDS = 120.0


@dataclass
class ActiveScopeStore:
    _data: dict[str, dict[str, float]] | None = None

    def __post_init__(self):
        self._data = {}

    def record(self, scope_id: str, user_id: str, now: float | None = None):
        if now is None:
            now = time.time()
        if scope_id not in self._data:
            self._data[scope_id] = {}
        self._data[scope_id][user_id] = now + _ACTIVE_WINDOW_SECONDS

    def get_active_scopes(self) -> list[str]:
        now = time.time()
        result = []
        for scope_id, users in self._data.items():
            expired = [uid for uid, end in users.items() if now > end]
            for uid in expired:
                del users[uid]
            if users:
                result.append(scope_id)
            else:
                del self._data[scope_id]
        return result


class EavesdroppingEngine:
    def __init__(self, plugin):
        self.plugin = plugin
        self._active_scopes = ActiveScopeStore()
        self._recorder = ReplyRecorder(plugin)

    def record_activity(self, scope_id: str, user_id: str, now: float | None = None):
        self._active_scopes.record(scope_id, user_id, now)

    def get_active_scopes(self) -> list[str]:
        return self._active_scopes.get_active_scopes()

    async def sync_framework_reply_state(self, scope_id: str, level: str = "full") -> bool:
        """由框架正常回复链路调用，同步社交模块冷却状态。"""
        state_dict = await self.plugin.dao.get_engagement_state(scope_id)
        if not state_dict:
            return False
        momentum = ConversationMomentum.from_dict(state_dict)
        now = time.time()
        if not momentum.is_wave_active(now, _MESSAGE_WINDOW_SECONDS):
            momentum.reset_wave(now)
        await self._recorder.record_framework_normal(scope_id, momentum, level=level)
        return True

    async def check_engagement(self, group_id: str) -> bool:
        """主动参与入口 - 定时任务调度用"""
        if group_id in self.plugin._shut_until_by_group:
            if time.time() < self.plugin._shut_until_by_group[group_id]:
                return False
        try:
            state_dict = await self.plugin.dao.get_engagement_state(group_id)
            now = time.time()
            momentum = (
                ConversationMomentum.from_dict(state_dict) if state_dict else ConversationMomentum(scope_id=group_id)
            )

            if not momentum.is_wave_active(now, _MESSAGE_WINDOW_SECONDS):
                momentum.reset_wave(now)

            if momentum.bot_has_spoken_in_current_wave:
                return False

            if momentum.new_user_message_after_bot:
                return False

            planner = EngagementPlanner(self.plugin)
            executor = EngagementExecutor(self.plugin, planner)

            state = GroupSocialState(
                scope_id=group_id,
                last_message_time=momentum.last_message_time or (now - 60),
                last_bot_message_time=momentum.last_bot_message_at,
                last_seen_message_seq=momentum.last_seen_message_seq,
                scene=SceneType.CASUAL,
                message_count_window=momentum.message_count_window,
                question_count_window=momentum.question_count_window,
                emotion_count_window=momentum.emotion_count_window,
                consecutive_bot_replies=momentum.consecutive_bot_replies,
            )

            computed = planner.compute_scene_windows([], state)
            state.mention_bot_recently = computed["mention_bot_recently"]

            eligibility = planner.check_eligibility(
                state,
                cooldown_seconds=self.plugin.cfg.interject_cooldown,
                min_new_messages=1,
            )
            if not eligibility.allowed:
                return False

            plan = planner.plan_engagement(state, eligibility, has_mention=False, has_reply_to_bot=False)
            if plan.level == EngagementLevel.IGNORE:
                return False

            result = await executor.execute(plan, state, trigger_text="")

            if result.executed:
                kind = BotMessageKind.ACTIVE if plan.level == EngagementLevel.FULL else BotMessageKind.STICKER
                momentum.scene_type = plan.scene.value
                momentum.bot_spoke(time.time(), kind, start_new_wave=True)
                await self._recorder.record(group_id, executed=True, momentum=momentum, level=plan.level.value)
                logger.info(f"[ActiveEngagement] 群 {group_id}: executed {result.action}")
                return True

            return False
        except Exception as e:
            logger.warning(f"[ActiveEngagement] 群 {group_id} 检查失败: {e}", exc_info=True)
            return False

    async def process_passive_engagement(self, event: AstrMessageEvent):
        """被动互动唯一入口"""
        group_id = event.get_group_id()
        if not group_id:
            return

        try:
            now = time.time()
            user_id = str(event.get_user_id()) if hasattr(event, "get_user_id") else ""
            sender_name = event.get_sender_name() if hasattr(event, "get_sender_name") else "群成员"
            if user_id:
                self.record_activity(group_id, user_id, now)

            state_dict = await self.plugin.dao.get_engagement_state(group_id)
            momentum = (
                ConversationMomentum.from_dict(state_dict) if state_dict else ConversationMomentum(scope_id=group_id)
            )

            if not momentum.is_wave_active(now, _MESSAGE_WINDOW_SECONDS):
                momentum.reset_wave(now)

            momentum.user_message_arrived(now)
            if momentum.bot_has_spoken_in_current_wave:
                momentum.new_user_after_bot()

            is_at = event.get_extra("is_at", False)
            has_reply = event.get_extra("has_reply", False)
            has_mention = is_at or has_reply

            if momentum.bot_has_spoken_in_current_wave and has_mention:
                return

            msg_text = event.message_str or ""
            if not msg_text.strip():
                msg_text = "[图片]"

            state = GroupSocialState(
                scope_id=group_id,
                last_message_time=momentum.last_message_time or (now - 60),
                last_bot_message_time=momentum.last_bot_message_at,
                last_seen_message_seq=momentum.last_seen_message_seq,
                scene=SceneType.CASUAL,
                message_count_window=momentum.message_count_window,
                question_count_window=momentum.question_count_window,
                emotion_count_window=momentum.emotion_count_window,
                consecutive_bot_replies=momentum.consecutive_bot_replies,
            )

            messages_for_scene = [{"text": msg_text, "message": []}]
            planner = EngagementPlanner(self.plugin)
            executor = EngagementExecutor(self.plugin, planner)

            state.message_count_window = max(int(state.message_count_window), 0) + 1
            computed = planner.compute_scene_windows(messages_for_scene, state)
            state.question_count_window = max(int(state.question_count_window), 0) + computed["question_count_window"]
            state.emotion_count_window = max(int(state.emotion_count_window), 0) + computed["emotion_count_window"]
            state.mention_bot_recently = computed["mention_bot_recently"]

            interaction = extract_interaction_context(
                event.get_messages(),
                persona_name=getattr(self.plugin, "persona_name", "黑塔"),
                bot_id=self.plugin._get_bot_id(),
            )
            quoted_info = interaction.get("quoted_info", "") or ""
            at_info = interaction.get("at_info", "") or ""

            momentum.message_count_window = state.message_count_window
            momentum.question_count_window = state.question_count_window
            momentum.emotion_count_window = state.emotion_count_window

            eligibility = planner.check_eligibility(
                state,
                cooldown_seconds=self.plugin.cfg.interject_cooldown,
                min_new_messages=1,
            )
            if not eligibility.allowed:
                logger.debug(
                    f"[PassiveEngagement] scope={group_id} eligible=no reason={eligibility.reason_code} {eligibility.reason_text}"
                )
                momentum.consecutive_bot_replies = 0
                await self._recorder.record(group_id, executed=False, momentum=momentum)
                return

            plan = planner.plan_engagement(state, eligibility, has_mention=has_mention, has_reply_to_bot=has_reply)
            if plan.level == EngagementLevel.IGNORE:
                logger.debug(f"[PassiveEngagement] scope={group_id} level=IGNORE scene={plan.scene.value}")
                momentum.consecutive_bot_replies = 0
                await self._recorder.record(group_id, executed=False, momentum=momentum)
                return

            logger.debug(f"[PassiveEngagement] scope={group_id} level={plan.level.value} scene={plan.scene.value}")

            result = await executor.execute(
                plan,
                state,
                trigger_text=msg_text,
                user_id=user_id,
                sender_name=sender_name,
                quoted_info=quoted_info,
                at_info=at_info,
            )

            momentum.scene_type = plan.scene.value
            momentum.last_seen_message_seq = state.last_seen_message_seq
            if result.executed:
                momentum.bot_spoke(time.time(), BotMessageKind.PASSIVE, start_new_wave=False)
            await self._recorder.record(
                group_id,
                executed=result.executed,
                momentum=momentum,
                level=result.level.value if result.executed else None,
            )

            if result.executed:
                logger.info(f"[PassiveEngagement] scope={group_id} executed {result.action} ({result.level.value})")

        except Exception as e:
            logger.warning(f"[PassiveEngagement] 群 {group_id} 处理失败: {e}", exc_info=True)
