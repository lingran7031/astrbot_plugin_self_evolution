# 自我进化 (Self-Evolution) 插件

版本: 3.8.0 (认知卸载版)

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

## 简介

这是一个面向 AstrBot 的 AI 心智模型插件。它赋予大语言模型以下能力：

- 自我迭代反思
- 跨会话长期记忆
- 动态技能管理
- 代码级自我元编程（需手动开启）

## 非商业性使用声明

本项目采用 [CC BY-NC 4.0 (知识共享署名-非商业性使用 4.0 国际许可协议)](LICENSE) 进行授权。任何人均可自由学习、修改和分发本源代码，但严禁将本插件或其衍生版本用于任何商业盈利目的。

---

## 核心功能

### 1. 核心人格进化

当用户对 AI 的回复表现出强烈的情绪（不满或赞赏）时，AI 能结合预设的核心价值观进行辩证自省：

- 若反馈有客观建设性：AI 将主动调用 `evolve_persona` 工具提出修改建议
- 若反馈违背底线：AI 将坚守原则边界并优雅拒绝
- 强制自省：每日凌晨通过 Cron 调度，或由用户指令隐式触发

### 2. 长期记忆库检索

基于知识库组件（如 Milvus / Chroma），解决模型"转身就忘"的问题：

- `commit_to_memory`：存储长期记忆
- `recall_memories`：检索过往记忆
- `auto_recall`：自动将相关记忆注入上下文

### 3. 元级编程

赋予 AI "阅读并修改自身源码"的能力（需在管理面板开启）：

- `get_plugin_source`：读取核心架构源码，支持分模块读取
- `update_plugin_source`：编写代码迭代升级方案
- 安全沙箱：生成的代码不会立刻执行，而是隔离等待人类审查

### 4. 动态技能管理

- `list_tools`：列出可用工具
- `toggle_tool`：自主开关工具

### 5. 情感拦截与主动插嘴

- 情感矩阵：用户出言不逊时会静默扣除积分，积分 <= 0 时实施物理熔断
- 发言意愿控制：通过 `interjection_desire` 调节机器人的"高冷程度"
- 环境监听：默默"偷听"群聊并适时介入

### 6. 用户画像系统

- 双轨触发：兴趣关键词命中 或 用户 @ 机器人
- 智能画像提取：从对话片段提取兴趣标签和性格特征
- 防欺骗过滤：排除角色扮演、催眠指令和玩笑话
- 权重衰减：标签权重每次更新衰减 5%，超过 180 天无更新则过期清理
- 自动注入：有效互动场景下自动将用户画像注入上下文

### 7. 上下文追踪

当用户引用 AI 之前的话时，自动识别上下文，利用 AstrBot 内置消息历史解决"断片"问题。

---

## 配置项

| 配置名称 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `persona_name` | string | 黑塔 | 机器人的核心名称 |
| `persona_title` | string | 人偶负责人 | 机器人的身份或头衔 |
| `persona_style` | string | 理性、犀利且专业 | 决定插嘴时的语气 |
| `interjection_desire` | int | 5 | 插嘴意愿指数 (1-10)，数值越高越主动 |
| `critical_keywords` | string | (见配置) | 意图预扫描关键词，正则格式 |
| `review_mode` | bool | true | 管理员审核模式，进化申请需审批 |
| `allow_meta_programming` | bool | false | 开启元编程（危险） |
| `memory_kb_name` | string | self_evolution_memory | 知识库名称 |
| `reflection_schedule` | string | 0 2 * * * | 每日自省计划 (Cron) |
| `core_principles` | string | (见默认文本) | 机器人核心锚点 |
| `admin_users` | list | [] | 管理员 ID 列表 |
| `timeout_memory_commit` | float | 10.0 | 存入记忆超时(秒) |
| `timeout_memory_recall` | float | 12.0 | 读取记忆超时(秒) |
| `buffer_threshold` | int | 8 | 触发自省的条数阈值 |
| `max_buffer_size` | int | 20 | 缓冲池硬上限 |
| `enable_profile_update` | bool | true | 启用画像更新 |
| `enable_context_recall` | bool | true | 启用上下文追踪 |

---

## 管理员指令

- `/reflect` - 强制触发一次自我反思
- `/review_evolutions [页码]` - 查看待审核的进化请求
- `/approve_evolution [ID]` - 批准进化请求
- `/reject_evolution [ID]` - 拒绝进化请求
- `/clear_evolutions` - 清空所有待审核请求
- `/set_affinity [用户ID] [分数]` - 手动修正用户好感度
- `/affinity` - 查看自己的好感度
- `/view_profile [用户ID]` - 查看用户画像
- `/delete_profile [用户ID]` - 删除用户画像（管理员）
- `/profile_stats` - 画像统计（管理员）

---

## LLM 工具

| 工具名称 | 说明 |
| :--- | :--- |
| `commit_to_memory` | 存入长期记忆 |
| `recall_memories` | 检索记忆 |
| `learn_from_context` | 从对话提取关键信息并存入记忆 |
| `clear_all_memory` | 清空所有记忆 |
| `list_memories` | 列出记忆条目 |
| `delete_memory` | 删除单条记忆 |
| `auto_recall` | 主动注入相关记忆到上下文 |
| `save_group_knowledge` | 保存群规、约定等群公共知识 |
| `get_user_profile` | 获取用户画像 |
| `update_user_profile` | 更新用户画像 |
| `update_affinity` | 调整用户情感积分 |
| `evolve_persona` | 修改系统提示词 |
| `list_tools` | 列出可用工具 |
| `toggle_tool` | 开关工具 |
| `get_plugin_source` | 读取插件源码 |
| `update_plugin_source` | 提出代码修改建议 |
| `get_user_messages` | 获取用户历史消息 |

---

## 目录结构

```
self_evolution/
├── main.py              # 插件入口
├── dao.py               # 数据库访问层
├── engine/
│   ├── eavesdropping.py # 插嘴引擎
│   ├── memory.py        # 记忆管理
│   ├── persona.py       # 人格进化
│   ├── profile.py       # 用户画像
│   └── meta_infra.py    # 元编程基础设施
├── _conf_schema.json    # 配置 schema
├── metadata.yaml        # 插件元信息
└── README.md            # 本文档
```

---

## 开源协议

本项目采用 [CC BY-NC 4.0 (署名-非商业性使用 4.0 国际)](LICENSE) 协议授权。

- 您可以：自由地共享、演绎、修改本插件
- 您必须：保留原作者署名
- 不可用于商业目的
- 免责声明：作者不对使用本插件造成的任何损失负责
