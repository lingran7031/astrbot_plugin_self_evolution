# 自我进化

`astrbot_plugin_self_evolution` 是一个给 AstrBot 使用的长期能力增强插件，适配群聊、私聊和 NapCat 消息结构。

它的目标不是只多几个命令，而是让 Bot 逐步具备更稳定的连续性：

- 用户画像与长期记忆
- 会话事件与每日总结
- 反思与自我校准
- 群聊上下文注入
- 主动与被动社交参与
- Persona Sim 人格生活模拟
- 图片 caption 与群聊图片审核
- 情感积分、SAN、表情包、群菜单等行为增强

## 交流

- QQ 群：`1087272376`
- 群名：`self_evolution 插件交流反馈群`

## 功能概览

### 记忆与画像

- 维护用户画像，记录身份、偏好、特征和补充备注
- 维护会话事件、每日总结与范围隔离的知识库
- 支持按群聊 / 私聊自动隔离 scope
- 支持长期知识库召回与 Prompt 注入

相关文件：

- [main.py](/D:/skills/GD/astrbot_plugin_self_evolution/main.py)
- [profile.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/profile.py)
- [profile_summary_service.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/profile_summary_service.py)
- [memory_router.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/memory_router.py)
- [memory_query_service.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/memory_query_service.py)
- [session_memory_store.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/session_memory_store.py)
- [session_memory_summarizer.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/session_memory_summarizer.py)

### 社交与行为

- 支持主动插话、被动回应、场景判断和输出约束
- 支持情感积分自动更新
- 支持 SAN 状态调节
- 支持表情包能力与群菜单推荐

相关文件：

- [eavesdropping.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/eavesdropping.py)
- [social_state.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/social_state.py)
- [engagement_planner.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/engagement_planner.py)
- [reply_executor.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/reply_executor.py)
- [output_guard.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/output_guard.py)
- [affinity.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/affinity.py)
- [san.py](/D:/skills/GD/astrbot_plugin_self_evolution/cognition/san.py)
- [entertainment.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/entertainment.py)
- [meal_store.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/meal_store.py)

### Persona Sim 人格生活模拟

插件现在内置了一套轻量的人格生活模拟层，用来增强“她在你没找她时也在变化”的连续感。

当前能力包括：

- 维护每个 scope 的人格状态：`energy`、`mood`、`social_need`、`satiety`
- 基于时间差做 delta 推演，不需要后台常驻线程
- 根据状态触发短期 Buff / Debuff，例如疲惫、低落、孤独、饥饿等
- 生成角色当前脑内待办，例如想休息、想聊天、想找点吃的
- 将人格状态以极短片段注入 Prompt
- 温和影响群聊参与意愿，但不取代现有 planner
- 在低频调度中做 persona consolidation，生成当日人格经历摘要

设计边界：

- Persona Sim 不替代 SAN
- Persona Sim 不替代 Affinity
- Persona Sim 不污染 `session_event`
- Persona Sim 的夜间固化写入独立 `persona_episodes`

相关文件：

- [persona_sim_types.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/persona_sim_types.py)
- [persona_sim_rules.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/persona_sim_rules.py)
- [persona_sim_engine.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/persona_sim_engine.py)
- [persona_sim_injection.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/persona_sim_injection.py)
- [persona_sim_consolidation.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/persona_sim_consolidation.py)

### 人格进化

- 提供管理员审核流
- 支持查看、批准、拒绝、清空、统计

相关文件：

- [persona.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/persona.py)

### 图片 caption 与群聊图片审核

插件内置了一条独立于 AstrBot 框架临时 caption 的图片理解与审核链：

- 监听 AstrBot + NapCat 消息事件
- 抽取主消息、回复、转发里的图片与可用视频封面
- 调用 AstrBot 已配置的图片理解 provider 生成中立 caption
- 将 caption 写入独立 cache，避免重复识图
- 基于 caption 做 NSFW / Promo 二次推定
- 输出结构化审核结果并进入 enforcement

这条链的原则很简单：

- caption 只表示“图里是什么”
- 审核结果表示“这算不算违规”
- caption cache 不存审核 JSON
- 执行层支持 `dry-run` 和真实执行切换

当前执行层能力：

- `ignore`：只记录日志
- `review`：记录 evidence，并按配置策略进入自动处理
- `delete`：删除消息并按累计违规次数升级处罚

相关文件：

- [media_extractor.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/media_extractor.py)
- [caption_service.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/caption_service.py)
- [moderation_classifier.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/moderation_classifier.py)
- [moderation_enforcer.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/moderation_enforcer.py)
- [moderation_executor.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/moderation_executor.py)

## 最小安装步骤

1. 在 AstrBot 后台安装 `astrbot_plugin_self_evolution`
2. 创建一个基础知识库，并把名字设置给 `memory_kb_name`
3. 确保 AstrBot 已配置可用模型
4. 如需启用图片审核，请确保已配置可用的图片理解 provider
5. 使用 NapCat 作为消息协议后端
6. 重载插件或重启 AstrBot

## 命令

### 用户命令

- `/system help`
- `/system version`
- `/reflect`
- `/affinity show`
- `/san show`
- `/今日老婆`
- `/addmeal <菜名>` - 添加菜品到群菜单
- `/delmeal <菜名>|all` - 删除菜品（all 仅管理员）
- `/banuseraddmeal <用户ID>` - 禁止指定用户添加菜品（仅管理员）
- `/unbanuseraddmeal <用户ID>` - 解除禁止（仅管理员）
- `/profile view [用户ID]`
- `/profile create [用户ID]`
- `/profile update [用户ID]`
- `/shut [分钟]`

