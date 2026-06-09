# Agent 工作流设计 (Agent Workflow)

## 1. 总览

本项目使用 **LangGraph** 的 `StateGraph` 实现多 Agent 协作。
整个系统的工作流是一个 **有向无环图（DAG），不同节点代表一个独立的 Agent。

## 2. 全局状态 (State)

```python
class ResumeAnalysisState(TypedDict):
    # 输入
    raw_text: str                    # 原始简历文本
    jd: str | None                   # 岗位描述（可选）

    # 解析产出
    parsed_resume: dict | None       # 结构化简历
    parse_confidence: float          # 解析置信度

    # 分析产出
    skills: list[str]
    highlights: list[str]
    weaknesses: list[str]
    education_score: int             # 0-100
    experience_score: int            # 0-100

    # 匹配产出
    match_score: float | None
    match_breakdown: dict | None
    match_reasons: list[str]

    # 优化产出
    optimize_suggestions: list[dict]

    # 元信息
    current_node: str
    trace: list[dict]                # 调用链
    error: str | None
```

## 3. 节点 (Nodes)

### Node 1: parser_agent

- **职责**: 把 `raw_text` 提取为结构化 `parsed_resume`
- **Prompt 策略**:
  - System: "你是一名高级 HR 助理，擅长从简历中抽取信息。"
  - Human: "请从以下简历中抽取关键信息，严格按 JSON Schema 输出..."
- **输出**: 姓名、邮箱、电话、学历、工作年限、技能、工作经历、项目经历

### Node 2: analyzer_agent

- **职责**: 对结构化简历做打分 + 亮点/不足分析
- **输入**: `parsed_resume`
- **输出**: `highlights`, `weaknesses`, `education_score`, `experience_score`

### Node 3: matcher_agent

- **职责**: 将简历与 JD 对比打分
- **输入**: `parsed_resume` + `jd`
- **输出**: `match_score` + 各维度评分 + 理由

### Node 4: optimizer_agent

- **职责**: 针对简历给出优化建议
- **输入**: `parsed_resume` + 可选 `jd`
- **输出**: 结构化建议列表（类别 + 原始内容 + 改进后内容）

## 4. 条件路由 (Conditional Edge)

```
parser ──► analyzer
               │
         ┌─────┴─────┐
         │ 有 jd ?   │
         └──┬─────┬──┘
            是     否
            │     │
            ▼     ▼
         matcher  optimizer
            │     │
            └──┬──┘
               ▼
              END
```

## 5. Prompt 模板管理

所有 Prompt 放在 `backend/app/agents/prompts/` 目录下，以 `.txt` 或 `.jinja` 文件形式管理，方便版本迭代与调试。

文件列表：
- `parser.txt` - 解析 Agent System + Human
- `analyzer.txt` - 分析 Agent
- `matcher.txt` - 匹配 Agent
- `optimizer.txt` - 优化 Agent

## 6. 可观测性

- 每个节点的输入/输出都会记录到 `state["trace"]`
- 关键步骤使用 `structlog` 记录
- 结构化日志中携带 `request_id` + `resume_id`
