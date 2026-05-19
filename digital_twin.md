# 设计文档：个人数字分身系统（Personal Digital Twin v1.3）

> 数字分身的内容基座 —— 把分散的个人语料组织为分层、可检索、可投影、可演化、可验证、可回滚的记忆系统。

---

## 阶段进度

```text
当前整体进度：

阶段 1   ⏳  Markdown 内容基座（MVP）
   1.1   ✅  inbox / curated 双层数据布局（content-addressed）
   1.2   ✅  L1 Schema + SQLite 模型（含 canonical_unit_id 预留）
   1.3   ✅  Ingestion Profile: tech_markdown
   1.4   ✅  缓存与重抽取（content-hash + prompt-hash + model_id）
   1.5   ✅  Schema Migrator（additive 直读 / rename 走 migrator）
   1.6   ✅  LLM Router（scope-driven，filter before retrieve）
   1.7   ✅  Retrieval API（含 as_of / dedup_by_canonical 接口预留）
   1.8   ✅  FTS5 + 关键词检索实现（含 LIKE 补充检索）
   1.9   ✅  `twin recall` CLI（可感知产出）
   1.10  ✅  Snapshot 机制基础（捕获状态指纹）
   1.11  ✅  评估集 v1（30 道能力评估，Recall@10 = 70%）
   1B     ✅  真实 LLM 接入（DeepSeek）+ 抽取 prompt 调优 + 评估集

阶段 2   ✅  Git 项目经验沉淀
   2.1   ✅  Ingestion Profile: code_repo
   2.2   ✅  `twin project <name>` CLI（可感知产出）
   2.3   ✅  Canonical 选举器 + same_as 自动去重
   2.4   ✅  评估集 v2（+20 道，Recall@10 = 70%）
   2.5   ✅  commit / readme 抽取（pr / issue / code_comment 预留）
   2.6   ✅  项目维度聚合视图（4 aspect + export handover）
   2.7   ✅  `twin project <name>` CLI + `twin canonical` CLI
   2.8   ✅  评估集 v2（+20 道项目相关，50 道总计）

阶段 3   ⏳  对话场景（面试 / 交接）+ 漂移检测
   3.1   ✅  Embedding 索引（shibing624/text2vec-base-chinese, dim=768）
   3.2   ✅  简化版 as_of 查询（基于 valid_from/valid_until 过滤）
   3.3   ✅  Projection 引擎（scope-aware 投影）
   3.4   ✅  Redactor 脱敏引擎
   3.5   ✅  对话状态管理（State Store + approved transcript 回流 L0-L1）
   3.6   ✅  漂移检测三级分类（auto_fix / needs_review / needs_user_decision）
   3.7   ✅  联网验证（LLM 验证 drift 正确性 + confidence 调整）
   3.8   ✅  Router fail-safe（本地模型故障 → 默认硬失败 + 显式降级选项）
   3.9   ✅  3-A 脚本化问答（固定问题清单 + 人工审阅闭环）
   3.10  ✅  3-B 模板对话（intent + slot: interview_qa / handover_brief / knowledge_review）
   3.11  ✅  3-C 开放对话 + 护栏（敏感词拦截 + scope 约束 + 响应脱敏）
   3.12  ✅  回归评估集（与 snapshot 绑定 + 简化 as_of 回放）
   3.13  ✅  评估集 v3（40 道，对齐实际数据，Hybrid Recall@5 = 95%）

阶段 4+  🔒  后续方向（schema 已预留，本期不实现）
   - 日记 ingestion（diary，强制 private）
   - 阅读笔记 ingestion（reading_note，含 tech / life / business 等 8 类）
   - 自己的文章 ingestion（article）
   - 写作助手（基于已有 article 的 few-shot）
   - 成长追踪 / 完整 bitemporal as_of 查询（追踪 valid_until 自身设置时间）
   - 反馈回路 / 校正回流 / 漂移检测从规则向学习升级
   - SQLite 独立 schema migration（仅当 rebuild-db 性能不可接受时启用）
```

图例：⏳ 进行中 / 即将开始　⏸ 暂未启动　🔒 远期规划　✅ 已完成

---

# 一、设计目标

---

## 1.1 系统定位

```text
个人数字分身的内容基座
```

系统的根本职责：

* 把分散的个人语料（技术笔记 / 项目代码 / 阅读 / 文章 / 日记 / 对话）
* 组织为分层、可检索、可投影、可演化、**可验证**、**可回滚**的**记忆系统**
* 支撑数字分身在不同场景下进行检索、回答、协作、产出

---

## 1.2 三类核心使用场景（MVP 范围）

| 场景 | 形态 | 阶段 | 优先级 |
|------|------|------|------|
| 自用知识检索 | CLI 问答 + 语义检索 | 阶段 1 起 | 🔴 P0 |
| 项目经验沉淀 | 项目维度聚合 + 查询 | 阶段 2 起 | 🔴 P0 |
| 对外专业场景（面试 / 交接） | 实时对话（脚本化 → 开放） | 阶段 3 | 🔴 P0 |

---

## 1.3 设计原则（强约束）

---

### 🔴 P1 — 原始语料不可销毁、不可重写

任何 ingestion 操作都**不修改原文**，原始材料一经写入 L0 即永久保留。所有上层产物可从 L0 完整重建。

> 注：漂移检测中的"自动修复"、对话校正、漂移修复也不真正销毁旧 unit，而是写新 unit + supersedes/corrects 关系 + 旧 unit 设置 valid_until。

---

### 🔴 P2 — Schema 一次性想清楚

数据模型字段宁可暂时为 null，也要预留好。后期改 schema 比延迟实现代价大得多。

---

### 🔴 P3 — 隐私默认从严（白名单制）

未显式标记 `public` / `internal` 的，一律视为 `private`。错误倾向永远偏向"过严"。

---

### 🔴 P4 — 本地数据主权

L0 raw / L1 units / embeddings / index 全部本地存储。云端 LLM 仅承担 inference，不留存数据。敏感内容路由到本地模型。

---

### 🔴 P5 — 每阶段必须可 dogfood

不允许"做完一个阶段没人感知"。每阶段必须有 CLI 工具产出，跑通自己用得起来的最小闭环。

---

### 🔴 P6 — MVP 不做 L4 人格层

不做 fine-tuning、LoRA、风格指纹。"像我"的能力用 prompt + few-shot 兜底。底线是"内容正确、不冒充"，不追求"语言风格一致"。

---

### 🔴 P7 — 派生物必须可重建

文档、回答、投影、报告等所有派生物，全部可从底层数据**幂等地重新生成**。派生物不是数据源。

---

### 🔴 P8 — 知识演化在使用阶段触发，不在 ingestion 阶段做

"知识过时"的判定是 **lazy + on-demand**：

* ingestion 阶段不主动做相似度检索找冲突
* query / 对话阶段，LLM 自然感知 retrieved units 与自身世界知识的差异
* 冲突时触发联网验证 + 用户 confirm
* **从不静默改变记忆**

