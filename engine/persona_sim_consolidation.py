"""
Persona Sim Consolidation - 低频固化层

每天睡眠时段（或手动触发）跑一次。

职责：
- 读取当天所有 persona_events
- 分析情绪轨迹 / effect 出现频率 / 互动质量
- 生成「人格经历日结」写入 persona_events (type=consolidated)
- 可选：轻微调整次日开始状态（persona drift）
- 可选：写入长期人格记忆（session_memory_store 的 private scope）

不做的：
- 不清空当天事件（保留原始记录）
- 不做复杂人格漂移（一期只做轻微 mood nudge）
"""

import logging
import time
from datetime import datetime, timedelta

from .persona_sim_types import EventType, PersonaEvent

logger = logging.getLogger("astrbot")

DRIFT_MAX = 5.0


class PersonaSimConsolidator:
    def __init__(self, plugin):
        self.plugin = plugin
        self._dao = getattr(plugin, "dao", None)
        self._memory_store = getattr(plugin, "memory_store", None)

    async def consolidate_scope(self, scope_id: str, force_date: str | None = None) -> str:
        """对指定 scope 执行日结。返回总结文字。"""
        if not self._dao:
            return "DAO 不可用"

        now = time.time()
        date_str = force_date or datetime.now().strftime("%Y-%m-%d")

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return f"日期格式错误: {date_str}，应为 YYYY-MM-DD"

        day_start = datetime.combine(target_date, datetime.min.time()).timestamp()
        day_end = day_start + 86400

        event_rows = await self._dao.get_all_persona_events_since(scope_id, day_start)
        if not event_rows:
            logger.info(f"[Consolidation] scope={scope_id} date={date_str} 无事件，跳过")
            return f"scope={scope_id} date={date_str} 无事件记录，跳过"

        events = [
            PersonaEvent(
                event_type=EventType(e.get("event_type", "natural")),
                summary=e.get("summary", ""),
                causes=e.get("causes", "").split("|") if e.get("causes") else [],
                effects_applied=e.get("effects_applied", "").split("|") if e.get("effects_applied") else [],
                timestamp=float(e.get("timestamp", 0)),
            )
            for e in event_rows
        ]

        state_rows = await self._dao.get_persona_state(scope_id)
        current_state = None
        if state_rows:
            current_state = {
                "energy": float(state_rows["energy"]),
                "mood": float(state_rows["mood"]),
                "social_need": float(state_rows["social_need"]),
                "satiety": float(state_rows["satiety"]),
            }

        summary_parts = self._analyze_day(events, current_state, date_str)
        summary_text = self._format_summary(summary_parts, date_str)

        summary_event = PersonaEvent(
            event_type=EventType.CONSOLIDATED,
            summary=summary_text,
            causes=[f"events_count={len(events)}"],
            effects_applied=[],
            timestamp=now,
        )
        await self._dao.add_persona_event(scope_id, summary_event)

        drift = self._calc_drift(summary_parts)
        if drift != 0 and current_state:
            new_mood = current_state["mood"] + drift
            new_mood = max(10.0, min(90.0, new_mood))
            logger.info(
                f"[Consolidation] scope={scope_id} mood drift: {current_state['mood']:.1f} -> {new_mood:.1f} (drift={drift:+.1f})"
            )
            current_state["mood"] = new_mood
            from .persona_sim_types import PersonaState

            new_state = PersonaState(
                energy=current_state["energy"],
                mood=current_state["mood"],
                social_need=current_state["social_need"],
                satiety=current_state["satiety"],
                last_tick_at=now,
                last_interaction_at=current_state.get("last_interaction_at", now),
            )
            await self._dao.upsert_persona_state(scope_id, new_state)

        if self._memory_store:
            await self._write_long_term_memory(scope_id, summary_text, date_str)

        logger.info(f"[Consolidation] scope={scope_id} date={date_str} 完成: {summary_text[:80]}")
        return f"人格日结完成 [{date_str}]\n{summary_text}"

    async def get_today_summary(self, scope_id: str) -> str:
        """只读今天的总结，不触发 drift。"""
        if not self._dao:
            return "DAO 不可用"
        date_str = datetime.now().strftime("%Y-%m-%d")
        day_start = datetime.combine(datetime.strptime(date_str, "%Y-%m-%d").date(), datetime.min.time()).timestamp()
        event_rows = await self._dao.get_all_persona_events_since(scope_id, day_start)
        if not event_rows:
            return f"[{date_str}] 暂无记录"
        state_rows = await self._dao.get_persona_state(scope_id)
        current_state = None
        if state_rows:
            current_state = {
                "energy": float(state_rows["energy"]),
                "mood": float(state_rows["mood"]),
                "social_need": float(state_rows["social_need"]),
                "satiety": float(state_rows["satiety"]),
            }
        events = [
            PersonaEvent(
                event_type=EventType(e.get("event_type", "natural")),
                summary=e.get("summary", ""),
                causes=e.get("causes", "").split("|") if e.get("causes") else [],
                effects_applied=e.get("effects_applied", "").split("|") if e.get("effects_applied") else [],
                timestamp=float(e.get("timestamp", 0)),
            )
            for e in event_rows
        ]
        summary_parts = self._analyze_day(events, current_state, date_str)
        return self._format_summary(summary_parts, date_str)

    def _analyze_day(
        self,
        events: list[PersonaEvent],
        state: dict | None,
        date_str: str,
    ) -> dict:
        effect_counter: dict[str, int] = {}
        natural_count = 0
        interaction_count = 0
        trigger_count = 0

        for ev in events:
            if ev.event_type == EventType.NATURAL:
                natural_count += 1
            elif ev.event_type == EventType.INTERACTION:
                interaction_count += 1
            elif ev.event_type == EventType.EFFECT_TRIGGER:
                trigger_count += 1
                for eff in ev.effects_applied:
                    effect_counter[eff] = effect_counter.get(eff, 0) + 1

        dominant_effect = max(effect_counter, key=effect_counter.get) if effect_counter else None
        dominant_count = effect_counter.get(dominant_effect, 0) if dominant_effect else 0

        mood_desc = ""
        energy_desc = ""
        if state:
            mood = state.get("mood", 50)
            energy = state.get("energy", 50)
            if mood >= 70:
                mood_desc = "心情愉悦"
            elif mood >= 50:
                mood_desc = "心情平稳"
            elif mood >= 30:
                mood_desc = "心情低落"
            else:
                mood_desc = "情绪低迷"
            if energy >= 70:
                energy_desc = "精力充沛"
            elif energy >= 50:
                energy_desc = "状态正常"
            elif energy >= 30:
                energy_desc = "有些疲惫"
            else:
                energy_desc = "非常疲倦"

        return {
            "date": date_str,
            "event_count": len(events),
            "natural_count": natural_count,
            "interaction_count": interaction_count,
            "effect_count": trigger_count,
            "dominant_effect": dominant_effect,
            "dominant_count": dominant_count,
            "mood_desc": mood_desc,
            "energy_desc": energy_desc,
        }

    def _format_summary(self, parts: dict, date_str: str) -> str:
        lines = [
            f"【人格日结 {date_str}】",
            f"共记录 {parts['event_count']} 条事件",
        ]
        if parts["interaction_count"] > 0:
            lines.append(f"互动 {parts['interaction_count']} 次")
        if parts["effect_count"] > 0:
            lines.append(f"状态变化 {parts['effect_count']} 次")
        if parts["dominant_effect"]:
            lines.append(f"主要状态：{parts['dominant_effect']}（出现 {parts['dominant_count']} 次）")
        if parts["mood_desc"]:
            lines.append(f"今日情绪：{parts['mood_desc']}")
        if parts["energy_desc"]:
            lines.append(f"精力状态：{parts['energy_desc']}")
        return "\n".join(lines)

    def _calc_drift(self, parts: dict) -> float:
        mood_map = {
            "情绪低迷": -3.0,
            "心情低落": -1.5,
            "心情平稳": 0.0,
            "心情愉悦": 1.5,
            "非常疲倦": -2.0,
            "有些疲惫": -1.0,
            "状态正常": 0.0,
            "精力充沛": 1.5,
        }
        base = mood_map.get(parts["mood_desc"], 0.0)
        if parts["interaction_count"] >= 5:
            base += 1.0
        elif parts["interaction_count"] == 0 and parts["natural_count"] > 0:
            base -= 1.0
        if abs(base) < 0.5:
            return 0.0
        return max(-DRIFT_MAX, min(DRIFT_MAX, base))

    async def _write_long_term_memory(self, scope_id: str, summary: str, date_str: str):
        """写入长期人格记忆（private scope）。"""
        if not self._memory_store:
            return
        try:
            private_scope = f"private_persona_{scope_id}"
            memory_json = f'{{"type":"persona_daily_summary","date":"{date_str}","summary":"{summary.replace(chr(34), chr(34) + chr(34))}"}}'
            await self._memory_store.save_session_event(
                private_scope,
                {
                    "content": f"[人格日结 {date_str}] {summary}",
                    "source": "persona_sim_consolidation",
                    "date": date_str,
                },
            )
            logger.debug(f"[Consolidation] 长期记忆已写入 private_scope={private_scope}")
        except Exception as e:
            logger.warning(f"[Consolidation] 写入长期记忆失败: {e}")
