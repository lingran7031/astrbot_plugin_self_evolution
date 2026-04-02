"""
Persona Sim Todo - 待办生成层

从 rules.py 里提取的 generate_todos 独立成层。
不存储，不持久化，只负责"根据状态和 active effects 生成 todo"。
"""

import time
from .persona_sim_rules import HOUR
from .persona_sim_types import PersonaEffect, PersonaState, PersonaTodo, TodoType


def make_todos(state: PersonaState, active_effects: list[PersonaEffect]) -> list[PersonaTodo]:
    """根据当前状态和 active effects 生成角色脑内待办（最多5条）。"""
    todos: list[PersonaTodo] = []
    active_ids = {e.effect_id for e in active_effects}

    if "hungry" in active_ids or state.satiety < 40:
        todos.append(
            PersonaTodo(
                todo_type=TodoType.INTERNAL,
                title="想找点吃的",
                reason="satiety 低于阈值",
                priority=7,
                mood_bias=-2.0,
                expires_at=time.time() + 3.0 * HOUR,
            )
        )

    if "lonely" in active_ids or state.social_need > 60:
        todos.append(
            PersonaTodo(
                todo_type=TodoType.SOCIAL,
                title="想和人聊聊天",
                reason="social_need 较高",
                priority=6,
                mood_bias=1.0,
                expires_at=time.time() + 6.0 * HOUR,
            )
        )

    if "low_energy" in active_ids or "sleepy" in active_ids or state.energy < 40:
        todos.append(
            PersonaTodo(
                todo_type=TodoType.INTERNAL,
                title="想休息一下",
                reason="energy 较低",
                priority=8,
                mood_bias=-1.0,
                expires_at=time.time() + 2.0 * HOUR,
            )
        )

    if "curious" in active_ids:
        todos.append(
            PersonaTodo(
                todo_type=TodoType.INTERNAL,
                title="想探索新话题",
                reason="处于好奇状态",
                priority=4,
                mood_bias=2.0,
                expires_at=time.time() + 4.0 * HOUR,
            )
        )

    if "low_mood" in active_ids or state.mood < 40:
        todos.append(
            PersonaTodo(
                todo_type=TodoType.INTERNAL,
                title="想做点让自己开心的事",
                reason="mood 偏低",
                priority=6,
                mood_bias=2.0,
                expires_at=time.time() + 5.0 * HOUR,
            )
        )

    if "wronged" in active_ids:
        todos.append(
            PersonaTodo(
                todo_type=TodoType.INTERNAL,
                title="想把委屈说出来",
                reason="感到委屈",
                priority=5,
                mood_bias=-1.0,
                expires_at=time.time() + 4.0 * HOUR,
            )
        )

    if "relieved" in active_ids:
        todos.append(
            PersonaTodo(
                todo_type=TodoType.INTERNAL,
                title="想保持现在的轻松状态",
                reason="处于轻松状态",
                priority=3,
                mood_bias=1.0,
                expires_at=time.time() + 3.0 * HOUR,
            )
        )

    todos.sort(key=lambda t: t.priority, reverse=True)
    return todos[:5]