详见 [6.6](#66-漂移检测与时效性验证)。

---

### 🔴 P9 — 对话既是消费者也是生产者

对话系统在记忆架构中**既消费记忆，又生产记忆**：

* **消费**：对话时从 L1-L2 检索来回答
* **生产**：approved 的对话答案 + 用户校正 → ingest 回 L0-L1（作为 `source_kind: conversation`）
* **临时状态**（draft / pending / need_edit）走外挂 State Store，不污染 L0-L1
* **关键边界**：只有 `approved` / `user.correction` 事件才触发 L0-L1 写入

详见 [6.5](#65-对话状态管理state-store--approved-回流)。

---

### 🔴 P10 — Schema 演进三档分级

任何 schema 变更必须显式归类，不同档走不同路径：

| 档位 | 变更类型 | 处理方式 | 成本 |
|------|---------|---------|------|
| **L1: Additive** | 加字段（含 default 非 null 或 nullable） | 旧 jsonl 直读，新字段用 default | 零成本 |
| **L2: Renaming / Retyping** | 字段重命名 / 类型变更 | **幂等 migrator** 重写 jsonl（旧文件 `.v<old>.jsonl.bak` 备份） | 一次性 IO，无 LLM 调用 |
| **L3: Semantic Change** | 抽取语义变了（如新增 kind 枚举值） | 触发 `twin reextract`（用户主动） | 高（重抽 LLM） |

**关键不变量**：

* migrator 必须**幂等**（多次运行结果一致）
* 任何变更都自动备份原 jsonl，永不真删
* schema_version 在每个 unit 上记录，DB 也记录"全局 current schema_version"

详见 [4.6](#46-schema-演进与-migrator)。

---

### 🔴 P11 — SQLite 是 jsonl 的纯派生物

```text
真相源：curated/*.jsonl
派生物：SQLite（含 FTS5 / 索引）

任何 schema 变更都通过 jsonl migrator 完成；
SQLite 不维护独立的 schema migration（无 Alembic-style ALTER TABLE）；
每次 jsonl migrate 后强制 `twin rebuild-db` 重建整个 SQLite。
```

**含义**：

* SQLite 任意时刻可 drop + recreate，不丢数据
* `twin rebuild-db` 是日常操作（非重型操作），但有性能上限监控
* 阶段 4+ 若数据规模导致 rebuild-db 不可接受（监控阈值 > 60s），再启用 SQLite 独立 migration

详见 [4.6.6 Rebuild-db 性能监控与升级阈值](#466-rebuild-db-性能监控与升级阈值)。

---

### 🔴 P12 — Router 永不静默降级到云端

```text
本地模型不可用时：
  默认行为：硬失败（拒答 / 终止 query）
  允许行为：用户显式 --fallback public-only 降级（仅查询 public 内容）
  禁止行为：任何形式的静默云端兜底
```

**理由**：宁可拒绝服务，也绝不让敏感内容因为本地模型故障而泄露到云端。

详见 [4.7.5 Router 故障路径](#475-router-故障路径fail-safe)。

---

## 1.4 明确不做（划清边界）

```text
本期 MVP 不做：

❌  fine-tuning / LoRA / SFT / RL
❌  风格指纹 / 写作助手
❌  日记 ingestion（schema 预留）
❌  成长追踪 / 观点演化分析（schema 预留）
❌  漂亮的人类阅读文档（人类阅读不是主要场景）
❌  自动化执行 / Agent runtime 持久服务
❌  ingestion 时的主动重叠检测（移到 query 时做）
❌  完整 bitemporal 模型（不追踪 valid_until 自身的设置时间）
```

> 这些不是"永远不做"，而是"MVP 不做、schema 不堵路"。

---

# 二、核心范式：四层记忆架构

---

## 2.1 总览

```text
┌──────────────────────────────────────────────────────────┐
│  L3   Projection Layer（投影层）                         │
│       scope-aware 投影：self / interview / handover / public │
│       脱敏 / 抽象 / 重组，按需生成、不存独立副本         │
├──────────────────────────────────────────────────────────┤
│  L2   Retrieval Index（检索索引）                        │
│       FTS5 关键词 + Embedding（阶段 3 升级）             │
│       Metadata filter（sensitivity / time / kind / tags）│
│       Canonical dedup（same_as 组聚合）                  │
│       ← LLM 真正消费的接口                               │
├──────────────────────────────────────────────────────────┤
│  L1   Atomic Memory Units（原子记忆单元）                │
│       丰富 metadata，引用回 L0 原文                      │
│       不可变、不删除、不抹平                             │
│       存储：curated/<source_kind>/<raw_sha256>.jsonl     │
│             （真相源） + SQLite（索引层）                │
├──────────────────────────────────────────────────────────┤
│  L0   Raw Corpus（原始语料）                             │
│       Content-addressed（sha256），永远保留              │
│       inbox/<date>/<sha256>.{ext} + meta.json            │
└──────────────────────────────────────────────────────────┘
        ↑↓ 对话回流：approved Q&A 作为新 raw 进 L0
        ↑  漂移检测：query 时触发，写新 unit
```

---

## 2.2 关键设计决策

---

### 🟢 决策 1：L0 是真正的数据根基

任何材料一进系统就 sha256 命名 + 时间戳入 inbox，**永不修改**。其他层全部是 L0 的**派生视图**，可随时重建。

---

### 🟢 决策 2：L1 不重写、不去重，只标记

* 提取阶段的 `content` 字段必须是**原文或最小重述**，不允许 LLM "融合重写"
* 重复出现的内容用 `same_as` 关系链接，并在 `frequency_signal` 累加（重复 = 信号）
* 矛盾观点用 `contradicts` / `supersedes` 关系链接
* **去重发生在 L2 检索层**（canonical 选择），不在 L1 数据层

---

### 🟢 决策 3：L2 是 LLM 的真实接口

不再生成"漂亮 Markdown 文档"给 LLM 看。LLM 通过检索 API 拿到 chunks（带 metadata），自己组织答案。
L2 同时承担 **canonical 选择**职责，把 same_as 组合并为单条结果对 LLM 呈现。

---

### 🟢 决策 4：L3 是按需投影、不存副本

private / public 视角不存两份数据，而是从 L1 按 scope 实时投影。脱敏、重组、过滤都是函数。

---

### 🟢 决策 5：暂不实现 L4

按"中等可降为底线"原则，MVP 用 prompt engineering + few-shot 兜底，足够支撑阶段 3 的对话场景。L4 保留为未来扩展点，**当前 schema 不需要为它做任何特殊准备**。

---

### 🟢 决策 6：curated 按 content-addressed 1:1 组织

curated 文件不承担"主题组织"职责，**仅做 raw → units 的 1:1 真相源存储**。
所有检索 / 主题归集 / 跨文件聚合 **完全依赖索引层**（SQLite + FTS5 + embedding）。

---

### 🟢 决策 7：知识演化是 lazy + on-demand

不在 ingestion 时做主动重叠检测。在 query / 对话时利用 LLM 世界知识感知冲突，触发联网验证，由用户 confirm 落地为新 unit。

---

### 🟢 决策 8：LLM Router 是 scope-driven + filter before retrieve

* 每次 query **必须声明 scope**
* 检索前按 scope 过滤候选 sensitivity（secret 永不参与对外检索）
* 整个 query 走**单一 LLM**，按 retrieved 的 max sensitivity 决策路由
* 同一 query 在不同 scope 下返回不同结果——这是**设计意图**，不是 bug

详见 [4.7](#47-llm-router-检索时序scope-driven--filter-before-retrieve)。

---

### 🟢 决策 9：对话产物分层归属

* draft / pending / 审阅状态 → **外挂 State Store**（`data/conversations/`）
* approved 对话的 **transcript（事件记录）** → **ingest 回 L0-L1**（不是 answer 本身，是"这次对话发生过"的事实记录）
* 用户校正 → 新 unit + `corrects` 关系

详见 [6.5](#65-对话状态管理state-store--approved-回流)。

---

### 🟢 决策 10：L0 收纳事件记录，不收纳派生答案

为避免 "approved 对话答案是派生物" 与 "L0 = 原始语料" 的语义冲突：

| 写入 L0 的 | 不写入 L0 的 |
|----------|------------|
| **transcript**（Q + A + retrieved unit_ids + approved 标签 + 时间）—— 这是事件 | LLM 生成答案的中间产物 |
| 用户在对话中**亲口表达**的新观点 | 仅 LLM 输出但用户未表态的内容 |
| 用户校正的**校正内容**（作为新 unit + corrects 关系） | 被校正的旧 unit（不动，只标 valid_until） |

**判定原则**：

> 凡是"事件"或"用户表达"的，是 L0 公民；
> 凡是"派生计算的产物"，不应进 L0（即使审阅过）。

approved transcript 之所以可以进 L0，因为它记录的是"这场对话发生了"这一事实，而非"这个答案是正确的"。

详见 [6.5.3 触发 L0-L1 写入的事件](#653-触发-l0-l1-写入的事件)。

---

# 三、数据模型

---

## 3.1 物理布局

```text
data/
├── inbox/                                # L0：原始投递箱（永远保留、永不修改）
│   └── 2026-05-15/
│       ├── a3f2c891....md                # content-addressed raw
│       ├── a3f2c891....meta.json
│       └── ...
│
├── curated/                              # L1 真相源（按 raw 1:1，不按主题）
│   ├── tech_markdown/
│   │   ├── a3f2c891....jsonl             # 1:1 对应 inbox/<date>/a3f2c891.md
│   │   ├── a3f2c891....v1.0.jsonl.bak    # migrator 备份
│   │   ├── b7e8f12c....jsonl
│   │   └── ...
│   ├── code_repo/
│   │   └── farl/
│   │       ├── commits/
│   │       │   ├── 2c4f8a....jsonl       # 对应单个 commit
│   │       │   └── ...
│   │       ├── readme/
│   │       │   └── ...
│   │       └── prs/
│   │           └── ...
│   ├── reading_note/
│   ├── article/
│   ├── conversation/                     # 对话回流后写入
│   └── diary/
│
├── index/
│   ├── twin.db                           # SQLite：units / relations / FTS5 / drifts / snapshots
│   └── vectors/                          # 阶段 3 起：embedding store
│
├── projections/                          # L3：按需生成的对外材料（缓存）
│   └── interview/
│       └── q_001.md
│
├── conversations/                        # 对话 State Store（不进 L0-L1）
│   └── <session_id>/
│       ├── meta.json                     # scope, started_at, status
│       ├── transcript.jsonl              # 每轮对话（含检索过程）
│       ├── reviews/                      # 人工审阅记录
│       │   └── q_<id>.review.json
│       └── drafts/                       # 待审阅 / need_edit 的草稿
│
├── drifts/                               # 漂移检测日志 + 待处理队列
│   ├── pending/
│   │   └── d_<id>.json
│   ├── applied/
│   │   └── d_<id>.json
│   └── rejected/
│
├── snapshots/                            # 知识库状态快照（指纹，非数据拷贝）
│   ├── snap_2026_05_15.json
│   └── ...
│
├── eval/
│   ├── capability/                       # 能力评估集（与数据状态无关）
│   │   └── v1.yaml
│   ├── regression/                       # 回归评估集（与 snapshot 绑定）
│   │   └── <snapshot_id>/
│   │       ├── snapshot.json
│   │       └── questions.yaml
│   └── reports/
│
└── logs/
    ├── ingestion.log
    └── conversations/
```

---

## 3.2 L0：inbox 规约

---

### 命名

```text
inbox/<YYYY-MM-DD>/<sha256[:40]>.<ext>
inbox/<YYYY-MM-DD>/<sha256[:40]>.meta.json
```

---

### meta.json

```json
{
  "sha256":         "a3f2c891...",
  "captured_at":    "2026-05-15T13:45:00+08:00",
  "original_path":  "D:/Notes/Tech/Redis/data-structures.md",
  "source_kind":    "tech_markdown",
  "sub_kind":       null,
  "url":            null,
  "size_bytes":     4823,
  "mime":           "text/markdown",
  "provenance":     "original | lost_origin | clipped_from_url | conversation_transcript",
  "ingest_status":  "pending | extracted | failed",
  "origin_session_id": null
}
```

`provenance: conversation_transcript` 与 `origin_session_id` 用于追踪"对话回流"的 raw —— 回流的是 transcript（事件记录），不是 answer（派生物）。详见 [6.5](#65-对话状态管理state-store--approved-回流) 与 [决策 10](#-决策-10l0-收纳事件记录不收纳派生答案)。

---

### 特殊情况：lost_origin

某些"整理过的笔记"已经丢失了原文。处理方式：

* 整理稿本身作为 L0 入 inbox
* `provenance: "lost_origin"`
* 明确接受："这部分内容的'个人性'已不可恢复"

---

### 特殊情况：仅链接的文章

* 用 `monolith` / `single-file` / `obsidian-clipper` **批量抓取原网页存 HTML**
* HTML 文件入 inbox，URL 写入 meta.json
* 不依赖外部链接可用性

---

## 3.3 L1：Atomic Memory Unit Schema

---

### 完整字段定义

```json
{
  "id":              "uuid7-string",
  "schema_version":  "1.0",

  "content":         "原话或最小重述（不允许融合重写）",
  "content_hash":    "sha256-of-content",

  "source": {
    "raw_sha256":    "a3f2c891...",
    "raw_offset":    [123, 456],
    "source_kind":   "tech_markdown",
    "sub_kind":      null,
    "captured_at":   "2026-05-15T...",
    "observed_at":   "2024-09-10T..."
  },

  "kind":            "fact | concept | procedure | decision | opinion | preference | experience | feeling | plan | typo_fix",

  "topics":          ["redis", "performance"],
  "entities":        [
                       {"name": "Redis", "type": "technology"},
                       {"name": "Lua",   "type": "technology"}
                     ],
  "tags":            ["caching", "database"],

  "stance":          0,
  "confidence":      0.8,
  "valence":         0.1,

  "valid_from":      "2024-09-10",
  "valid_until":     null,

  "frequency_signal": 1,
  "canonical_unit_id": null,

  "sensitivity":     "private",
  "visibility_overrides": {
                       "interview": "internal",
                       "handover":  "public"
                     },

  "relations":       [
                       {"type": "supersedes",   "target_id": "..."},
                       {"type": "contradicts",  "target_id": "..."},
                       {"type": "same_as",      "target_id": "..."},
                       {"type": "corrects",     "target_id": "..."},
                       {"type": "example_of",   "target_id": "..."},
                       {"type": "derived_from", "target_id": "..."},
                       {"type": "part_of",      "target_id": "..."}
                     ],

  "embedding_id":          null,

  "extracted_by":          "claude-sonnet-4.5@2026-05",
  "extracted_at":          "2026-05-15T...",
  "extracted_prompt_hash": "sha256-of-prompt-template",
  "human_verified":        false,

  "verified":              false,
  "verified_by":           null,
  "verified_at":           null,
  "verification_method":   null,
  "drift_classification":  null
}
```

---

### 字段说明：核心几组

---

#### `content` —— 原话保真

* 必须是**原文片段**或**最小重述**
* 禁止 LLM "工程师风格融合改写"
* 如必须改写，保留 `raw_offset` 指向原句

---

#### `kind` —— 知识类型

| kind | 含义 | 示例 |
|------|------|------|
| `fact` | 客观事实 | "Redis 默认端口 6379" |
| `concept` | 概念定义 | "什么是 Lua VM 隔离" |
| `procedure` | 操作步骤 | "Redis 持久化配置流程" |
| `decision` | 我做出的决策 | "选择 luajit 而非纯 Lua" |
| `opinion` | 我的观点 | "我认为 Redis pub/sub 不适合做消息队列" |
| `preference` | 我的偏好 | "偏好 Python 而非 Ruby" |
| `experience` | 我的经历 | "做 FARL 时遇到了 X 问题" |
| `feeling` | 情绪 | "对这次重构很挫败" |
| `plan` | 计划 | "下个季度学 Rust" |
| `typo_fix` | 漂移修复产生的修正 unit | "redis-cli"（修自"reids-cli"） |

`fact / concept / procedure` → 技术内容主体
`decision / opinion / preference / experience` → 项目经验主体（阶段 2）
`feeling / plan` → 默认 private，阶段 4+ 处理
`typo_fix` → 漂移检测产生，详见 [6.6](#66-漂移检测与时效性验证)

> **注**：新增 kind 枚举值（如 `typo_fix`）属于 P10 中的 **L3 Semantic Change**，需要触发 reextract。已写入文档作为约束。

---

#### `stance / confidence / valence` —— 主观三元组

* `stance`：-1 反对 / 0 中立 / +1 支持
* `confidence`：0.0 ~ 1.0，我对此有多确定
* `valence`：-1.0 ~ +1.0，情感色彩（负面 → 默认敏感）

MVP 中：`fact / concept / procedure` 默认 `stance=0, valence=0`，仅 `opinion / preference / feeling` 必填。

---

#### `sensitivity` —— 四档

| 级别 | 含义 |
|------|------|
| `public` | 可对外公开、可发布 |
| `internal` | 可用于专业场景（面试 / 交接），可能需脱敏 |
| `private` | 仅自用 |
| `secret` | 仅自用，禁止任何 LLM 复述（如 token / 密码） |

默认为 `private`。详见 [3.5 默认隐私规则](#35-默认隐私规则白名单从严)。

---

#### `canonical_unit_id` —— L2 去重锚点

* 同一组 `same_as` 关系的 units 共享一个 canonical
* canonical unit 自己的 `canonical_unit_id = 自己的 id`
* 阶段 1 默认：每个 unit 自成一组（`canonical_unit_id = 自己的 id`）
* 阶段 2+：随 `same_as` 关系建立，触发选举

**关键约束**：

> Canonical **只能从当前有效（`valid_until IS NULL`）的 unit 中选举**。
> 如果一组内全部 unit 都已 expire，则该组无 canonical（检索时整组不出现）。

**Canonical 选择优先级**（候选集已先过滤 `valid_until IS NULL`）：

```text
0. 候选集 = group filter (valid_until IS NULL)   ← 必须的前置过滤
1. human_verified = true
2. verified = true AND verification_method != 'agent_self'
3. frequency_signal 最高
4. captured_at 最新
5. id 字典序（兜底，保证确定性）
```

**触发选举的时机**（详见 [5.5.1](#551-触发时机)）：

* 新建 `same_as` 关系时
* 某 unit 的 `valid_until` 发生变化时（重抽取、漂移修复、用户校正）
* 手动 `twin canonical rebuild`

详见 [7.3 Retrieval API](#73-retrieval-api) 中的 `dedup_by_canonical`。

---

#### `relations` —— 关系（替代去重）

| 类型 | 用途 | MVP |
|------|------|-----|
| `same_as` | 同一观点的多次表达（替代去重） | ✅ |
| `supersedes` | 新观点取代旧观点（成长追踪用 + 漂移修复用） | ✅ |
| `corrects` | 用户校正了 unit（与 supersedes 语义不同：corrects 是"我修正了它"，supersedes 是"事实演化") | 阶段 3 |
| `contradicts` | 矛盾（待人工 / LLM 处理） | 阶段 3 |
| `example_of` | 例子 → 概念 | ⏸ |
| `derived_from` | 推导来源 | ⏸ |
| `part_of` | 组成关系 | ⏸ |

---

#### `observed_at` vs `captured_at` vs `valid_from/valid_until`

| 字段 | 含义 |
|------|------|
| `captured_at` | 录入系统的时间（transaction time） |
| `observed_at` | 原始事件 / 表达时间（valid time 的起点） |
| `valid_from` | unit 开始有效的时间（通常 = observed_at） |
| `valid_until` | unit 失效的时间（null = 仍有效） |

**四时间维度共存的查询能力**（详见 [7.3](#73-retrieval-api)）：

* `observed_since / observed_until` — 按事件时间窗
* `captured_since / captured_until` — 按录入时间窗
* `as_of` — 时间点"那时有效"查询（阶段 1 预留、阶段 6 实现）
* `include_historical` — 是否含已 expire 的 unit

> **MVP 已知限制**：当前是**单时间维度**模型——`as_of` 查询返回的是"当前系统认为某时刻有效的 unit"，不是"某时刻系统当时认为有效的 unit"。完整 bitemporal 模型（追踪 valid_until 自身的设置时间）不在 MVP 范围。

---

#### 抽取版本化字段

* `extracted_by`：抽取模型 + 版本（如 `claude-sonnet-4.5@2026-05`）
* `extracted_at`：抽取时间
* `extracted_prompt_hash`：抽取所用 prompt 模板的 sha256
* `human_verified`：是否经人工 review 确认

**用途**：当 prompt 或模型升级时，可以 query 出"需要重抽取"的 units（详见 [4.5](#45-缓存与重抽取)）。

---

#### 验证字段（阶段 3）

* `verified`：是否经过验证
* `verified_by`：验证来源（URL / source / "agent_self" / "human"）
* `verified_at`：验证时间
* `verification_method`：`agent_self` | `web_search` | `human`
* `drift_classification`：仅 typo_fix 类 unit 上记录，记录漂移类型

详见 [6.6](#66-漂移检测与时效性验证)。

---

## 3.4 source_kind 体系（二级分类）

---

### sub_kind 的角色

> **sub_kind 不是主题细分**，主题细分用 `topics` / `tags` 表达（完全开放、多标签、动态产生）。
>
> **sub_kind 是"敏感度域 + 处理策略"载体**：能映射到不同 sensitivity 默认规则的才单列。

举例：《被讨厌的勇气》的笔记
* `source_kind: "reading_note"`
* `sub_kind: "psychology"` ← 决定默认 sensitivity = private
* `topics: ["adler", "self-acceptance", "interpersonal"]` ← 细粒度，无层级限制

---

### 完整 source_kind / sub_kind 清单

---

#### `tech_markdown`（技术 Markdown 笔记，阶段 1）

无 sub_kind（或 null）。技术内容处理策略统一。

```text
source_kind: tech_markdown
sub_kind:    null
默认 sensitivity: internal
```

---

#### `code_repo`（Git 仓库，阶段 2）

```text
source_kind: code_repo
sub_kind:
  ├── commit          # commit message + diff summary
  ├── pr              # PR description + 评论
  ├── readme          # README / design docs / changelog
  ├── issue           # issue + 我的回复
  └── code_comment    # 代码内的设计性注释

默认 sensitivity: 按仓库可见性
  - public_on_github  → public
  - private repo      → internal
```

---

#### `conversation`（对话，阶段 3）

```text
source_kind: conversation
sub_kind:
  ├── interview       # 面试问答
  ├── handover        # 项目交接
  ├── qa              # 一般问答（如 AMA）
  ├── meeting         # 会议
  ├── chat            # 私下聊天
  └── miscellaneous   # 未明确归类

默认 sensitivity:
  - interview / handover / qa  → internal
  - meeting / chat / misc       → private
```

> 在 P9 下，approved 对话 + 用户校正都会以 `source_kind: conversation` 回流入 L0-L1。

---

#### `reading_note`（读书 / 文章 / 网页笔记 / 摘录，阶段 4+）

```text
source_kind: reading_note
sub_kind:
  ├── tech            # 技术、编程、工程
  ├── science         # 数学、物理、自然科学
  ├── business        # 商业、管理、创业、经济
  ├── humanities      # 历史、文学、艺术、文化
  ├── psychology      # 心理、认知、思维方式
  ├── philosophy      # 哲学、伦理、价值观
  ├── lifestyle       # 健康、习惯、生活方式
  └── miscellaneous   # 未明确归类

默认 sensitivity:
  - tech / science / business / humanities  → internal
  - psychology / philosophy / lifestyle      → private
  - miscellaneous                            → private（保守兜底）
```

---

#### `article`（自己写的文章 / 博客 / 公开内容，阶段 4+）

```text
source_kind: article
sub_kind:
  ├── tech            # 技术文章
  ├── tutorial        # 教程
  ├── essay           # 随笔、个人思考
  ├── review          # 书评 / 影评 / 产品评测
  └── miscellaneous   # 未明确归类

默认 sensitivity:
  - tech / tutorial   AND already_published  → public
  - review            → internal
  - essay             → internal
  - miscellaneous     → private
```

---

#### `diary`（日记 / 私人记录，阶段 4+）

```text
source_kind: diary
sub_kind:
  ├── daily           # 日常记录
  ├── reflection      # 反思 / 自省
  ├── idea            # 灵感 / 想法
  ├── emotion         # 情绪记录
  └── miscellaneous   # 未明确归类

默认 sensitivity:
  - 全部强制 private（force_private_strict）

  分类只用于"成长追踪"维度的细分查询，
  不参与任何 public / internal 投影。
```

---

### 阶段对应表

| source_kind | 阶段 | sub_kind 数量 |
|-------------|------|---------------|
| `tech_markdown` | 阶段 1 | 0 |
| `code_repo` | 阶段 2 | 5 |
| `conversation` | 阶段 3 | 6 |
| `reading_note` | 阶段 4+ | 8 |
| `article` | 阶段 4+ | 5 |
| `diary` | 阶段 4+ | 5 |

---

## 3.5 默认隐私规则（白名单从严）

```yaml
default: private        # 没显式命中规则的，一律私密

promote_to_public:
  - source_kind: code_repo
    AND visibility_in_origin: public_on_github
  - source_kind: tech_markdown
    AND NOT contains_named_person
    AND NOT contains_company_name
    AND valence > -0.3
  - source_kind: article
    sub_kind: [tech, tutorial]
    AND already_published: true

allow_internal:
  - source_kind: tech_markdown
  - source_kind: code_repo
    AND visibility_in_origin: private_repo
  - source_kind: conversation
    sub_kind: [interview, handover, qa]
  - source_kind: reading_note
    sub_kind: [tech, science, business, humanities]
  - source_kind: article
    sub_kind: [essay, review]

force_private:
  - kind: [opinion, feeling, preference]
    AND valence < -0.3
  - kind: decision AND status: undecided
  - source_kind: reading_note
    sub_kind: [psychology, philosophy, lifestyle, miscellaneous]
  - source_kind: conversation
    sub_kind: [meeting, chat, miscellaneous]
  - source_kind: article
    sub_kind: miscellaneous
  - contains_entity in <personal_contacts>

force_private_strict:                # 不允许任何 override
  - source_kind: diary               # 日记任何 sub_kind 都强制 private
  - kind: feeling

force_secret:
  - matches_pattern: api_key | password | private_key | token
```

每个 unit 都可以通过 `visibility_overrides` 字段在特定 scope 下手动调整（但不能 override `force_private_strict` 与 `force_secret`）。

---

## 3.6 L1 存储：curated 1:1 真相源

---

### 核心原则

> **curated 文件不承担"主题组织"职责，仅做 raw → units 的 1:1 真相源存储**。
>
> 所有检索 / 主题归集 / 跨文件聚合 **完全依赖索引层**（SQLite + FTS5 + embedding）。

---

### 命名约定

```text
curated/<source_kind>[/<sub_path>]/<raw_sha256>.jsonl
```

每个 jsonl 文件 = 一个 raw 文件抽取出的所有 units，每行一个 unit。

Schema migrator 备份文件命名：

```text
curated/<source_kind>/<raw_sha256>.v<schema_version>.jsonl.bak
```

---

### 为什么这样组织

| 诉求 | 满足方式 |
|------|---------|
| 处理过的无需聚合 | ✅ 物理上不按主题聚合，按来源原子化存储 |
| 通过索引组织 | ✅ 主题 / 标签 / 跨文件检索完全靠索引层 |
| curated 不给人翻阅 | ✅ 文件名是 sha256，本来就不可读，强化"只是真相源"定位 |
| 重新抽取单个文件 | ✅ 删 `<sha256>.jsonl` + 重抽取 → 干净 |
| Schema migrate 单文件 | ✅ migrator 每个文件独立处理 + 单独备份 |
| git diff 友好 | ✅ changes 集中在某个 jsonl 文件 |
| 1:1 追溯 | ✅ raw `<sha256>.md` ↔ curated `<sha256>.jsonl` ↔ inbox meta |
| append-only 友好 | ✅ jsonl 天然追加格式 |

---

### 文件格式

每行一个 unit（标准 JSONL），UTF-8 编码：

```jsonl
{"id":"01HXJW...","content":"...","kind":"fact",...}
{"id":"01HXJW...","content":"...","kind":"opinion",...}
{"id":"01HXJW...","content":"...","kind":"procedure",...}
```

---

### jsonl ↔ SQLite 同步

* **写入**：抽取产物先写 jsonl（原子追加），再批量同步到 SQLite
* **真相源**：jsonl
* **重建**：`twin rebuild-db` 一键从 jsonl 重建整个 SQLite

---

## 3.7 SQLite Schema 草图

> **SQLite 是 jsonl 的纯派生物（落地 P11）**：
>
> * 任何 schema 变更通过 jsonl migrator（[4.6](#46-schema-演进与-migrator)）
> * SQLite 不维护独立 schema migration（无 ALTER TABLE 链）
> * 每次 jsonl migrate 后强制 `twin rebuild-db` 重建整个 SQLite
> * SQLite 任意时刻可 drop + recreate，不丢数据

```sql
CREATE TABLE units (
  id                     TEXT PRIMARY KEY,
  schema_version         TEXT NOT NULL DEFAULT '1.0',

  content                TEXT NOT NULL,
  content_hash           TEXT NOT NULL,

  source_kind            TEXT NOT NULL,
  sub_kind               TEXT,
  raw_sha256             TEXT NOT NULL,
  raw_offset_s           INTEGER,
  raw_offset_e           INTEGER,
  captured_at            TEXT NOT NULL,
  observed_at            TEXT,

  kind                   TEXT,
  stance                 INTEGER DEFAULT 0,
  confidence             REAL    DEFAULT 0.5,
  valence                REAL    DEFAULT 0.0,

  valid_from             TEXT,
  valid_until            TEXT,

  frequency_signal       INTEGER DEFAULT 1,
  canonical_unit_id      TEXT,                  -- 自指向；同组 same_as 共享
                                                -- 阶段 1 默认 = 自己的 id

  sensitivity            TEXT NOT NULL DEFAULT 'private',

  embedding_id           TEXT,

  extracted_by           TEXT,
  extracted_at           TEXT,
  extracted_prompt_hash  TEXT,
  human_verified         INTEGER DEFAULT 0,

  verified               INTEGER DEFAULT 0,
  verified_by            TEXT,
  verified_at            TEXT,
  verification_method    TEXT,
  drift_classification   TEXT,

  raw_jsonl_path         TEXT      -- 回链 curated/.../file.jsonl
);

CREATE TABLE unit_topics    (unit_id TEXT, topic TEXT, PRIMARY KEY(unit_id, topic));
CREATE TABLE unit_entities  (unit_id TEXT, name TEXT, type TEXT);
CREATE TABLE unit_tags      (unit_id TEXT, tag TEXT, PRIMARY KEY(unit_id, tag));

CREATE TABLE relations (
  src_id     TEXT NOT NULL,
  rel_type   TEXT NOT NULL,
  dst_id     TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(src_id, rel_type, dst_id)
);

CREATE TABLE visibility_overrides (
  unit_id     TEXT NOT NULL,
  scope       TEXT NOT NULL,
  sensitivity TEXT NOT NULL,
  PRIMARY KEY(unit_id, scope)
);

CREATE TABLE drifts (
  id                  TEXT PRIMARY KEY,
  detected_at         TEXT NOT NULL,
  triggered_by        TEXT,                 -- query_text / unit_id
  old_unit_id         TEXT,
  new_content         TEXT,
  classification      TEXT,                 -- auto_fix / needs_review / needs_user_decision
  agent_confidence    REAL,
  status              TEXT,                 -- pending / applied / rejected
  applied_at          TEXT,
  applied_new_unit_id TEXT,
  verification_url    TEXT
);

CREATE TABLE snapshots (
  id                   TEXT PRIMARY KEY,
  created_at           TEXT NOT NULL,
  raw_sha256_set       TEXT NOT NULL,        -- JSON 数组
  schema_version       TEXT NOT NULL,
  extract_prompt_hash  TEXT,
  extract_model        TEXT,
  unit_count           INTEGER,
  as_of                TEXT,                 -- 配合 as_of 查询
  notes                TEXT
);

CREATE TABLE conversations (
  session_id   TEXT PRIMARY KEY,
  scope        TEXT NOT NULL,                -- self / interview / handover
  started_at   TEXT NOT NULL,
  ended_at     TEXT,
  status       TEXT NOT NULL,                -- active / closed / approved / rejected
  approved_raw_sha256 TEXT                   -- 若已 approve 回流，记录新 raw
);

CREATE VIRTUAL TABLE units_fts USING fts5(
  content,
  topics,
  entities,
  tags,
  content=units, content_rowid=rowid
);

CREATE INDEX idx_units_source        ON units(source_kind, sub_kind);
CREATE INDEX idx_units_kind          ON units(kind);
CREATE INDEX idx_units_sensitivity   ON units(sensitivity);
CREATE INDEX idx_units_observed_at   ON units(observed_at);
CREATE INDEX idx_units_valid_until   ON units(valid_until);
CREATE INDEX idx_units_canonical     ON units(canonical_unit_id);
CREATE INDEX idx_units_extracted_by  ON units(extracted_by);
CREATE INDEX idx_topics_unit         ON unit_topics(topic);
CREATE INDEX idx_drifts_status       ON drifts(status);
```

---

# 四、阶段 1：Markdown 内容基座（MVP）

---

## 4.1 目标

```text
跑通整条最小闭环：
  Markdown → L0 → L1（不重写、保 metadata）→ SQLite + FTS5 → twin recall CLI
```

并交付**可 dogfood 的 CLI 工具**、**评估集 v1**、**Schema migrator 基础设施**、**Snapshot 机制**。

---

## 4.2 范围

* ✅ 仅 ingest `source_kind = tech_markdown`
* ✅ L0 / L1 两层完整建立
* ✅ FTS5 关键词检索
* ✅ `twin recall` CLI
* ✅ LLM Router（scope-driven，filter before retrieve）
* ✅ 缓存与重抽取策略（content-hash + prompt-hash + model_id）
* ✅ Schema Migrator 框架（additive 直读 / migrator / reextract 三档）
* ✅ Retrieval API 含 `as_of` / `dedup_by_canonical` / `include_duplicates` 接口预留
* ✅ Snapshot 机制基础（捕获状态指纹，不绑评估集）
* ❌ 不做 embedding（阶段 3 才做）
* ❌ 不做项目维度聚合（阶段 2 做）
* ❌ 不做对外投影 / 脱敏（阶段 3 做）
* ❌ 不做漂移检测（阶段 3 做，但 schema 已留好字段）
* ❌ 不做 canonical 自动选举（阶段 2+，但字段已预留）

---

## 4.3 模块结构

```text
src/
├── ingest/
│   ├── inbox.py                  # L0 写入：sha256 + meta.json
│   ├── chunker.py                # 段落级分块
│   ├── pipeline.py               # ingest 编排
│   ├── cache.py                  # ⭐ 抽取缓存（content + prompt + model）
│   └── profiles/
│       ├── base.py               # IngestionProfile 接口
│       └── tech_markdown.py      # ⭐ 阶段 1 唯一实现
│
├── store/
│   ├── db.py                     # SQLite ORM
│   ├── jsonl_writer.py           # curated/*.jsonl 原子追加
│   ├── jsonl_sync.py             # jsonl → SQLite
│   ├── rebuild.py                # 从 jsonl 重建 DB
│   ├── snapshot.py               # ⭐ Snapshot 捕获与读取
│   └── migrations/
│       ├── __init__.py           # ⭐ Migrator registry
│       └── _example_1.0_to_1.1.py
│
├── retrieval/
│   ├── api.py                    # search(query, filters, k)
│   ├── fts.py                    # FTS5 实现
│   └── ranker.py                 # 简单加权（topic match + recency）
│
├── llm/
│   ├── router.py                 # ⭐ scope-driven，filter before retrieve
│   ├── clients/
│   │   ├── cloud.py              # Claude / GPT
│   │   └── local.py              # Ollama / llama.cpp
│   ├── prompts/
│   │   ├── extract_tech_md.txt
│   │   └── recall_answer.txt
│   └── parser.py                 # tolerant JSON
│
├── cli/
│   ├── ingest.py                 # `twin ingest <path>`
│   ├── recall.py                 # `twin recall <query>`
│   ├── inspect.py                # `twin inspect <unit_id>`
│   ├── rebuild.py                # `twin rebuild-db`
│   ├── promote.py                # `twin promote <unit_id> --to public`
│   ├── reextract.py              # ⭐ `twin reextract`
│   ├── migrate.py                # ⭐ `twin migrate`
│   ├── snapshot.py               # ⭐ `twin snapshot create/list`
│   └── eval.py                   # `twin eval <set>`
│
└── eval/
    ├── runner.py
    ├── metrics.py                # recall@k / faithfulness
    └── capability/
        └── v1.yaml               # 30 道能力评估集
```

---

## 4.4 Ingestion 关键流程

---

### 4.4.1 主流程

```text
[输入] *.md 文件
    ↓
[1] inbox.write(file)
        → sha256 + meta.json → inbox/<date>/<sha256>.md
        → 如果 sha256 已存在，跳过（去重在 L0）
    ↓
[2] cache.check(raw_sha256, current_prompt_hash, current_model)
        → 如果 curated/<source_kind>/<sha256>.jsonl 存在
          AND 文件中所有 units 的 extracted_prompt_hash == current
          AND extracted_by == current_model
          → 跳过抽取（缓存命中）
        → 否则进入 [3]
    ↓
[3] profile.tech_markdown.extract(inbox_path)
        → chunker.split() → chunks
        → 对每个 chunk 调用 LLM 抽取 units
        → 严格 prompt：原文保真、metadata 必填
        → tolerant JSON parser
        → 每个 unit 记录 extracted_by / extracted_at / extracted_prompt_hash
        → canonical_unit_id 默认 = 自己的 id
    ↓
[4] 默认 sensitivity 推定（按 3.5 规则）
        → 写入 unit.sensitivity
    ↓
[5] jsonl_writer.write(units, curated/tech_markdown/<sha256>.jsonl)
        → 原子写入（先 .tmp 再 rename）
    ↓
[6] jsonl_sync.sync(jsonl_path, db)
        → INSERT units / unit_topics / unit_entities / unit_tags
        → FTS5 索引由 trigger 自动更新
    ↓
[完成] meta.ingest_status = "extracted"
```

---

### 4.4.2 抽取 prompt 关键约束

```text
你的任务：从给定的 Markdown chunk 中抽取"原子记忆单元"。

绝对禁止：
  - 改写、融合、总结、重组原文
  - "工程师风格"重写
  - 跨段落合并观点

必须：
  - content 字段保留原句或最小重述
  - 每个独立观点单独抽取
  - 填写 kind / topics / entities
  - 对 fact/concept/procedure：stance=0, valence=0
  - 对 opinion/preference/experience：stance ∈ {-1,0,+1}, valence ∈ [-1,1]
  - confidence ∈ [0,1]
  - 不能确定的字段填 null，不要猜
```

---

## 4.5 缓存与重抽取

---

### 4.5.1 缓存层次（三层）

```text
┌─────────────────────────────────────────────────────────────┐
│ L1: content-level cache                                     │
│   key = raw_sha256                                          │
│   逻辑：同一份原文，已抽取过就不重抽                       │
│   命中条件：curated/<source_kind>/<raw_sha256>.jsonl 存在  │
├─────────────────────────────────────────────────────────────┤
│ L2: extraction-version cache                                │
│   key = (raw_sha256, extracted_prompt_hash, extracted_by)   │
│   逻辑：prompt 或模型变化才重抽                            │
│   命中条件：jsonl 中所有 unit 的 prompt_hash 与 by 匹配当前│
├─────────────────────────────────────────────────────────────┤
│ L3: chunk-level cache（可选）                              │
│   key = sha256(chunk_content + prompt + model)              │
│   逻辑：单个 chunk 级别的细粒度缓存                        │
│   用途：当一个文件部分内容变了，只重抽变化的 chunks       │
└─────────────────────────────────────────────────────────────┘
```

MVP 实现 L1 + L2，L3 留待后续。

---

### 4.5.2 重抽取策略

**不允许自动覆盖旧 unit**。重抽取的实质是：

```text
1. 新抽取产生新 unit（含新 id、新 extracted_at）
2. 旧 unit 不删除，valid_until 设为重抽取时刻
3. 建立 supersedes 关系：new_unit supersedes old_unit
4. 检索默认只返回 valid_until = null 的 unit
5. 可通过 --include-historical 显式查询历史版本
```

---

### 4.5.3 重抽取 CLI

```bash
# 显式指定重抽取范围
twin reextract --raw <sha256>                           # 单个 raw
twin reextract --source tech_markdown                   # 某 source_kind 全部
twin reextract --where "extracted_by != current_model"  # 按条件
twin reextract --where "extracted_prompt_hash != current_prompt_hash"
twin reextract --since 2024-01-01                       # 时间范围
twin reextract --dry-run                                # 只看哪些会被重抽，不执行

# 全局缓存控制
twin ingest <path> --no-cache                           # 完全禁用缓存
twin ingest <path> --force-refresh                      # 强制重抽
```

---

### 4.5.4 缓存与重抽取的关键不变量

```text
🔒 任何重抽取操作都不删除旧 unit
🔒 旧 unit 的 curated jsonl 保留，仅 valid_until 标记
🔒 重抽取永远是 INSERT，不是 UPDATE
🔒 raw 文件本身（inbox）永不修改
```

---

## 4.6 Schema 演进与 Migrator

---

### 4.6.1 三档分级机制（P10 落地）

```text
┌────────────────────────────────────────────────────────────┐
│ L1: Additive（默认）                                       │
│   - 新加字段（含 default 非 null 或 nullable）             │
│   - 旧 jsonl 直读，缺失字段用 default                     │
│   - 零成本，不需要任何 migration                          │
│   示例：加 frequency_signal (default 1)                    │
├────────────────────────────────────────────────────────────┤
│ L2: Renaming / Retyping                                    │
│   - 字段重命名 / 类型变更 / 结构调整                       │
│   - 必须写一个幂等 migrator                                │
│   - 自动备份旧 jsonl 为 *.v<old>.jsonl.bak                 │
│   - 一次性 IO，无 LLM 调用                                 │
│   示例：domain → topics[0]                                 │
├────────────────────────────────────────────────────────────┤
│ L3: Semantic Change                                        │
│   - 抽取逻辑变了（语义级 schema 变化）                     │
│   - 必须触发 reextract                                     │
│   - 高成本（LLM 调用）                                     │
│   示例：新增 kind 枚举值 / 改变 stance 计算方式           │
└────────────────────────────────────────────────────────────┘
```

---

### 4.6.2 判定规则（强约束，写入 PR 检查清单）

```text
✅ Additive 合法：
   - 加字段 + default 不为 null
   - 加可选字段（null 默认）
   - 加新表 / 新索引

❌ 必须走 L2 migrator：
   - 改字段名
   - 改字段类型
   - 改约束（NOT NULL / UNIQUE）
   - 改默认值的语义

❌ 必须走 L3 reextract：
   - 改字段语义（即使名字不变）
   - 改 kind / sensitivity / sub_kind 枚举集合
   - 改抽取 prompt（用 prompt_hash 自动检测）
```

---

### 4.6.3 Migrator 接口

```python
# src/store/migrations/_template.py
class Migration:
    from_version: str    # "1.0"
    to_version: str      # "1.1"
    breaking: bool       # 是否破坏向后兼容
    
    def up(self, unit_dict: dict) -> dict:
        """旧 → 新。必须幂等。"""
    
    def down(self, unit_dict: dict) -> dict:
        """新 → 旧。必须幂等。可选实现。"""

# Registry 自动发现
MIGRATIONS = discover_migrations()  # 按文件名 1.0_to_1.1.py 之类
```

---

### 4.6.4 Migrator CLI

```bash
twin migrate --to 1.1                  # 升到目标版本
twin migrate --to 1.1 --dry-run        # 不写入，只输出会改什么
twin migrate --rollback                # 回滚到上一个 .bak
twin migrate --check                   # 校验所有 jsonl 的 schema_version 一致性
```

**migrator 的执行流程**：

```text
[1] 扫描所有 curated/*.jsonl，按 schema_version 分组
[2] 计算 migration path：current_version → target_version
[3] 对每个文件：
     a) 备份：<sha256>.jsonl → <sha256>.v<old>.jsonl.bak
     b) 逐行 migrate（up）
     c) 原子重写 <sha256>.jsonl
[4] 强制 rebuild-db（落地 P11：SQLite 是 jsonl 派生物）
       - drop 所有表
       - 按当前 SQL schema 重建
       - 从 jsonl 全量加载
       - 重建 FTS5 索引
       - 记录 rebuild_duration 到 logs/
[5] 更新全局 current_schema_version
```

---

### 4.6.5 关键不变量

```text
🔒 Migrator 必须幂等（重跑结果一致）
🔒 任何 migrate 都自动 .bak，永不真删
🔒 schema_version 在每个 unit 上记录（用于多版本共存场景）
🔒 reextract 等价于 "彻底废除旧 unit + 生成新 unit"，
   不是 migrate
🔒 SQLite 是 jsonl 的纯派生物（P11），
   migrator 之后必然 rebuild-db
🔒 SQLite 不维护独立 schema migration 链
```

---

### 4.6.6 Rebuild-db 性能监控与升级阈值

落地 P11 的关键运营机制：rebuild-db 廉价时一直用纯派生物方案；当数据规模导致 rebuild-db 变贵时，再考虑升级架构。

---

#### 监控指标

每次 `twin rebuild-db` 自动记录：

```json
{
  "rebuild_id":         "rb_2026_05_15_001",
  "started_at":         "2026-05-15T16:00:00",
  "duration_ms":        1247,
  "unit_count":         1248,
  "jsonl_file_count":   312,
  "fts_index_ms":       420,
  "triggered_by":       "migrate | manual | reextract | ingest_batch"
}
```

存档到 `data/logs/rebuild.log`。

---

#### 升级阈值（架构 alarm）

```text
默认架构假设：rebuild-db < 10s   → 健康
警告阈值：     rebuild-db ≥ 10s 且 < 60s   → 监控
告警阈值：     rebuild-db ≥ 60s             → 需要升级架构
```

**触发告警时的应对路径**（远期，阶段 4+ 决定是否启用）：

1. **优化方案 A：增量 sync**
   * 不再 drop + recreate
   * jsonl_sync.py 做 diff（按 jsonl 文件 mtime + content_hash）→ 仅 INSERT/UPDATE 变化部分
   * 风险：sync 逻辑容易与真相源不一致

2. **优化方案 B：升级为独立 SQLite migration**
   * 启用 Alembic 式 ALTER TABLE 链
   * jsonl migrator 不再触发 rebuild-db
   * 代价：维护两套 schema 版本链

MVP 阶段不预先做这两个优化。`twin rebuild-db --benchmark` 提供基准测试 CLI，用户监控曲线决定何时升级。

---

#### CLI

```bash
twin rebuild-db                        # 默认：完整重建 + 记录耗时
twin rebuild-db --benchmark            # 仅基准测试，不实际操作
twin rebuild-db --verbose              # 显示各阶段耗时
twin rebuild-stats                     # 查看历史 rebuild 耗时曲线
```

---

## 4.7 LLM Router 检索时序（scope-driven + filter before retrieve）

---

### 4.7.1 核心决策

```text
1. 每次 query 必须声明 scope（默认 self）
   - scope ∈ {self, interview, handover, public}

2. 检索前按 scope 过滤候选 sensitivity 集合：
   - scope=self      → 候选 = {public, internal, private, secret}
   - scope=interview → 候选 = {public, internal}
   - scope=handover  → 候选 = {public, internal}
   - scope=public    → 候选 = {public}
   
   secret 永不参与对外检索路径，杜绝内存侧载 / 日志泄露

3. retrieve top-K（候选集已被 sensitivity 过滤）

4. Router 决策维度：max(unit.sensitivity for unit in retrieved)
   - max ∈ {private, secret}        → 本地模型
   - max == internal AND scope=self → 本地模型（保守）
   - max == internal AND scope ∈ {interview, handover} → 按配置（默认本地）
   - max == public                  → 云端模型

5. 整个 query 走单一 LLM，不按 chunk 拆分
```

---

### 4.7.2 设计权衡

| 选项 | 选 / 不选 | 理由 |
|------|----------|------|
| Filter before retrieve | ✅ 选 | secret 永不进检索路径，错向"过严" |
| Filter after retrieve（仅在 prompt 前剔除） | ❌ 不选 | 敏感内容会进入 retrieval 内存路径 |
| 整个 query 单一 LLM | ✅ 选 | 简单、一致、可审计；保持完整推理能力 |
| Chunk 级路由 + 答案合并 | ❌ 不选 | 复杂度高，合并算法易出错，失去整体推理 |

---

### 4.7.3 同一 query 在不同 scope 下结果不同 —— 这是设计意图

```text
twin recall "我对公司 X 的看法" --scope self
  → 可能返回含 private 的真实评价

twin recall "我对公司 X 的看法" --scope interview
  → 仅返回 internal+public，结果可能完全不同
  → 这是正确行为（scope 的语义本就如此）
```

CLI 必须**始终显式 / 默认 scope**，避免歧义。

---

### 4.7.4 实现草图

```python
SCOPE_ALLOWED = {
    'self':      {'public', 'internal', 'private', 'secret'},
    'interview': {'public', 'internal'},
    'handover':  {'public', 'internal'},
    'public':    {'public'},
}

def search(query, scope='self', k=10, filters=None, fallback='abort') -> SearchResult:
    # 1. 强制按 scope 过滤候选 sensitivity
    sensitivity_filter = SCOPE_ALLOWED[scope]
    filters = (filters or SearchFilter()).with_sensitivity(sensitivity_filter)
    
    # 2. 检索（候选集已被过滤）
    candidates = retrieval_api.search(query, filters, k)
    
    # 3. 计算路由依据
    max_sensitivity = max_sens(candidates) or 'public'
    
    # 4. 路由（含 fail-safe，见 4.7.5）
    llm = router.route(scope=scope, max_sensitivity=max_sensitivity, fallback=fallback)
    
    return SearchResult(
        units=candidates,
        llm_client=llm,
        routed_to=llm.identifier,
        scope=scope,
    )
```

---

### 4.7.5 Router 故障路径（fail-safe）

落地 P12。本地模型不可用（Ollama 未启动 / 显存不足 / 模型损坏 / 健康检查超时）时的行为：

---

#### 决策矩阵

| 触发条件 | 默认行为 | 用户可选 |
|---------|---------|---------|
| 本地模型不可用 + 仅需 public 内容 | 走云端（无变化） | — |
| 本地模型不可用 + 需 internal/private/secret | **硬失败（abort）** | `--fallback public-only` |
| **任何情况下** | **永不静默云端兜底** | （这是 P12，不可关闭） |

---

#### 三种 fallback 模式

```text
1. abort（默认）
   → 直接报错终止
   → 错误信息：
       "Local model unavailable. Query requires sensitivity={...} 
        which cannot route to cloud. Use --fallback public-only 
        to query public content only, or fix local model."

2. public-only（用户显式启用）
   → 自动把 scope 临时降级为 public（仅查询 public 内容）
   → 输出明确标注 "FALLBACK MODE: public content only"
   → 不查询 / 不返回任何 internal+ 的 unit

3. cloud-anyway（永不可用 ✗）
   → 设计上禁止存在
   → 即使用户尝试设置，配置层拒绝（P12 是硬约束）
```

---

#### 健康检查机制

```python
class LocalLLMClient:
    def health_check(self, timeout=5) -> bool:
        """
        启动时 + 每次路由前快速 ping
        失败缓存 60s，避免每次 query 都重新尝试
        """
```

---

#### CLI

```bash
# 默认行为：本地不可用 → abort
twin recall "我对 X 的看法"

# 显式降级（仅查询 public）
twin recall "我对 X 的看法" --fallback public-only

# 健康检查
twin router health             # 检查所有 LLM client 状态
```

---

#### 配置

```yaml
# config/router.yaml
local_model_health_check:
  enabled:           true
  ping_timeout_ms:   5000
  failure_cache_s:   60          # 失败缓存时长

fail_safe:
  default_behavior:                abort
  allow_public_only_fallback:      true   # 允许 --fallback public-only
  never_silent_cloud_fallback:     true   # 硬约束（P12）
```

---

#### 关键不变量

```text
🔒 本地模型不可用时，含敏感内容的 query 默认硬失败
🔒 任何形式的"静默云端兜底"被设计上禁止（P12）
🔒 用户显式降级也只能"剔除敏感、仅查 public"，
   而不是"用云端处理敏感"
🔒 fallback 行为必须在输出中显式标注
```

---

## 4.8 `twin recall` CLI（可感知产出）

---

### 命令形态

```bash
# 自然语言查询（默认 scope=self）
twin recall "我对 redis lua scripting 是什么观点？"

# 显式 scope
twin recall "..." --scope interview

# 结构化查询
twin recall --topic redis --kind opinion
twin recall --since 2024-01-01 --sensitivity private

# 显示检索过程（debug 用）
twin recall "x" --explain --k 10

# 包含历史版本（已 supersede 的旧 unit）
twin recall "x" --include-historical

# 时间点查询（阶段 3 简化版上线，阶段 1 报 NotImplementedError）
twin recall "x" --as-of 2024-03-01

# 显式禁用 canonical 去重（看所有 same_as 变体）
twin recall "x" --include-duplicates

# 本地模型不可用时的 fallback（默认 abort）
twin recall "x" --fallback public-only
```

---

### 输出样例

```text
$ twin recall "我对 redis lua scripting 是什么观点？"
  scope: self   |   routed: claude-sonnet-4.5@cloud   |   dedup: canonical

[Top 3 matches]

【1】 unit:a3f2c891  (score: 0.87)
  kind: opinion          stance: +1        valence: +0.3
  topics: redis, lua
  same_as_count: 3       total_freq: 8     (use --include-duplicates)
  content: "Lua scripting 用于原子操作很好，但调试体验很差，
            生产慎用复杂脚本"
  source:  inbox/2024-09-10/a3f2c891.md @ line 23-26
  observed_at: 2024-09-10
  extracted_by: claude-sonnet-4.5@2026-05

【2】 unit:b7e8...  (score: 0.71)
  kind: experience
  content: "在 X 项目里用 Lua + Redis 实现了限流，遇到的坑是..."
  ...

【LLM Answer】
你对 Redis Lua scripting 的核心观点：
- 认可用于原子操作 [1]
- 不推荐复杂脚本，因调试体验差 [1]
- 实践中用于限流，但要避免...  [2]

参考：unit:a3f2c891, unit:b7e8...
```

---

### 关键约束

* **强制 citation**：LLM 答案中每个事实陈述必须带 `[N]` 引用
* **检索分数低于阈值时拒绝回答**：不外推
* **支持引用回原文**：从 unit → raw_sha256 → inbox 文件
* **scope + dedup + routed 必显示**：可审计

---

## 4.9 Snapshot 机制基础

---

### 4.9.1 Snapshot 是什么

**逻辑指纹，不是数据物理拷贝**。记录某时刻"知识库的状态摘要"，配合 `as_of` 查询可"回放"到该时刻。

```json
{
  "snapshot_id":         "snap_2026_05_15",
  "created_at":          "2026-05-15T15:00:00+08:00",
  "as_of":               "2026-05-15T14:59:59+08:00",
  "raw_sha256_set":      ["a3f2...", "b7e8...", "..."],
  "schema_version":      "1.0",
  "extract_prompt_hash": "...",
  "extract_model":       "claude-sonnet-4.5@2026-05",
  "unit_count":          1247,
  "notes":               "before upgrading to prompt v2"
}
```

---

### 4.9.2 阶段 1 范围

* ✅ Schema 中加 snapshots 表
* ✅ `twin snapshot create / list / show` CLI
* ✅ 触发条件：手动 + schema migrate 前自动 + reextract 前自动
* ⏸ 与回归评估集绑定（阶段 3）
* ⏸ as_of 查询消费 snapshot（阶段 6）

---

### 4.9.3 CLI

```bash
twin snapshot create --notes "before prompt upgrade"
twin snapshot list
twin snapshot show <snapshot_id>
twin snapshot diff <id1> <id2>           # 简单 diff：unit_count、新增 raw 等
```

---

## 4.10 Acceptance（阶段 1 完成标准）

```text
✅  任意 .md 文件 → inbox sha256 入库（content-addressed，dedup）
✅  tech_markdown extractor 工作，6 个核心字段非空率 ≥ 90%
✅  curated/<source_kind>/<raw_sha256>.jsonl 1:1 组织
✅  SQLite + FTS5 索引建立完整
✅  缓存命中：重复 ingest 同一文件 → 完全跳过 LLM 调用
✅  重抽取命中：prompt 或 model 变化 → 自动检测出 stale units
✅  `twin recall <query>` 能返回 Top K matches + LLM 答案 + 引用
✅  `twin recall` 输出始终显示 scope + dedup + routed
✅  `twin inspect <unit_id>` 能定位回 inbox 原文行号
✅  `twin rebuild-db` 能从 jsonl 重建整个 DB
✅  `twin reextract --dry-run` 能列出哪些 units 需要重抽
✅  `twin migrate --dry-run` 能在 schema_version 不匹配时报告差异
✅  `twin snapshot create` 能生成 snapshot JSON
✅  LLM Router 工作：
       - secret 内容在 scope=interview 时永不出现在检索结果
       - sensitivity=private 路由本地，public 路由云端
       - 单一 query 走单一 LLM
       - 本地模型故障时默认硬失败
       - `--fallback public-only` 工作，且日志明确标注 FALLBACK
       - 任何情况下不会静默走云端处理敏感内容
✅  `twin rebuild-stats` 能展示历史 rebuild 耗时（阶段 1 期望 < 10s）
✅  Retrieval API 接口齐备：
       - observed_since / observed_until 工作
       - as_of 参数存在，传入时抛 NotImplementedError
       - dedup_by_canonical 默认 true（每 unit 暂时自成一组，效果等同不去重）
✅  评估集 v1（30 道能力评估）跑过：
       - Recall@5 ≥ 60%
       - Faithfulness ≥ 80%
✅  ingestion 日志完整，失败可重试
```

---

## 4.11 阶段 1 风险与缓解

| 风险 | 缓解 |
|------|------|
| 抽取 LLM 输出不稳定，JSON 解析失败 | tolerant parser + 3 次重试 + 失败日志 |
| 抽取出大量"标题级"低质量 unit | chunker 配段落最小长度过滤 + LLM 显式拒绝 |
| sensitivity 默认 private 过严，全部不可用 | CLI `twin promote --batch` 批量调整工具 |
| curated.jsonl 与 SQLite 不一致 | jsonl 是真相源，DB 任何时刻可 rebuild |
| 评估集 Recall@5 < 60% | 退路 1：调 prompt；退路 2：提前引入 BM25-only 增强 |
| 抽取太慢，全量首跑数小时 | 文件级缓存 + ThreadPoolExecutor 并发抽取 |
| 模型/prompt 频繁升级 → 重抽爆炸 | reextract 默认手动触发，dry-run 看影响 |
| Schema additive 误判为 breaking（或反之） | PR 模板含 schema-change 检查清单；migrator 必须配套 |
| Migrator 不幂等导致数据损坏 | 强制 .bak + dry-run + rollback CLI |
| Router 在敏感判定上失误 | 默认 private，错偏严；本地模型质量再差也优先用 |

---

# 五、阶段 2：Git 项目经验沉淀

---

## 5.1 目标

把你的 git 仓库（FARL / 其他）作为内容源，抽取"**项目经验**"维度的知识，并提供项目视图。

---

## 5.2 范围

* ✅ ingest `source_kind = code_repo`，覆盖 5 个 sub_kind：
  * `commit` / `pr` / `readme` / `issue` / `code_comment`
* ✅ 项目维度聚合视图
* ✅ `twin project <name>` CLI
* ✅ 评估集 v2（+20 道项目相关）
* ✅ 启动 `canonical_unit_id` 自动选举（基于 same_as 关系）

---

## 5.3 新增模块

```text
src/ingest/profiles/
└── code_repo.py             # ⭐ git 仓库扫描 + 多 sub_kind 抽取

src/aggregation/
├── project_view.py          # 项目维度聚合
└── aspects/
    ├── decisions.py
    ├── pitfalls.py
    ├── tech_choices.py
    └── todos.py

src/store/
└── canonical.py             # ⭐ canonical 选举（同 same_as 组中）

src/cli/
└── project.py               # `twin project`
```

---

## 5.4 Ingestion 关键设计

---

### 5.4.1 commit 抽取

每个 commit：
* `content`：commit message（如有有意义内容）
* `kind`：通常 `decision` 或 `experience`
* `topics`：从 commit 涉及的文件/路径推断
* `entities`：从 message + diff 中抽取
* `observed_at`：commit 时间

低质量 commit（如 `fix typo`）跳过抽取。

---

### 5.4.2 PR / issue 抽取

PR 描述往往含**决策依据 + 权衡**，是项目经验的金矿。

* PR description → 1~N 个 unit，主要是 `decision`
* PR review 评论中我的回复 → `opinion / decision`
* issue 中我的回复 → 同上

---

### 5.4.3 readme / design docs

走 `tech_markdown` 类似流程，但 `source_kind: code_repo, sub_kind: readme`，并打项目 tag。

---

### 5.4.4 跨 source_kind 关联

很多时候 design doc 在仓库里也在笔记里有副本。通过 content_hash 检测，建立 `same_as` 关系，跨 source_kind 共享一个观点。

→ 触发 canonical 选举。

---

## 5.5 Canonical 选举（启用）

---

### 5.5.1 触发时机

* 新建 `same_as` 关系时
* **某 unit 的 `valid_until` 发生变化时**（重抽取 / 漂移修复 / 用户校正）
* 手动 `twin canonical rebuild`

> `valid_until` 变化必须触发重选举，否则会出现"canonical 已 expire 但仍被检索返回"的 bug。

---

### 5.5.2 算法

```python
def elect_canonical(group: list[Unit]) -> str | None:
    # 第 0 步：仅从有效 unit 中选举（关键约束）
    valid_group = [u for u in group if u.valid_until is None]
    
    if not valid_group:
        # 整组已 expire，无 canonical
        # 该组在默认检索中不出现（include_historical 才能看到）
        for u in group:
            u.canonical_unit_id = None
        return None
    
    # 第 1~5 步：按优先级排序
    sorted_group = sorted(valid_group, key=lambda u: (
        -int(u.human_verified),
        -int(u.verified and u.verification_method != 'agent_self'),
        -u.frequency_signal,
        -captured_at_unix(u),
        u.id,    # 字典序兜底
    ))
    canonical_id = sorted_group[0].id
    
    # 整组（含 expired 的）都指向同一 canonical
    # 这样 include_historical=True 时仍能看到完整组关系
    for u in group:
        u.canonical_unit_id = canonical_id
    return canonical_id
```

---

### 5.5.3 边缘情况

| 场景 | 行为 |
|------|------|
| 组内全部 valid | 正常选举 |
| 组内部分 expired | 仅从 valid 中选；canonical 永远是 valid |
| 组内全部 expired | `canonical_unit_id = NULL`；默认检索整组不出现 |
| 新建 same_as 关系连接两组 | 触发合并选举（按合并组的 valid 候选集重选） |
| canonical unit 自己被 expire | 立即重选举（落地 5.5.1 触发条件） |

---

### 5.5.3 CLI

```bash
twin canonical show <unit_id>           # 查看某 unit 所在组
twin canonical rebuild --all            # 强制重选举
twin canonical pin <unit_id>            # 手动锁定某 unit 为 canonical
```

---

## 5.6 `twin project <name>` CLI

---

### 输出形态

```text
$ twin project FARL

# FARL 项目（数字分身视角）

【元信息】
  仓库:       D:/Codes/Others/FARL
  时间跨度:   2024-08 ~ 2026-05
  unit 数量:  127
  最近活动:   2026-05-14

【关键决策】（kind=decision，按时间倒序）
  [2026-05-13] Factorio 1.0 → 2.0 升级
    依据: ...
    源:   commit a3f2c... + design_4.md
  [2024-12-04] Lua VM 内存隔离方案选 luajit-isolate
    依据: ...
  ...

【踩过的坑】（kind=experience AND valence < 0）
  - ...

【技术选型】（kind=decision AND tags 含 tech_choice）
  - ...

【未完成 / TODO】（kind=plan AND valid_until=null）
  - ...
```

---

### 命令参数

```bash
twin project FARL
twin project FARL --since 2024-01-01
twin project FARL --aspect decisions
twin project FARL --aspect pitfalls
twin project FARL --export handover-draft.md     # 生成交接初稿
```

---

## 5.7 Acceptance

```text
✅  任意 git 仓库 → 扫描成功 → L1 units 入库
✅  5 个 sub_kind（commit / pr / readme / issue / code_comment）都能抽取
✅  低质量 commit 自动过滤
✅  Canonical 选举：建立 same_as 关系后自动选举正确 canonical
✅  project view 输出 4 个 aspect（决策 / 坑 / 选型 / TODO）
✅  `twin project <name>` 工作
✅  `--export handover-draft.md` 可生成交接初稿（即阶段 3 准备物）
✅  评估集 v2（+20 道）Recall@5 ≥ 70%
```

---

# 六、阶段 3：对话场景（面试 / 交接）+ 漂移检测

---

## 6.1 目标

* 实现实时对话能力。按 "**3-A 脚本化 → 3-B 模板化 → 3-C 开放对话 + 护栏**" 三步推进，每一步都可独立交付。
* 上线 **漂移检测与时效性验证**机制，确保对话不输出过时信息。
* 实现 **对话状态管理**：draft 走 State Store，approved 回流 L0-L1。
* 实现 **回归评估集**，绑定 snapshot。

---

## 6.2 范围

* ✅ Embedding 索引上线，替换 FTS5 作为主检索手段（FTS5 保留作辅助）
* ✅ Projection 引擎（L3）：scope-aware 投影
* ✅ Redactor 脱敏引擎
* ✅ **对话状态管理（State Store + approved 回流 L0-L1）**
* ✅ 漂移检测三级分类机制
* ✅ 联网验证（web search）
* ✅ 3-A 脚本化问答：固定问题清单 + 人工审阅闭环
* ✅ 3-B 模板对话：intent + slot
* ✅ 3-C 开放对话 + 护栏
* ✅ 回归评估集（与 snapshot 绑定）
* ✅ 评估集 v3（+50 道场景化）

---

## 6.3 对话三步走

---

### 6.3.1 阶段 3-A：脚本化问答（首先实现）

```text
固定问题清单 (yaml)
   ↓ 每个问题预定义检索路径（topics / tags / kind filter）
   ↓ scope = interview | handover
[1] 检索：retrieval.search(filters, k=10)
[2] 投影：projection.project(units, scope)
[3] 脱敏：redactor.redact(units, scope)
[4] LLM 生成答案（含强制 citation + 漂移自检）
[5] 写入 conversations/<session_id>/drafts/q_<id>.md
[6] 人工 review：approved / need_edit / rejected
[7] 若 approved → 触发 ingest 回流 L0-L1（见 6.5）
```

---

### 6.3.2 阶段 3-B：模板对话（intent + slot）

```text
intent: "项目深入提问"
slots:
  - project_name: required
  - aspect: [decisions | tech_choices | pitfalls | timeline] required
  - depth: [overview | detail] default=overview

检索模板：
  filters = {
    topics: ⊇ {project_name},
    kind: aspect 对应的 kind,
    sensitivity: scope-allowed
  }
```

每个 intent 对应一个 prompt 模板 + 检索 + 生成流程。

---

### 6.3.3 阶段 3-C：开放对话 + 护栏（终态）

---

#### 护栏清单

| 护栏 | 触发条件 | 动作 |
|------|---------|------|
| 不知道就拒答 | top-1 score < threshold | "我对此没有记录" |
| sensitivity 硬过滤 | scope=interview 但 unit.sensitivity < internal | 该 unit 不进入 prompt（filter before retrieve 已保证） |
| Citation 强制 | LLM 输出未带 `[unit_id]` | 重生成 / 拒答 |
| 不外推 | LLM 试图基于"一般情况"推测 | 检测 + 拒答 |
| 实体黑名单 | 输出含人名 / 公司 / 未公开项目名 | 自动 redact |
| 矛盾告警 | retrieved units 含 contradicts 关系 | 答案中显式说明 |
| 漂移检测 | retrieved units 与 agent 知识冲突 | 见 [6.6](#66-漂移检测与时效性验证) |

---

#### 监控指标

* 拒答率（rejection_rate）
* 降级率（fallback_to_scripted_rate）
* Redaction 触发次数
* Citation 完整率
* Drift 触发率（按三级分类统计）

任意指标越线立刻拉回到 3-B / 3-A 形态。

---

## 6.4 Projection / Redactor 引擎

---

### Projection（scope-aware 投影）

```python
def project(units: list[Unit], scope: str) -> list[Unit]:
    allowed = SCOPE_ALLOWED[scope]
    return [
        u for u in units
        if effective_sensitivity(u, scope) in allowed
    ]

def effective_sensitivity(u, scope):
    if scope in u.visibility_overrides:
        return u.visibility_overrides[scope]
    return u.sensitivity
```

> 注：在 P8 Router 设计中，**filter before retrieve 已经在 SearchFilter 阶段完成 sensitivity 过滤**。Projection 是二次防御 + 处理 `visibility_overrides` 字段。

---

### Redactor（脱敏）

```python
def redact(unit: Unit, scope: str) -> Unit:
    rules = load_rules(scope)
    text = unit.content
    text = redact_persons(text, rules.allowed_persons)
    text = redact_companies(text, rules.allowed_companies)
    text = redact_projects(text, rules.allowed_projects)
    text = redact_numbers(text, rules.allowed_metrics)
    text = redact_dates(text, rules.allowed_periods)
    return unit.with_content(text)
```

---

## 6.5 对话状态管理（State Store + approved 回流）

---

### 6.5.1 总览（落地 P9 + 决策 10）

```text
┌──────────────────────────────────────────────────────────────┐
│  External State Store（外挂，不进 L0-L1）                    │
│    位置：data/conversations/<session_id>/                    │
│    包含：                                                    │
│      - 对话进行中的 session state                            │
│      - 检索中间产物（query / retrieved units 记录）         │
│      - draft / pending / need_edit 审阅状态                  │
│      - LLM 生成的中间答案版本                               │
│      - 临时数据，可被丢弃                                    │
└──────────────────────────────────────────────────────────────┘
                            ↓
            (审阅通过 approved → 触发 ingest)
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  L0-L1（流入记忆系统）                                       │
│    回流的是 transcript（事件记录），不是 answer（派生物）！  │
│                                                              │
│    L0 写入：                                                 │
│      - transcript markdown（含 Q + 最终 A + retrieved refs   │
│        + approved 标签 + 审阅时间）                         │
│      - source_kind: conversation                             │
│      - sub_kind: interview / handover / qa                   │
│      - provenance: "conversation_transcript"                 │
│      - origin_session_id: <session_id>                       │
│                                                              │
│    L1 抽取：                                                 │
│      - 从 transcript 中抽出 units                            │
│      - 默认 confidence = 0.7（中等，因含 LLM 生成成分）     │
│      - verified=true, verification_method=human              │
│      - kind 优先 experience / fact，避免 opinion              │
│      - 与现有 unit 通过 content_hash 检测建立 same_as       │
│                                                              │
│    用户校正：                                                │
│      - 写入新 unit（校正内容是用户亲表达）                  │
│      - 建立 relation: new_unit corrects old_unit             │
│      - old_unit.valid_until = now                            │
└──────────────────────────────────────────────────────────────┘
```

---

### 6.5.1.1 为什么 transcript 可以进 L0（而 answer 不行）

| 内容 | 是不是事实？ | 是不是派生物？ | 进 L0？ |
|------|------------|-------------|--------|
| 原始技术笔记 | ✅ | ❌ | ✅ |
| 用户日记 | ✅ | ❌ | ✅ |
| **对话 transcript（"在 X 时刻进行了这场对话，最终 approved 是这个版本"）** | ✅ 是事件 | ⚠️ 内容含派生 | ✅ |
| **LLM 生成的 raw answer（未审阅）** | ❌ | ✅ | ❌ |
| handover-draft.md（项目导出） | ❌ | ✅ | ❌（永远不会回流） |

**核心判定**：

> transcript 记录的是 "**这场对话发生了**"——这是不可重建的历史事件。
> LLM 答案的具体措辞可以重建（虽然不稳定），但"用户审阅后 approved 这个版本"是只此一次的事件。
>
> 因此 transcript 配 L0 身份，但其抽取出的 units 不能被当成"高置信事实"——所以默认 confidence=0.7、避免标 opinion。

---

### 6.5.2 State Store 结构

```text
data/conversations/<session_id>/
├── meta.json              # scope, started_at, status
├── transcript.jsonl       # 每轮对话（query / retrieved unit_ids / generated answer）
├── reviews/               # 人工审阅记录
│   └── q_<id>.review.json
└── drafts/                # 待审阅 / 已 need_edit 的草稿
    └── q_<id>.md
```

`meta.json`：

```json
{
  "session_id": "sess_2026_05_15_001",
  "scope": "interview",
  "started_at": "2026-05-15T10:00:00+08:00",
  "ended_at": null,
  "status": "active | closed | approved | rejected",
  "approved_raw_sha256": null
}
```

---

### 6.5.3 触发 L0-L1 写入的事件

```text
event: review.approved
  → 渲染 transcript 为 markdown（这是事件记录，不是答案缓存）：
       ```
       # Conversation Transcript
       session: <sid>    scope: <scope>
       started_at: <ts>  approved_at: <ts>
       
       ## Q
       <question>
       
       ## A (approved version)
       <approved_answer_text>
       
       ## Review Notes
       <human review notes if any>
       
       ## References
       Retrieved units: unit:..., unit:...
       ```
     → 写入 inbox/<date>/<sha256>.md
        - source_kind: conversation
        - sub_kind: <scope 对应：interview/handover/qa>
        - provenance: "conversation_transcript"   # 不是 "_approved"
        - origin_session_id: <session_id>
     → 走标准 ingestion pipeline（ConversationProfile）
     → 抽取出 units 进 L1，其中：
        - 用户在 transcript 中**亲表达**的内容 → 正常 unit（confidence 按内容）
        - 来自 LLM 生成的事实陈述 → kind=fact, confidence=0.7
        - 答案中的观点表述 → 保守不抽（避免污染 L1 的"我的观点"）

event: user.correction
  → 用户标记某个 unit 内容不准确，提供新内容
  → 抽取出新 unit（content = 用户亲表达的新内容）
  → 建立 relation: new_unit corrects old_unit
  → old_unit.valid_until = now
  → 新 unit.verified = true, verification_method = "human"
  → 新 unit.confidence = 0.9（用户亲表达，置信度高）
  → 触发 canonical 重选举（5.5.1 触发条件）
```

---

### 6.5.3.1 抽取约束（ConversationProfile 特殊规则）

抽取 prompt 必须显式区分 transcript 中的两类内容：

```text
你在抽取 conversation transcript：

【高置信内容（confidence ≥ 0.8）】
  - 用户亲口说的话（Q 中的陈述、Review Notes 中的注释）
  - 用户校正过的内容

【中置信内容（confidence = 0.7）】
  - LLM 生成且 approved 的 fact 类陈述
  - 标记 kind=fact / experience / concept（不标 opinion）

【不抽取】
  - LLM 生成的 opinion / preference / feeling
  - 任何"系统推测"的观点
  - 重复检索来源单元的内容（避免冗余）
```

这是为了防止 LLM 生成的内容被错误地以"用户观点"形式回流到 L1。

**注意 `corrects` 与 `supersedes` 的语义区别**：

| 关系 | 触发方 | 语义 |
|------|--------|------|
| `corrects` | 用户主动校正 | "原 unit 写得不准确" |
| `supersedes` | 漂移检测 / 重抽取 / 事实演化 | "事实变化了，新旧都对、只是时间不同" |

---

### 6.5.4 ConversationProfile（Ingestion Profile）

```python
class ConversationProfile(IngestionProfile):
    source_kind = "conversation"
    
    def detect(self, raw_path):
        # 检查 meta 中 provenance == "conversation_transcript"
        ...
    
    def extract(self, raw_sha256):
        # 走 conversation 专用 prompt（见 6.5.3.1）：
        # - 区分用户亲表达 vs LLM 生成
        # - LLM 生成的事实 → confidence=0.7, kind=fact
        # - LLM 生成的观点 → 不抽取
        # - 用户亲表达 → 正常抽取
        # - 默认 sensitivity 按 sub_kind 推定
        # - extracted_prompt_hash 与 tech_markdown 不同
        ...
```

---

### 6.5.5 CLI

```bash
twin chat --scope interview                  # 启动对话 session
twin chat --resume <session_id>              # 恢复

twin review <session_id>                     # 进入审阅 UI
twin review <session_id> q_001 --approve     # 标记审阅状态
twin review <session_id> q_001 --need-edit
twin review <session_id> --close             # 关闭 session

twin correct <unit_id> --new-content "..." --reason "..."
                                             # 用户主动校正
```

---

### 6.5.6 关键不变量

```text
🔒 draft / pending / need_edit 永远在 State Store，不进 L0-L1
🔒 只有 approved 和 user.correction 才触发 L0-L1 写入
🔒 写入 L0 的是 transcript（事件记录），不是 answer（派生物）
🔒 provenance: "conversation_transcript"（明确语义：是事件，不是答案缓存）
🔒 ConversationProfile 抽取时区分用户亲表达 vs LLM 生成：
   - 用户亲表达 → 正常 confidence
   - LLM 生成的 fact → confidence=0.7
   - LLM 生成的 opinion / preference / feeling → 不抽取
🔒 用户校正建立 corrects 关系而非 supersedes
🔒 校正不修改旧 unit（valid_until 标记，保留全部历史）
🔒 校正触发 canonical 重选举
🔒 派生物（如 handover-draft.md、project view 报告）永远不回流 L0
   —— 它们是 100% 派生物，可幂等重建
```

---

## 6.6 漂移检测与时效性验证

---

### 6.6.1 核心思想

> 知识演化是 **lazy + on-demand**：
>
> * ingestion 阶段不主动找冲突
> * 在 query / 对话阶段，LLM 自然感知 retrieved units 与自身世界知识的差异
> * 冲突时按严重度分级处理，最终落地为新 unit（不修改旧 unit）

---

### 6.6.2 三级分类

```text
┌─────────────────────────────────────────────────────────────────┐
│ Level 1: auto_fix_eligible      (拼写/格式/明显笔误)           │
│   - LLM 高置信度判定为"低级错误"                              │
│   - 不改变语义、不改变主观字段                                 │
│   → 自动修复，但保留审计与 undo                                │
├─────────────────────────────────────────────────────────────────┤
│ Level 2: needs_review           (事实漂移)                      │
│   - 命令参数变更、API 变更、版本变更                          │
│   → 强制 confirm（不允许 agent 越权）                          │
├─────────────────────────────────────────────────────────────────┤
│ Level 3: needs_user_decision    (主观变化)                     │
│   - stance / valence / 观点改变                                │
│   → 仅用户能决定，agent 无权                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 6.6.3 三级分类示例

| 旧 content | 新输入 / 训练知识 | 分类 | 默认行为 |
|-----------|------------------|------|---------|
| "用 `reids-cli` 连接" | "redis-cli" | **L1 auto_fix** | 自动修（编辑距离 1） |
| "命令是 `KETS`" | "KEYS" | **L1 auto_fix** | 自动修（字母换位） |
| "Redis 默认端口 6739" | "6379" | **L1 auto_fix** | 自动修（数字换位） |
| "Redis 没有用户权限管理" | "Redis 6.0+ 有 ACL" | **L2 needs_review** | confirm 后写新 unit |
| "Lua 5.3 移除了 `setfenv`" | "Lua 5.2 就移除了" | **L2 needs_review** | confirm（事实细节） |
| "我认为 NoSQL 比 SQL 简单" | （用户态度变了） | **L3 needs_user_decision** | 必须用户主动改 |
| "我对 X 持中立" → "我反对" | stance 变化 | **L3 needs_user_decision** | 必须用户主动改 |

---

### 6.6.4 自动修复（Level 1）的护栏

---

#### 护栏 A：自动修复**不真的销毁旧 unit**

```text
1. 写入新 unit
   - content: 修正后的内容
   - kind: typo_fix
   - verified: true
   - verification_method: agent_self
   - drift_classification: "typo_fix"

2. 建立关系: new_unit supersedes old_unit

3. 旧 unit 设置 valid_until = now
   - 旧 unit 仍在 curated/.../<sha256>.jsonl 中保留
   - 仍可通过 --include-historical 查询到

4. 写入 drift_log（drifts/applied/d_<id>.json）
```

---

#### 护栏 B：多重合取条件（缺一不可）

```text
auto_fix 触发的所有条件（AND）：

  1. LLM "这是 typo" 置信度 ≥ 0.95
  2. Levenshtein 编辑距离 ≤ 5
  3. Embedding 余弦相似度 ≥ 0.95
  4. 不改变关键字段：
       - kind 不变
       - stance 不变
       - sensitivity 不变
       - confidence 容差 ≤ 0.1
       - valence 容差 ≤ 0.1
  5. 配置中 auto_fix_enabled: true

任何一条不满足 → 降级为 needs_review，走 confirm 流程。
```

---

#### 护栏 C：默认 OFF，渐进式启用

```text
阶段 3 初版上线时：
  auto_fix_enabled: false  ← 默认全部走 confirm

用户用一段时间，觉得"每次拼写错误都让我 confirm 很烦"，
再手动改 config：
  auto_fix_enabled: true

即使打开，每次自动修都有审计 + 可 undo
```

---

#### 护栏 D：完整审计 + 一键 undo

```bash
twin drift-report                  # 列出所有 drift 处理历史
twin drift-report --auto-only      # 仅看自动修
twin drift-report --since 2026-05-01

twin undo-drift <drift_id>         # 回滚单个自动修
twin undo-drift --auto --since 2026-05-15  # 批量回滚一段时间
```

---

### 6.6.5 完整漂移检测流程

```text
用户: twin recall "Redis 的 ACL 用户权限怎么用？" --scope self

[1] 检索 → retrieved units:
       unit_x (2024-03):
         "Redis 没有用户权限管理，只能靠 requirepass 做整库密码"

[2] LLM 生成答案时同时启用 "drift_check" 模式：
       LLM 自我对比：
         retrieved unit 主张 "无 ACL"
         vs 我的训练知识 "Redis 6.0 引入 ACL"
       → 输出结构化 conflict signal

[3] CLI 输出：

   [Answer based on memory]
   你的记忆里 (2024-03)：Redis 没有用户权限管理 [unit_x]

   ⚠ Knowledge Drift Detected (classification: needs_review)
   Agent 训练知识与上述记忆冲突：Redis 6.0+ 引入了 ACL 命令

   操作：
     [v] verify  → 联网验证
     [a] accept agent knowledge (写入新 unit + supersedes)
     [k] keep memory unchanged
     [d] discuss   → 进入对话模式

[4] 用户选 verify：
       触发 web search
       → 获取权威来源（官方文档 / changelog）
       → LLM 综合证据，输出结论 + citation

[5] 输出验证结果，让用户确认是否：
       (a) 写入新 unit_y（含 verified=true + verified_by=<url>）
       (b) 建立 unit_y supersedes unit_x
       (c) 设置 unit_x.valid_until = 验证时刻

       这一步必须用户显式 confirm，不静默写入。
```

---

### 6.6.6 漂移检测的默认开关

| 配置项 | 默认值 | 含义 |
|--------|--------|------|
| `drift_check_enabled` | `true` | 每次 query 都让 LLM 自检（提示但不行动） |
| `auto_fix_enabled` | `false` | L1 漂移是否自动修（默认 OFF） |
| `confirm_required_for_l2` | `true` | L2 必须 confirm |
| `confirm_required_for_l3` | `true` | L3 必须 confirm（不可关闭） |
| `web_verify_on_demand` | `true` | 用户选择 verify 时才触发联网 |
| `auto_web_verify_for_l2` | `false` | L2 是否自动联网验证（默认 OFF） |

---

### 6.6.7 命令清单

```bash
# 显式触发验证
twin recall "x" --verify              # 强制走全验证流程
twin verify <unit_id>                 # 显式验证某个 unit

# 漂移报告与管理
twin drift-report                     # 列出近期 drift 提示历史
twin drift-report --pending           # 仅看待处理
twin drift-report --auto-only         # 仅看自动修

# 应用 / 回滚
twin confirm-drift <drift_id>         # 应用某个 pending 的 drift 提议
twin reject-drift <drift_id>          # 拒绝
twin undo-drift <drift_id>            # 回滚已应用的 drift
```

---

## 6.7 Acceptance

```text
✅  Embedding 索引上线，Recall@5 ≥ 80%
✅  简化版 as_of 工作：`SearchFilter(as_of=...)` 不再抛 NotImplementedError
       - 基于 valid_from / valid_until 过滤
       - 完整 bitemporal 升级留待阶段 6
✅  Projection 引擎：scope=interview 时正确剔除 private 内容
✅  Redactor：人名 / 公司 / 未公开项目自动脱敏
✅  对话状态管理：
       - draft/pending 仅在 State Store
       - approved 触发 transcript（事件记录）回流 L0-L1
       - provenance: "conversation_transcript"
       - ConversationProfile 抽取时区分用户亲表达 vs LLM 生成
       - LLM 生成的 fact 默认 confidence=0.7
       - LLM 生成的 opinion / preference 不抽取
       - 用户校正建立 corrects 关系，旧 unit valid_until 标记
       - 校正触发 canonical 重选举
✅  漂移检测三级分类工作：
       - L1 触发自动修（默认 OFF；启用后行为正确）
       - L2 触发 needs_review + 用户 confirm
       - L3 触发 needs_user_decision
✅  联网验证：用户选 verify 时能拉到权威来源 + 写新 unit
✅  drift_report / undo-drift CLI 工作
✅  Router fail-safe：
       - 本地不可用 + 默认 abort 时返回明确错误
       - `--fallback public-only` 工作，输出标注 FALLBACK
       - 永不出现静默云端兜底
✅  3-A 固定问题清单（30 道）100% 可回答，人工审阅通过 ≥ 80%
✅  3-B 模板对话覆盖 ≥ 5 个 intent
✅  3-C 护栏指标可被监控，拒答率合理（10~30%）
✅  回归评估集与 snapshot 绑定，可基于简化 as_of 重复跑
✅  评估集 v3（50 道场景化）：
       - Recall@5 ≥ 85%
       - Faithfulness ≥ 90%
       - Citation 完整率 100%
```

---

# 七、模块骨架（仅方向）

---

## 7.1 Ingestion Profile 接口

```python
class IngestionProfile(Protocol):
    source_kind: str

    def detect(self, raw_path: Path) -> bool:
        """这个 profile 能处理这个文件吗"""

    def to_inbox(self, raw_path: Path) -> str:
        """写入 L0 inbox，返回 sha256"""

    def extract(self, raw_sha256: str) -> Iterable[Unit]:
        """L0 → L1 units"""

    def default_sensitivity(self, unit: Unit) -> str:
        """初始 sensitivity 推定"""
```

MVP 实现：`TechMarkdownProfile`。
阶段 2：`CodeRepoProfile`。
阶段 3：`ConversationProfile`（对话回流）。
阶段 4+：`ReadingNoteProfile`、`ArticleProfile`、`DiaryProfile` 等。

---

## 7.2 LLM Router

```python
class LLMRouter:
    def __init__(self, cloud_client, local_client):
        self.cloud_client = cloud_client
        self.local_client = local_client
        self._local_unavailable_until = None  # 失败缓存

    def health_check(self, force=False) -> bool:
        """快速 ping 本地模型。失败缓存 60s。"""
        if not force and self._local_unavailable_until and now() < self._local_unavailable_until:
            return False
        ok = self.local_client.ping(timeout=config.ping_timeout_ms / 1000)
        if not ok:
            self._local_unavailable_until = now() + 60
        return ok

    def route(
        self,
        scope: str,
        max_sensitivity: str,
        fallback: Literal['abort', 'public-only'] = 'abort',
    ) -> LLMClient:
        # 1. 决定理想路由（无故障情况）
        ideal = self._ideal_route(scope, max_sensitivity)
        
        # 2. 如果理想路由是 cloud，直接返回
        if ideal is self.cloud_client:
            return self.cloud_client
        
        # 3. 理想路由是 local：检查本地可用性
        if self.health_check():
            return self.local_client
        
        # 4. 本地不可用：fail-safe（落地 P12）
        if fallback == 'public-only':
            # 用户显式同意降级，调用方需重做 query 限定 scope=public
            raise FallbackRequired(mode='public-only',
                reason='Local model unavailable; user-requested fallback')
        
        # 默认 abort
        raise LocalUnavailable(
            f"Local model unavailable. Query requires sensitivity={max_sensitivity} "
            f"which cannot route to cloud (P12). "
            f"Use --fallback public-only to query public content only.")

    def _ideal_route(self, scope, max_sensitivity):
        if max_sensitivity in ('private', 'secret'):
            return self.local_client
        if max_sensitivity == 'internal' and scope == 'self':
            return self.local_client
        if max_sensitivity == 'internal' and scope in ('interview', 'handover'):
            return self.local_client if config.prefer_local_for_internal else self.cloud_client
        return self.cloud_client
```

**阶段 1 即上线**，即使本地模型暂时跑得差，也要先把架构走通（含 fail-safe）。

---

## 7.3 Retrieval API

```python
@dataclass
class SearchFilter:
    # 范围过滤（阶段 1 实现）
    topics:             list[str] | None = None
    kinds:              list[str] | None = None
    source_kinds:       list[str] | None = None
    sensitivity:        list[str] | None = None
    
    observed_since:     datetime | None = None
    observed_until:     datetime | None = None
    captured_since:     datetime | None = None
    captured_until:     datetime | None = None
    
    # 时间点过滤（阶段 1 预留、阶段 6 实现）
    as_of:              datetime | None = None
    """那个时刻'有效'的 units：
       valid_from <= as_of AND (valid_until IS NULL OR valid_until > as_of)
    """
    
    # 历史包含
    include_historical: bool = False
    
    # Canonical 去重（阶段 1 接口已开放、行为见说明）
    dedup_by_canonical: bool = True
    include_duplicates: bool = False
    """include_duplicates=True 等价于 dedup_by_canonical=False"""

class RetrievalAPI(Protocol):
    def search(self, query: str, filters: SearchFilter, k: int) -> list[ScoredUnit]:
        """阶段 1：as_of 传入抛 NotImplementedError"""
```

---

### 各阶段实现进度

| 字段 | 阶段 1 | 阶段 2 | 阶段 3 | 阶段 6 |
|------|-------|-------|-------|-------|
| `topics / kinds / source_kinds / sensitivity` | ✅ | ✅ | ✅ | ✅ |
| `observed_since / observed_until` | ✅ | ✅ | ✅ | ✅ |
| `captured_since / captured_until` | ✅ | ✅ | ✅ | ✅ |
| `as_of` | ⏸ NotImplementedError | ⏸ NotImplementedError | ✅ **简化版** | ✅ 完整 bitemporal |
| `include_historical` | ✅ | ✅ | ✅ | ✅ |
| `dedup_by_canonical` | ✅ 接口（每 unit 自成一组） | ✅ 完整（含选举） | ✅ 完整 | ✅ 完整 |
| `include_duplicates` | ✅ 接口 | ✅ 完整 | ✅ 完整 | ✅ 完整 |

**as_of 三档实现**：

| 阶段 | as_of 实现程度 | 能回答的问题 |
|------|---------------|------------|
| 阶段 1 | 抛 `NotImplementedError` | — |
| 阶段 3 | **简化版**：`valid_from <= as_of AND (valid_until IS NULL OR valid_until > as_of)` | "现在的我，认为某时刻有效的 units 是哪些" |
| 阶段 6 | **完整 bitemporal**：追踪 valid_until 自身的设置时间 | "某时刻的系统，当时认为有效的 units 是哪些" |

> 阶段 3 的简化版**已经足够**支撑回归评估"基于 snapshot 重放"的核心需求。阶段 6 升级的是"严格的过去状态回放"。

* 阶段 1：`FtsRetrievalAPI`
* 阶段 3：`HybridRetrievalAPI`（embedding + FTS5 加权，含简化 as_of）
* 阶段 6：完整 bitemporal `as_of`（追踪 valid_until 设置时间）
* 远期：可切到 Qdrant / pgvector / Milvus，接口不变

---

## 7.4 Drift Detector（阶段 3）

```python
@dataclass
class DriftSignal:
    unit_id: str
    claim_in_memory: str
    agent_knowledge: str
    classification: Literal['auto_fix', 'needs_review', 'needs_user_decision']
    confidence: float
    suggest_action: Literal['auto_apply', 'verify_online', 'user_decide']

class DriftDetector:
    def check(self, retrieved_units: list[Unit], llm_response: str) -> list[DriftSignal]:
        ...

    def auto_fix(self, signal: DriftSignal) -> Unit | None:
        """仅在所有护栏满足时才执行，否则返回 None 让上层走 confirm 流程"""
```

---

## 7.5 Canonical Elector（阶段 2）

```python
class CanonicalElector:
    def elect(self, same_as_group: list[Unit]) -> str:
        """返回 canonical unit id；按 6.5.2 优先级"""

    def rebuild_all(self) -> int:
        """全量重选举；返回更新的 unit 数"""
```

---

## 7.6 Schema Migrator（阶段 1）

```python
class Migration:
    from_version: str
    to_version: str
    breaking: bool
    
    def up(self, unit_dict: dict) -> dict: ...
    def down(self, unit_dict: dict) -> dict: ...

class MigrationRunner:
    def detect_path(self, current: str, target: str) -> list[Migration]: ...
    def dry_run(self, target_version: str) -> MigrationReport: ...
    def apply(self, target_version: str) -> MigrationReport: ...
    def rollback(self) -> MigrationReport: ...
```

---

## 7.7 Projection / Redactor

见 [6.4](#64-projection--redactor-引擎)。

---

## 7.8 Evaluation Runner

```yaml
# eval/capability/v1.yaml
- id: q_001
  scope: self
  question: "我对 Redis Lua scripting 持什么看法？"
  expected_topics: [redis, lua]
  expected_kinds: [opinion]
  expected_stance: positive
  # ⚠ 注意：能力评估集不绑定 expected_unit_ids
  notes: "..."
```

```yaml
# eval/regression/<snapshot_id>/questions.yaml
- id: r_001
  scope: self
  question: "..."
  expected_topics: [...]
  expected_unit_ids: [u_a3f2..., u_b7e8...]  # 与 snapshot 绑定
  expected_top_k: 5
  notes: "..."
```

```python
def run_eval(set_path, snapshot_id=None) -> Report:
    qs = load_questions(set_path)
    results = []
    for q in qs:
        r = recall(q.question, q.scope, k=5,
                   filters=SearchFilter(as_of=snapshot.as_of if snapshot_id else None))
        results.append({
            'q_id': q.id,
            'recall_at_5': hit_any(r.top5, q.expected_unit_ids) if q.expected_unit_ids else None,
            'topic_match': set(r.top1.topics) >= set(q.expected_topics),
            'faithfulness': faithfulness_score(r.answer, r.top5),
        })
    return Report(results)
```

---

# 八、评估机制

---

## 8.1 三档指标

| 指标 | 含义 | MVP 目标 |
|------|------|---------|
| Recall@K | retrieved 中是否含期望 unit | 阶段 1: ≥ 60% / 阶段 3: ≥ 85% |
| Faithfulness | 答案陈述是否能从 retrieved 中找到根据 | 阶段 1: ≥ 80% / 阶段 3: ≥ 90% |
| Coverage | 评估集对 kinds / topics / scopes 的覆盖度 | 报告项 |

阶段 3 额外指标：

| 指标 | 含义 | 目标 |
|------|------|------|
| Drift detection rate | 已知漂移问题被检出的比例 | ≥ 80% |
| False auto-fix rate | 自动修被人工 undo 的比例 | ≤ 5% |
| Citation 完整率 | 答案中每个事实都有 citation | 100% |

---

## 8.2 不做的指标

* ❌ Persona consistency（不追求像我）
* ❌ Style similarity
* ❌ BLEU / ROUGE 类生成指标

---

## 8.3 双层评估集（关键架构）

```text
┌─────────────────────────────────────────────────────────┐
│  Capability Evaluation（能力评估，与数据无关）          │
│    eval/capability/v1.yaml / v2.yaml / v3.yaml          │
│    - 每题不绑定 expected_unit_ids                       │
│    - 绑定 expected_topics / expected_kind / stance      │
│    - 评分：检索 top-K 是否覆盖 expected_topics +        │
│            答案 faithfulness                            │
│    - 用途：长期跟踪系统能力                            │
│    - 知识库增长不影响（但召回的具体 unit 会变）         │
├─────────────────────────────────────────────────────────┤
│  Regression Evaluation（回归评估，与 snapshot 绑定）    │
│    eval/regression/<snapshot_id>/                       │
│      ├── snapshot.json    # 该 snapshot 状态指纹        │
│      └── questions.yaml   # 该 snapshot 上的问题        │
│    - 每题绑定 expected_unit_ids                         │
│    - 升级 schema/prompt/model 前必跑                    │
│    - 升级后跑同一 snapshot + 同问题，对比 metrics       │
│    - 任一指标退步 → 阻断升级                            │
└─────────────────────────────────────────────────────────┘
```

---

### 8.3.1 为什么需要双层

| 问题 | 单一评估集的困境 | 双层方案的解 |
|------|----------------|-------------|
| 知识库增长后期望答案变了 | 评估集不可维护 | 能力集不绑 unit_id，对此鲁棒 |
| 模型/prompt 升级是否退步 | 无法对比，因为答案本身在变 | 回归集 + snapshot 锁定 |
| 评估"系统能力" vs "状态下能力" | 混淆 | 能力集测能力，回归集测某状态 |

---

### 8.3.2 工作流

```text
[场景 A: 日常运行]
  → 每次大规模 ingest 后：跑 capability/v1.yaml
  → 看 Recall@5 / Faithfulness 长期曲线

[场景 B: 升级 prompt / model / schema 前]
  → twin snapshot create --notes "before prompt v2"
  → 基于该 snapshot 构造 regression set
       （或选取已有的 regression set）
  → 保存 baseline metrics

[场景 C: 升级后]
  → 切换 prompt / model
  → 用同一 snapshot + 同一 regression set 跑
       阶段 3 起：基于简化 as_of（valid_from/valid_until 过滤）
       阶段 6：升级为完整 bitemporal 回放
  → 对比 metrics：任一退步则阻断
  → 通过则更新 baseline
```

---

#### 简化版 as_of 的局限性

阶段 3 的简化版能正确处理 **90% 实际场景**，但有一个已知盲区：

```text
场景：
  Day 1: 创建 snapshot A，此时 unit_x 的 valid_until = null
  Day 5: unit_x 被漂移修复，valid_until 设为 Day 3
  Day 10: 用 snapshot A 跑 regression

简化 as_of(Day 1) 查询：
  WHERE valid_from <= Day 1 AND (valid_until IS NULL OR valid_until > Day 1)
  → unit_x.valid_until = Day 3 > Day 1 ✅
  → unit_x 仍然返回（正确）

但如果场景变为：
  Day 5: unit_x.valid_until 被设为 Day 1（更早）
  
简化 as_of(Day 1) 查询：
  → unit_x.valid_until = Day 1 NOT > Day 1
  → unit_x 不返回 ❌
  → 但 snapshot A 创建时这个 unit 是 valid 的

这是简化版的盲区：valid_until 被回溯设置过去的时间点。
完整 bitemporal（阶段 6）追踪 valid_until 自身的设置时间，
可以正确处理。
```

**MVP 应对**：

* 漂移修复 / 重抽取设 valid_until = **当前时间**（不回溯）→ 避开盲区
* 用户校正设 valid_until = **当前时间**
* 文档约束：禁止把 valid_until 设为过去的时间点（除非显式知道含义）

---

### 8.3.3 阶段对应

| 阶段 | 评估集 | 回归集 |
|------|--------|--------|
| 阶段 1 | capability v1（30 道） | — |
| 阶段 2 | capability v2（+20 道） | — |
| 阶段 3 | capability v3（+50 道）+ drift 子集（10 道） | 首批 regression set（基于 snapshot） |
| 阶段 6 | 完整 as_of 支持，回归集可"真正回放" | 全量 |

---

## 8.4 评估集来源

* **v1（30 道）**：技术内容，"我对 X 的看法 / 我做过 Y 吗 / Z 的关键点"
* **v2（+20 道）**：项目维度，"FARL 里 Lua VM 怎么选型 / 升级到 2.0 遇到什么"
* **v3（+50 道）**：场景化，模拟面试官 / 交接同事的实际问题
* **v3 漂移子集（10 道）**：故意构造"已过时"的 unit，看是否能被检测
* **regression 集**：从 v1/v2/v3 中抽样 + 绑定 snapshot + 标 expected_unit_ids

评估集是**人工标注**，每道含 expected_topics 至少。

---

## 8.5 评估频率

* 每次 schema 改动后（必须跑能力集 + regression）
* 每次 ingest 大批量新内容后（跑能力集）
* 每个阶段 release 前（必须通过 Acceptance 指标）
* 升级 prompt / model 前后（必须跑 regression）

---

# 九、风险与权衡

---

| 风险 | 影响 | 缓解 |
|------|------|------|
| 抽取 LLM 输出质量不稳 | 阶段 1 整体卡住 | tolerant parser + 重试 + 失败 unit 单独存档 |
| sensitivity 默认 private 过严 | MVP 内容不可用 | CLI 批量 promote 工具 + scope 模板可临时放开 |
| curated.jsonl 与 SQLite 双写不一致 | 数据漂移 | jsonl 真相源 + 一键 rebuild |
| 数据规模上升后 SQLite + FTS5 不够 | 检索质量下降 | retrieval/api.py 已抽象，可切 Qdrant 等 |
| LLM Router 在敏感判定上失误 | 隐私泄露 | 默认 private，错也偏严；filter before retrieve；本地模型兜底 |
| 阶段 3 实时对话护栏不严 | 真出事 | 严格 3-A → 3-B → 3-C 推进，每步独立可交付 |
| MVP 几个月没真用上 | 失去动力 | 每阶段必有 CLI 产出，强制 dogfood |
| 抽取速度太慢 | 全量首跑数小时 | sha256 增量 + 并发抽取 |
| 评估集本身有偏 | 优化方向跑偏 | 评估集分批 review，每阶段补充 |
| 完全自动迭代不可能 | 知识过时 | 三级漂移分类 + 用户 confirm + 联网验证 |
| 自动修误判 | 静默改坏数据 | 默认 OFF + 多重护栏 + 全程审计 + undo |
| 漂移检测让对话变慢 | UX 退化 | 默认仅做轻量自检；联网验证按需触发 |
| Prompt / model 频繁升级 | 重抽爆炸 | reextract 默认手动；dry-run 看影响 |
| Schema additive 误判为 breaking（或反之） | migrator 不必要 / 数据损坏 | PR 模板含 schema-change 检查清单；3 档分级强制声明 |
| Migrator 不幂等 | 重跑数据损坏 | 强制 .bak + dry-run + rollback + 单测覆盖 |
| Canonical 选举漂移 | 同组 unit 选出的代表不稳定 | 优先级表确定性 + id 字典序兜底 + `canonical pin` 手动锁 |
| 对话回流污染 L1 | 答案错误被吸收成"事实" | 仅 approved 才回流；conversation profile 默认 internal；可批量 reject 回滚 |
| User correction 与漂移检测语义冲突 | `corrects` vs `supersedes` 混淆 | 关系语义在文档 + prompt 中严格区分；CLI 显式区分 |
| 评估集与 snapshot 解耦 | 回归无法对比 | 双层评估集 + snapshot.json 强制绑定 |
| as_of 查询语义被误用 | 用户期待 bitemporal | 阶段 3 简化版明确局限性 + 完整 bitemporal 阶段 6；文档约束"valid_until 不回溯过去时间" |
| Rebuild-db 性能爆炸 | 数据规模上来后阻塞日常 | 性能监控 + 60s 阈值告警；保留方案 A/B 升级路径（阶段 4+） |
| 简化 as_of 盲区（valid_until 回溯过去） | regression 结果失真 | 文档约束 + 实施时 valid_until 永远 = now |
| Canonical 选举返回过期 unit | 检索结果含失效内容 | 选举算法第 0 步 filter valid；valid_until 变化触发重选举 |
| L0 纯洁性稀释（派生物入 L0） | 数据语义混淆 | 决策 10 明确边界：transcript 是事件 ≠ answer 是派生物；ConversationProfile 抽取约束 |
| LLM 生成内容被当成"我的观点" | 污染 L1 | ConversationProfile 抽取时拒抽 LLM-generated opinion；用户亲表达单独标记 |
| 本地模型故障导致服务中断 | 用户体验差 | P12 默认 abort + 显式 `--fallback public-only`；健康检查缓存 60s |
| 用户误用 `--fallback public-only` 暴露隐私 | 私密内容被剔除导致答案误导 | 输出强制标注 FALLBACK；CLI 提示当前模式仅查 public |

---

# 十、后续阶段（仅方向，schema 已预留）

---

## 阶段 4 — 日记 / 阅读笔记 / 自己的文章

```text
🔒  Ingestion profiles:
      - diary               (sensitivity force_private_strict)
      - reading_note(tech/science/business/humanities)  → internal
      - reading_note(psychology/philosophy/lifestyle/miscellaneous)  → private
      - article(tech/tutorial) → public (if already_published)
      - article(essay/review)  → internal
🔒  阅读笔记区分原文摘录 vs 我的批注（is_original_thought 字段）
🔒  日记不参与任何 public / internal 投影
🔒  仅用于自用检索 + 成长追踪基础
```

---

## 阶段 5 — 写作助手

```text
🔒  基于 article + tech_markdown 已有内容
🔒  实现：few-shot exemplars，不微调
🔒  CLI: twin draft <topic> --style <reference_articles>
```

---

## 阶段 6 — 成长追踪 / 完整 as-of-time

```text
🔒  使用 relations: supersedes / contradicts / corrects
🔒  时间维度查询：twin recall <topic> --as-of 2024-01（完整实现）
🔒  CLI: twin evolution <topic>
🔒  漂移检测产生的 supersedes 链可视化
🔒  回归评估集"真正回放"（基于 as_of 查询）
```

---

## 阶段 7 — 反馈回路 / 漂移智能化

```text
🔒  对话日志结构化存档
🔒  漂移检测从规则向学习升级（基于历史 confirm/reject）
🔒  开放对话护栏自适应调整
🔒  完整 bitemporal 模型（valid_until 自身的设置时间）—— 可选
```

---

# 十一、附录

---

## 附录 A：项目目录约定（最终形态）

```text
digital-twin/
├── data/                       # 所有数据（git ignore 或 git-lfs）
│   ├── inbox/                  # L0
│   ├── curated/                # L1 真相源（按 raw 1:1）
│   ├── index/                  # SQLite / vectors
│   ├── projections/            # L3 缓存
│   ├── conversations/          # 对话 State Store
│   ├── drifts/                 # 漂移检测日志
│   ├── snapshots/              # 状态快照
│   ├── eval/                   # 评估集 + 报告
│   └── logs/
│
├── config/
│   ├── sensitivity_rules.yaml
│   ├── drift.yaml              # drift_check_enabled / auto_fix_enabled 等
│   ├── router.yaml             # scope → router 决策
│   ├── projections/
│   │   ├── interview.yaml
│   │   └── handover.yaml
│   └── redaction.yaml
│
├── src/
│   ├── ingest/
│   ├── store/
│   │   └── migrations/         # ⭐ schema migrator
│   ├── retrieval/
│   ├── llm/
│   ├── projection/
│   ├── drift/                  # 阶段 3
│   ├── conversation/           # 阶段 3：State Store + 回流
│   ├── aggregation/            # 阶段 2
│   ├── eval/
│   └── cli/
│
├── eval/
│   ├── capability/
│   │   └── v1.yaml
│   └── regression/
│       └── <snapshot_id>/
│
├── prompts/
│   ├── extract_tech_md.txt
│   ├── extract_code_repo.txt
│   ├── extract_conversation.txt
│   ├── recall_answer.txt
│   └── drift_check.txt
│
├── tests/
└── README.md
```

---

## 附录 B：阶段 3 固定问题清单模板（待填）

```yaml
# 面试场景
interview_questions:
  self_intro:
    - id: ii_001
      q: "请简单介绍一下你自己和你的技术栈"
      retrieval:
        topics: [self_intro, tech_stack]
        kinds: [fact, preference]
      scope: interview

  project_deep_dive:
    - id: ip_001
      q: "你在 X 项目里担任什么角色？最大的贡献是什么？"
      retrieval:
        topics: [<project>]
        kinds: [decision, experience]
      scope: interview
    - id: ip_002
      q: "X 项目里你做过哪个技术选型？是怎么权衡的？"
      retrieval:
        topics: [<project>]
        kinds: [decision]
        tags: [tech_choice]
      scope: interview
    ...

  problem_solving:
    - id: ips_001
      q: "讲一个你解决过的最棘手的技术问题"
      ...

# 交接场景
handover_questions:
  context:
    - id: hc_001
      q: "这个项目的核心目标是什么？"
      retrieval:
        topics: [<project>]
        kinds: [concept]
        tags: [project_goal]
      scope: handover

  decisions:
    - id: hd_001
      q: "为什么选 X 方案而不是 Y？"
      ...

  pitfalls:
    - id: hp_001
      q: "这个项目里有哪些已知的坑？"
      ...

  todos:
    - id: ht_001
      q: "还有哪些没做完的事？"
      ...
```

---

## 附录 C：CLI 命令清单（最终形态）

```bash
# ─────────── Ingestion ───────────
twin ingest <path>                       # 单个文件 / 目录 ingest
twin ingest --source tech_md <path>
twin ingest <path> --no-cache            # 禁用缓存
twin ingest <path> --force-refresh       # 强制重抽

# ─────────── Reextract（重抽取）──────
twin reextract --raw <sha256>
twin reextract --source tech_markdown
twin reextract --where "extracted_by != current_model"
twin reextract --where "extracted_prompt_hash != current_prompt_hash"
twin reextract --since 2024-01-01
twin reextract --dry-run                 # 只看哪些会被重抽

# ─────────── Schema migrate ──────
twin migrate --to 1.1
twin migrate --to 1.1 --dry-run
twin migrate --rollback
twin migrate --check                     # 校验 schema_version 一致性

# ─────────── Snapshot ────────────
twin snapshot create --notes "..."
twin snapshot list
twin snapshot show <snapshot_id>
twin snapshot diff <id1> <id2>

# ─────────── Inspection ──────────
twin inspect <unit_id>                   # 查看 unit 详情 + 原文回链
twin show raw <sha256>                   # 查看 L0 原文
twin ls --source tech_md                 # 列出 units
twin ls --kind opinion --since 2024-01-01

# ─────────── Retrieval ───────────
twin recall <query>                      # 默认 scope=self
twin recall <query> --scope interview
twin recall --topic redis --kind opinion
twin recall <query> --explain
twin recall <query> --include-historical
twin recall <query> --include-duplicates # 不去重，看 same_as 全部
twin recall <query> --verify             # 强制走漂移验证流程
twin recall <query> --as-of 2024-03-01   # 阶段 1 抛 NotImplementedError；阶段 3 起简化版工作
twin recall <query> --fallback public-only # 本地模型故障时显式降级


# ─────────── Aggregation（阶段 2）──
twin project <name>
twin project <name> --aspect decisions
twin project <name> --export handover-draft.md
twin canonical show <unit_id>
twin canonical rebuild --all
twin canonical pin <unit_id>

# ─────────── Conversation（阶段 3）─
twin chat --scope interview
twin chat --resume <session_id>
twin review <session_id>
twin review <session_id> q_001 --approve     # 触发回流 L0-L1
twin review <session_id> q_001 --need-edit
twin review <session_id> q_001 --reject
twin review <session_id> --close
twin correct <unit_id> --new-content "..." --reason "..."
                                             # 建立 corrects 关系
twin scripted run --set interview_q.yaml

# ─────────── Drift（阶段 3）───────
twin verify <unit_id>
twin drift-report
twin drift-report --pending
twin drift-report --auto-only
twin drift-report --since 2026-05-01
twin confirm-drift <drift_id>
twin reject-drift <drift_id>
twin undo-drift <drift_id>

# ─────────── Maintenance ─────────
twin promote <unit_id> --to public
twin promote --batch --from private --to internal --filter "topic:redis"
twin rebuild-db                          # 从 jsonl 重建 SQLite
twin rebuild-db --benchmark              # 基准测试，不实际操作
twin rebuild-db --verbose                # 显示各阶段耗时
twin rebuild-stats                       # 查看 rebuild 历史耗时曲线
twin router health                       # 检查 LLM client 健康状态
twin eval capability/v1                  # 跑能力评估集
twin eval regression/<snapshot_id>       # 跑回归评估集

# ─────────── Privacy / projection ──
twin project-view <unit_id> --scope interview     # 看在某 scope 下的投影
twin redact-preview <unit_id> --scope public      # 看脱敏后的样子
```

---

## 附录 D：配置文件清单

```yaml
# config/router.yaml
prefer_local_for_internal: true     # internal 是否优先本地
scope_allowed:
  self:      [public, internal, private, secret]
  interview: [public, internal]
  handover:  [public, internal]
  public:    [public]

local_model_health_check:
  enabled:           true
  ping_timeout_ms:   5000
  failure_cache_s:   60

fail_safe:
  default_behavior:                abort      # abort | public-only-fallback
  allow_public_only_fallback:      true       # 允许用户 --fallback public-only
  never_silent_cloud_fallback:     true       # P12 硬约束，不可关闭

rebuild_db:
  warn_threshold_ms:   10000     # 警告：rebuild 耗时 ≥ 10s
  alarm_threshold_ms:  60000     # 告警：rebuild 耗时 ≥ 60s，建议升级架构
```

```yaml
# config/drift.yaml
drift_check_enabled:        true
auto_fix_enabled:           false        # 默认 OFF
auto_fix_min_confidence:    0.95
auto_fix_max_edit_distance: 5
auto_fix_min_similarity:    0.95
confirm_required_for_l2:    true
confirm_required_for_l3:    true         # 不可关闭
web_verify_on_demand:       true
auto_web_verify_for_l2:     false
```

```yaml
# config/sensitivity_rules.yaml
# 见 [3.5 默认隐私规则]
```

```yaml
# config/projections/interview.yaml
scope: interview
allowed_sensitivity: [public, internal]
allowed_persons: []          # 显式白名单
allowed_companies: []
allowed_projects: []
redact_dates_below: month    # 仅保留到月份
```

---

## 附录 E：Schema 演进 PR 检查清单

任何对 schema 的改动（含 L1 schema、SQLite schema），PR 必须勾选：

```text
[ ] 我已声明本次改动属于哪个档位：
    [ ] L1 Additive（加字段含 default 非 null，或 nullable）
    [ ] L2 Renaming / Retyping（必须附带 migrator）
    [ ] L3 Semantic Change（必须附带 reextract 计划）

[ ] 若 L2：
    [ ] 已提交 migrator 到 src/store/migrations/
    [ ] migrator up() 已通过单测（含幂等性测试）
    [ ] migrator down() 已实现或显式声明不可逆
    [ ] schema_version 已更新

[ ] 若 L3：
    [ ] 已声明影响范围（哪些 source_kind / 哪些已有 units 需重抽）
    [ ] 已估算 LLM 调用成本
    [ ] 用户已被告知

[ ] 已更新本设计文档相应章节
[ ] 已更新评估集（若涉及）
```

---

# 十二、需求澄清决策记录

---

### 决策 1：content 重述边界

允许去口语化（去掉语气词，保留语义和结构），不允许结构化重组（列表化/分点等）；保留 `raw_offset` 指向原文；在抽取 prompt 中给 2-3 个正反例锚定边界。

---

### 决策 2：raw_offset 语义

统一为行号 `[起始行号, 结束行号]`，稳定且跨编码一致。SQLite 中字段名改为 `raw_offset_line_s` / `raw_offset_line_e`。

---

### 决策 3：same_as 建立机制

分层实现。阶段 1：`content_hash` 精确匹配自动建 `same_as` 关系（零成本）；阶段 2+：语义匹配批处理可选（`twin dedup` 命令）。

---

### 决策 4：缓存 L2 粒度

文件级粒度，任一 unit 的 `extracted_prompt_hash` 不匹配即触发整个文件重抽。旧 unit 不删除，设 `valid_until` + `supersedes` 关系（符合 4.5.2 重抽取策略）。

---

### 决策 5：本地模型依赖与 dogfood 矛盾

新增 `--dev` 模式（允许 private 内容路由到云端，输出强制标注 `⚠ DEV MODE: private content sent to cloud`，仅用于开发/评估，生产环境禁用）；`tech_markdown` 默认 sensitivity 改为 `internal`（降低无本地模型时的门槛）。需更新 P3 表述为"未显式标记的，按 source_kind 默认规则推定，无命中规则则 private"。需更新 3.5 默认隐私规则中 `tech_markdown` 的默认 sensitivity 为 `internal`。

---

### 决策 6：twin ingest 输入粒度

支持单文件、目录递归、glob 模式。增加开发便利参数：`--limit N` 限制处理文件数、`--slice N:M` 仅处理第 N 到 M 个 chunk。

---

### 决策 7：frequency_signal 更新机制

`same_as` 关系建立时累加。canonical 的 `frequency_signal` = 组内所有 unit 的 `frequency_signal` 之和。

---

### 决策 8：评估集 v1 来源

基于实际 ingested 内容构造。先导入用户的技术笔记，再根据笔记中实际存在的内容出题。

---

### 决策 9：twin recall 检索/生成解耦

支持 `--retrieve-only` 参数，只返回检索结果不调用 LLM 生成答案。评估和调试必备。

---

### 决策 10：extracted_prompt_hash 计算

仅对 prompt 模板文件内容做 sha256。检测"抽取指令变了没"，不包含填入的 chunk 内容。

---

### 决策 11：visibility_overrides 冲突处理

写入时校验 + 拒绝（与 `force_private_strict` / `force_secret` 冲突时直接报错）。force 规则可配置但需解锁：config 中新增 `allow_override_force_rules: false`（默认关闭），用户显式改为 `true` 才能修改 force 规则。

---

### 决策 12：entities type 枚举

开放词汇，LLM 自由标注。膨胀风险可控（per-unit 1-3 个 entity，type 天然有限）。阶段 2+ 可统计高频 type 逐步收敛为建议词表。

---

### 决策 13：twin chat 交互形态

A+B 混合。默认 REPL 交互式对话（`/exit` 退出），也支持单次问答模式 `twin chat "问题" --scope interview`。

---

### 决策 14：工程化约束

Python 3.12+ / uv 管理依赖 / pyproject.toml / mypy 或 pyright 类型检查 / ruff 格式化。用 conda 创建虚拟环境。

---

### 决策 15：对话 session 状态机

线性流转 `active → closed → approved/rejected`。先结束对话（不再新增问答），再逐条审阅，最后整体批准或拒绝。

---

### 决策 16：provenance 枚举

用 monolith 抓取的 HTML 标 `clipped_from_url`（语义为"从 URL 获取的内容"），URL 写入 `meta.json`。

---

### 决策 17：审阅界面 + API 架构

MVP 用纯 CLI 命令（`twin review <session_id> q_001 --approve`）；核心业务层为纯 Python 函数，CLI 和 HTTP API 双入口调用同一层；阶段 1 先实现 CLI，代码组织预留 API 层接入点。

---

### 决策 18：配置文件加载

固定路径 `config/*.yaml` + 环境变量 override（`TWIN_` 前缀，如 `TWIN_ROUTER__PREFER_LOCAL=false`）。环境变量优先级最高。

---

### 决策 19：错误处理策略

结构化错误码体系（如 `INGEST_001` = JSON 解析失败）+ 分级日志（DEBUG/INFO/WARN/ERROR）+ CLI 输出用户友好消息 + 日志文件记录完整堆栈。

---

### 决策 20：raw_jsonl_path 存储

jsonl 中也存储 `raw_jsonl_path` 字段，冗余存储用空间换时间，查询时无需动态计算。

---

# 文档版本

| 版本 | 日期 | 备注 |
|------|------|------|
| v1.0 | 2026-05-15 | 初版 |
| v1.1 | 2026-05-15 | 整合 6 个架构决策：Schema 三档分级 / Router 检索时序 / as_of 接口预留 / canonical_unit_id 与 same_as 消费 / 对话状态分层（State Store + 回流）/ 双层评估集 + Snapshot |
| v1.2 | 2026-05-15 | 整合 5 个深度问题：SQLite 为 jsonl 纯派生物（P11，含性能监控）/ as_of 三档实现（阶段 3 简化版）/ canonical 选举强制 valid 候选集 / L0 收纳 transcript 而非 answer（决策 10）/ Router fail-safe（P12，永不静默云端） |
| v1.3 | 2026-05-18 | 需求澄清：20 条决策落地 |
| v1.4 | 2026-05-18 | 阶段 1A 实现完成：MockLLMClient + 完整 pipeline 跑通（ingest → recall → rebuild-db → inspect → snapshot），Redis.md 57 units 端到端验证通过 |
| v1.5 | 2026-05-18 | 阶段 1B 实现完成：DeepSeek 接入 + 抽取 prompt + FTS5+LIKE 混合检索 + reextract/migrate/rebuild-stats/eval CLI + 评估集 v1（30 道，Recall@10 = 70%） |
| v1.6 | 2026-05-18 | 阶段 2 实现完成：CodeRepoProfile + Canonical 选举器 + same_as 去重 + twin project/canonical CLI + 评估集 v2（50 道，Recall@10 = 70%） |

---

# ✅ 最终总结

> 本系统的核心不是"自动生成漂亮文档"，而是：

```text
把分散的个人语料组织为
分层（L0~L3）、
不可篡改（content-addressed）、
可投影（scope-aware）、
可演化（relations + temporal）、
可验证（drift detection + web verify）、
可回滚（migrator + drift undo）
的记忆系统，
作为数字分身的内容基座
```

> 三阶段开发必须严格遵循：

```text
阶段 1：MVP 闭环（md → recall + 缓存 + migrator + snapshot）
阶段 2：项目维度扩展（code_repo → project + canonical 选举）
阶段 3：对外能力 + 时效性 + 对话回流
        （scripted → templated → open）
        （drift detection 三级 + 联网验证）
        （State Store + approved 回流 L0-L1）

每一步都必须有可 dogfood 的 CLI 产出。
```

> 核心不变量（任何场景都不破）：

```text
🔒 原始语料永不销毁、永不重写
🔒 所有"修改"实质都是"加新 unit + 标记旧的"
🔒 用户不 confirm 不会改变记忆（auto_fix 默认 OFF）
🔒 派生物（文档/答案/投影）随时可幂等重建
🔒 隐私默认从严（白名单制）
🔒 本地数据主权，云端只跑 inference
🔒 Schema 变更必须显式分档（additive / migrator / reextract）
🔒 对话 draft 永不进 L1；只有 approved transcript（事件记录）才回流
🔒 transcript 进 L0 是事件，不是 answer 派生物
🔒 ConversationProfile 拒抽 LLM-generated opinion / preference
🔒 corrects 与 supersedes 语义严格区分；corrects 触发 canonical 重选举
🔒 secret 永不参与对外检索路径
🔒 SQLite 是 jsonl 的纯派生物（P11），无独立 schema migration
🔒 canonical 仅从 valid_until IS NULL 的 unit 中选举
🔒 valid_until 状态变化触发 canonical 重选举
🔒 valid_until 永不回溯设置过去时间（避开简化 as_of 盲区）
🔒 本地模型故障默认 abort，永不静默云端兜底（P12）
🔒 用户显式降级只能"剔除敏感、仅查 public"，不可"用云端跑敏感"
```
