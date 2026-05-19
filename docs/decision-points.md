# 按分歧点决策 - 功能规划

## 1. 背景与问题

当前 Decisions 标签在需要人类决策时，只提供"采纳/驳回"的粗暴二选一。
用户无法针对具体分歧点（如数据库选型、缓存策略、部署方式）做逐项决策，
也无法输入自定义方案。

**目标**：将决策粒度从"整体方案"细化到"具体分歧点"，让人类针对每个分歧点
独立选择方案，支持关联约束和自定义输入。

## 2. 核心设计

### 2.1 决策点数据模型

```python
class DecisionPoint(BaseModel):
    """一个具体的决策分歧点"""
    decision_id: str           # 唯一标识
    session_id: str
    topic: str                 # 决策主题，如"数据库选型"
    description: str           # 背景描述，如"系统需要选择持久化存储方案"
    options: list[DecisionOption]  # 各方提出的选项
    constraints: list[str]     # 关联约束，如["选择了向量数据库则不能选SQLite"]
    human_choice: str = ""     # 人类最终选择
    human_custom: str = ""     # 人类自定义输入

class DecisionOption(BaseModel):
    """决策点的一个选项"""
    option_id: str
    label: str                 # 选项名称，如"PostgreSQL"
    proposed_by: str           # 提出该选项的Agent ID
    reasoning: str             # 理由，如"需要向量存储支持"
    pros: list[str] = []       # 优点
    cons: list[str] = []       # 缺点
    related_decisions: list[str] = []  # 关联的决策点ID及兼容性
```

### 2.2 分歧点提取时机：Critic 阶段

**选择 Critic 阶段的原因：**
1. Agent 已在阅读对方提案并找问题，提取分歧点是自然延伸
2. 不增加流程长度（不需要新阶段）
3. 在 Revision 之前提取，Agent 修订时可参考分歧点
4. Agent 已在分析差异，额外提交结构化分歧点成本低

**具体做法：**
- Critic 阶段的 Agent 提交内容扩展：除了 challenges，还必须提交 `decision_points`
- 每个 Agent 从所有提案中识别关键决策分歧点，结构化提交
- 系统汇总所有 Agent 提交的决策点，去重合并

### 2.3 汇总机制

多个 Agent 可能识别出相同或相似的决策点，需要汇总去重：

**方案：投票式汇总**
1. 每个 Agent 提交自己识别的决策点列表
2. 系统按 `topic` 语义相似度聚类（简单方案：关键词匹配；进阶方案：embedding相似度）
3. 同一聚类内的决策点合并：
   - `topic` 取出现最多的表述
   - `options` 合并去重（相同label的选项合并reasoning）
   - `constraints` 合并去重
4. 生成最终的决策点清单

**简化方案（推荐先实现）：**
- Agent 提交的决策点包含 `topic`（主题关键词，如"database"、"cache"）
- 系统按 `topic` 精确匹配分组
- 同组内合并选项，不同Agent提出的同名选项合并reasoning
- 未被任何Agent识别的决策点不出现（信任Agent的专业判断）

### 2.4 关联约束

某些决策点之间存在依赖关系，例如：
- 选择"向量数据库"→ 不能选"SQLite"
- 选择"微服务架构"→ 必须选"容器化部署"

**实现方式：**
- Agent 在提交决策点时，可以声明 `constraints`
- 约束格式：`{"if": "decision_id_A=option_X", "then": "decision_id_B!=option_Y"}`
- 前端在选择时实时校验约束，冲突时高亮提示

### 2.5 前端决策界面

```
┌─────────────────────────────────────────────┐
│ 📋 决策点 1/5：数据库选型                      │
│ 系统需要选择持久化存储方案                       │
│                                              │
│ ○ PostgreSQL                                 │
│   提出者：Agent A (integration_ecosystem)     │
│   理由：后续需要向量存储，pgvector原生支持       │
│   ✅ 开源免费  ✅ 向量搜索  ❌ 资源占用较高      │
│                                              │
│ ○ MySQL                                      │
│   提出者：Agent B (developer_experience)      │
│   理由：生态成熟，团队熟悉                       │
│   ✅ 生态丰富  ✅ 性能稳定  ❌ 不支持向量搜索     │
│                                              │
│ ○ SQLite                                     │
│   提出者：Agent C (cost_optimization)         │
│   理由：前期数据量小，无需独立部署               │
│   ✅ 零部署  ✅ 轻量  ❌ 不支持并发写入           │
│                                              │
│ ○ 自定义方案                                  │
│   ┌─────────────────────────────────────┐    │
│   │ 输入您的方案...                       │    │
│   └─────────────────────────────────────┘    │
│                                              │
│ ⚠️ 关联约束：选择SQLite将与"部署方式"冲突       │
└─────────────────────────────────────────────┘
```

## 3. 实现计划

### Phase 1：数据模型与后端（约150行）
- [ ] 新增 `DecisionPoint`、`DecisionOption` 模型（models.py）
- [ ] Session 模型添加 `decision_points` 字段
- [ ] Critic 阶段提交逻辑扩展，支持 `decision_points`（engine.py）
- [ ] 汇总去重逻辑：`_merge_decision_points()`（engine.py）
- [ ] API 序列化：`_serialize_session()` 添加 `decision_points`（web.py）
- [ ] 人类决策 API：`/resolve-decision-point`（web.py）

### Phase 2：Critic 阶段提示词更新（约50行）
- [ ] 更新 Critic 阶段的 phase description，要求 Agent 提交 `decision_points`
- [ ] 更新 `get_phase_context` 返回的提示信息
- [ ] 更新 SKILL.md 协议文档

### Phase 3：前端决策界面（约200行）
- [ ] Decisions 标签：逐点展示决策卡片
- [ ] 每个决策点：选项列表 + 自定义输入框
- [ ] 关联约束实时校验与提示
- [ ] 决策进度指示器（已决策/总决策点数）
- [ ] 一键采纳多数方案（自动选择每个点得票最多的选项）

### Phase 4：测试与验证
- [ ] 单元测试：DecisionPoint 模型、汇总去重逻辑
- [ ] 集成测试：Critic→DecisionPoints→HumanDecision 完整流程
- [ ] UI 测试：Playwright 验证决策界面交互

## 4. 关键技术决策

| 决策项 | 方案 | 备注 |
|--------|------|------|
| 分歧提取方式 | Agent结构化提交 | Critic阶段扩展，不需要额外LLM调用 |
| 汇总方式 | topic关键词匹配分组 | 简单可靠，后续可升级为embedding |
| 关联约束 | Agent声明+前端校验 | 先实现基本约束，复杂约束后续迭代 |
| 自定义输入 | 每个分歧点都有输入框 | 用户可填写Agent未提到的方案 |
| 决策粒度 | 逐点独立决策 | 支持关联约束提示 |

## 5. 风险与注意事项

1. **Agent合规性**：Agent可能不按格式提交decision_points，需要容错处理
2. **汇总质量**：关键词匹配可能漏掉语义相似但用词不同的决策点
3. **约束复杂度**：关联约束可能过于复杂，建议先支持简单互斥/依赖关系
4. **向后兼容**：旧session没有decision_points数据，前端需要兼容处理
