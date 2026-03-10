# 自我进化 (Self-Evolution) 插件

**版本**: 5.0.15 | **CognitionCore**: 6.0

交流群: 1087272376

---

## 简介

这是 AstrBot 的认知增强插件，赋予 AI 主动环境感知、长期记忆、用户认知、情感模拟等高级能力。

**核心理念**: 让 AI 拥有"高维生物感"——不只是响应命令，而是像真正的生命体一样感知、记忆、学习、成长。

---

## 核心功能

### 主动插嘴引擎 (EavesdroppingEngine)

**指数衰减积分器** - 模拟更自然的插嘴节奏
```
S_t = S_{t-1} * e^(-λ*Δt) + w_i
```
- 长时间无人说话时自动冷静
- 关键词命中时瞬间冲动
- 日常聊天时缓慢积累

**漏斗机制** - 三级用户活跃判定
| 级别 | 触发条件 |
|------|----------|
| L1 | @机器人、命令前缀、引用回复 |
| L2 | 唤醒词(黑塔/belta)、AI意图句式 |
| L3 | 30秒活跃时间窗口 |

**主动无聊机制** - 信息熵检测，低信息量累积时拒绝回复

**中间消息过滤** - 拦截工具调用期间的过渡性消息

---

### 用户画像系统 (ProfileManager)

- **分层失活**: 核心信息永不丢失，边缘信息随机丢弃增加人味
- **情绪依存记忆**: 根据好感度动态调整记忆检索倾向
- **内部独白**: 判定不插嘴时的内心OS，存储并在下次发言时注入
- **记忆模糊化**: 低置信度记忆表现出不确定，"我隐约记得..."

---

### 记忆系统 (MemoryManager)

**认知卸载** - 把脏活扔给晚上的LLM
- 凌晨批量构建用户画像
- Markdown 文本存储
- 直接读取，非向量检索

**惊奇驱动学习** - 检测用户认知颠覆，实时更新画像

---

### 关系图谱 (GraphRAG)

- 记录用户在群聊中的互动关系
- 追踪活跃群组和频繁互动用户
- 增强记忆检索

---

### 精力值系统 (SANSystem)

- 模拟心智疲劳
- 每条消息消耗精力，定期恢复
- 精力耗尽时拒绝服务

---

### 群体情绪共染 (GroupVibeSystem)

- 感知群聊整体情绪
- 积极/消极词汇计分
- 影响 AI 回复风格

---

### 元级编程 (MetaInfra)

**多智能体对抗** - GAN 风格代码审查
- 黑塔生成代码提案
- 螺丝咕姆/阮梅对抗辩论
- 多轮达成共识后人工审核

**跨机体蜂群心智** - 跨群知识关联分析

---

## 快速配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `persona_name` | 黑塔 | 机器人名称 |
| `interjection_desire` | 3 | 发言意愿 (1-10，越高越爱说话) |
| `leaky_integrator_enabled` | true | 启用积分器 |
| `boredom_enabled` | true | 启用无聊检测 |
| `dream_enabled` | true | 启用凌晨画像构建 |
| `dropout_enabled` | true | 启用分层失活 |
| `graph_enabled` | true | 启用关系图谱 |
| `san_enabled` | true | 启用精力值 |

---

## 指令

| 指令 | 说明 |
|------|------|
| `/reflect` | 强制自省 |
| `/affinity` | 查看自己好感度 |
| `/set_affinity [用户ID] [分数]` | 调整好感度 |
| `/view_profile [用户ID]` | 查看用户画像 |
| `/delete_profile [用户ID]` | 删除画像 |
| `/graph_info [用户ID]` | 查看关系图谱 |

---

## LLM 工具

| 工具 | 说明 |
|------|------|
| `get_user_profile` | 获取用户画像 |
| `update_user_profile` | 更新用户画像 |
| `commit_to_memory` | 存入记忆 |
| `recall_memories` | 检索记忆 |
| `get_user_messages` | 获取用户消息历史 |
| `update_affinity` | 调整好感度 |
| `evolve_persona` | 修改人格 |

---

## 提示词配置

所有提示词已提取到 `prompts.yaml`，可自定义：
- `persona.anchor` - 核心人设
- `persona.communication` - 交流准则
- `eavesdrop.system` - 插嘴决策提示
- `memory.user_summary` - 画像总结提示

---

## 目录结构

```
self_evolution/
├── main.py              # 插件入口
├── config.py            # 配置系统
├── prompts.yaml         # 提示词配置
├── prompts.py          # 提示词加载器
├── dao.py              # 数据库层
├── cognition/
│   ├── san.py          # 精力值系统
│   └── vibe.py         # 群体情绪
└── engine/
    ├── eavesdropping.py # 插嘴引擎
    ├── memory.py       # 记忆管理
    ├── profile.py      # 用户画像
    ├── persona.py      # 人格进化
    ├── meta_infra.py   # 元级编程
    └── graph.py        # 关系图谱
```

---

## 开源协议

CC BY-NC 4.0 - 署名-非商业性使用