说明：

- `/profile view` 是只读操作，不会隐式刷新画像
- 普通用户在私聊里只能操作自己
- 普通用户在群聊里也只能操作自己的画像

### 管理员命令

- `/affinity debug <用户ID>`
- `/set_affinity <用户ID> <分数>`
- `/san set [值]`
- `/profile delete <用户ID>`
- `/profile stats`
- `/evolution review [页码]`
- `/evolution approve <ID>`
- `/evolution reject <ID>`
- `/evolution clear`
- `/evolution stats [scope_id]`
- `/sticker list [页码]`
- `/sticker preview <UUID>`
- `/sticker delete <UUID>`
- `/sticker disable <UUID>`
- `/sticker enable <UUID>`
- `/sticker clear`
- `/sticker stats`
- `/sticker sync`
- `/sticker add`
- `/sticker migrate`
- `/persona state [scope]`
- `/persona status [scope]`
- `/persona tick [scope] [quality]`
- `/persona todo [scope]`
- `/persona effects [scope]`
- `/persona apply [scope] [quality]`
- `/persona today [scope]`
- `/persona consolidate [scope] [date]`
- `/db show`
- `/db reset`
- `/db rebuild`
- `/db confirm`

## LLM 工具

- `get_user_profile`
- `upsert_cognitive_memory`
- `get_user_messages`
- `get_group_recent_context`
- `get_group_memory_summary`
- `update_affinity`
- `evolve_persona`
- `list_stickers`
- `send_sticker`

## 数据存储

- 用户画像：本地文件
- 会话总结 / 会话事件：AstrBot 知识库
- 图片 caption cache / 审核 evidence：SQLite
- 反思 / SAN / 情感积分等运行数据：SQLite
- Persona Sim：SQLite
- 表情包：本地目录

Persona Sim 当前会落这些表：

- `persona_state`
- `persona_effects`
- `persona_events`
- `persona_todos`
- `persona_episodes`

## 配置分组

### 基础

- `review_mode`
- `persona_name`
- `admin_users`
- `target_scopes`
- `debug_log_enabled`

### 核心开关

- `memory_enabled`
- `reflection_enabled`
- `interject_enabled`
- `san_enabled`
- `entertainment_enabled`

### 记忆与画像

- `memory_kb_name`
- `memory_fetch_page_size`
- `memory_summary_chunk_size`
- `memory_summary_schedule`
- `enable_kb_memory_recall`
- `profile_msg_count`
- `profile_cooldown_minutes`
- `enable_profile_injection`
- `enable_profile_fact_writeback`
- `auto_profile_enabled`
- `auto_profile_schedule`

### 行为与互动

- `affinity_auto_enabled`
- `affinity_recovery_enabled`
- `interject_interval`
- `interject_cooldown`
- `interject_trigger_probability`
- `engagement_react_probability`
- `san_auto_analyze_enabled`

### 娱乐

- `sticker_learning_enabled`
- `sticker_freq_threshold`
- `sticker_total_limit`
- `meal_max_items`
- `meal_eat_keywords`
- `meal_banquet_keywords`
- `meal_banquet_count`
- `meal_banquet_cooldown_minutes`

### 审核

- `moderation.enabled`
- `moderation.enforcement_enabled`
- `moderation.nsfw_keywords`
- `moderation.promo_keywords`
- `moderation.refusal_keywords`
- `moderation.nsfw_refusal_confidence`
- `moderation.promo_refusal_confidence`
- `moderation.weak_keyword_confidence`
- `moderation.confidence_threshold`
- `moderation.escalation_threshold`
- `moderation.ban_duration_minutes`
- `moderation.nsfw_warning_message`
- `moderation.nsfw_ban_reason_message`
- `moderation.promo_warning_message`
- `moderation.promo_ban_reason_message`

## 日志前缀

排查问题时，优先看这些前缀：

- `[MemoryWrite]`
- `[MemoryQuery]`
- `[MemorySummary]`
- `[MemoryStore]`
- `[MemoryInject]`
- `[PersonaSim]`
- `[Consolidation]`
- `[Engagement]`
- `[Affinity]`
- `[Moderation]`
- `[ModerationEnforcer]`

正常跳过通常只打 `debug`，不打 `warning`。

## 重装与迁移注意事项

- 重装插件不会自动清空 AstrBot 知识库
- 重建数据库不会删除画像文件
- 重建数据库不会删除表情包目录
- scope 知识库会按群聊 / 私聊自动隔离

如果需要彻底清理不同层的数据，需要分别处理：

- 数据库：`/db reset` 或 `/db rebuild`
- 表情包：`/sticker clear` 或删除本地表情包目录
- 画像：删除画像文件
- 知识库总结：在 AstrBot 知识库侧清理

## 入口文件

如果你要继续看代码，优先从这些入口开始：

- [main.py](/D:/skills/GD/astrbot_plugin_self_evolution/main.py)
- [memory_router.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/memory_router.py)
- [memory_query_service.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/memory_query_service.py)
- [profile.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/profile.py)
- [session_memory_store.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/session_memory_store.py)
- [engagement_planner.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/engagement_planner.py)
- [reply_executor.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/reply_executor.py)
- [persona_sim_engine.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/persona_sim_engine.py)
- [persona_sim_consolidation.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/persona_sim_consolidation.py)
- [caption_service.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/caption_service.py)
- [moderation_classifier.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/moderation_classifier.py)
- [moderation_enforcer.py](/D:/skills/GD/astrbot_plugin_self_evolution/engine/moderation_enforcer.py)
