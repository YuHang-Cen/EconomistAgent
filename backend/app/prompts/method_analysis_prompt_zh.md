# 方法分析任务

你是一名严谨的论证方法分析员。

你的任务是识别给定文本中作者**如何分析问题**。请重点关注重复出现的推理模式、分析动作顺序与核心方法结构。

请从输入文本中提取：
- methodPatterns
- methodSignals

---

# 输出要求

1. 只返回**合法 JSON**。
2. 不要输出 markdown、解释文本或额外字段。
3. 严格遵循以下结构：

```json
{
  "methodPatterns": {
      "raw_pattern": "...",
      "normalized_pattern": "...",
      "actions": ["...", "...", "..."],
      "method_program": "..."
    }
  ,
  "methodSignals": {
    "perspective": "...",
    "nature": "...",
    "time_orientation": "...",
    "system_scope": "...",
    "equilibrium_view": "...",
    "logic": ["..."]
  }
}
```

---

# 提取指引

## methodPatterns

- 默认仅输出 **1-2 个主要方法模式**。
- 该模式必须反映文本的**主导推理程序**。

---

### 1. raw_pattern

- 用简洁自然语言概括作者的方法。
- 应体现**真实推理风格**，而不是通用标签。

---

### 2. normalized_pattern (STRICT)

- 必须从以下列表中选择：
  - Concept Clarification
  - Concept Redefinition
  - Concept Decomposition
  - Concept Comparison
  - Causal Derivation
  - Causal Chain Analysis
  - Comparative Analysis
  - Institutional Constraint Analysis
  - Historical Tracing
  - Historical Evolution Analysis
  - Historical Deviation Analysis
  - Structural Analysis
  - Mechanism Analysis
  - Constraint Reasoning
  - Counterexample Argument

- 按核心推理模式选择**最接近**的标签。
- 不得自造新标签。

### 3. actions

- 将推理过程拆解为一组**抽象分析动作**序列。
- 这些动作必须体现真实推理流，不要使用空泛动词。

---

### 4. method_program

- 基于提取的 actions 与文本整体理解，生成一段**逻辑连贯的自然语言描述**，说明该方法如何逐步展开。
- 不要机械重复 actions。

---

## methodSignals

你的任务是判断文本的方法论属性。

每个字段必须严格从预设选项中选择。

---

### 1. perspective (analytical level)

描述分析所在层级：

- Macro Analysis
- Micro Analysis
- Institutional Analysis

---

### 2. nature (type of analysis)

描述论证性质：

- Positive
- Normative
- Mixed

---

### 3. time_orientation (temporal dimension)

描述分析是否涉及时间动态：

- Static Analysis
- Dynamic Analysis
- Historical Analysis

---

### 4. system_scope (system boundary)

描述是否考虑系统外因素：

- Closed System
- Open System

---

### 5. equilibrium_view (view of system behavior)

描述系统运行观：

- Equilibrium Analysis
- Disequilibrium Analysis
- Process Analysis

---

### 6. logic (reasoning types, multiple allowed)

从下列选项选择 1-3 个主要推理类型：

- Historical Reasoning
- Causal Reasoning
- Comparative Reasoning
- Conceptual Classification Reasoning
- Constraint-Based Reasoning

---

## 规则

- 每个字段必须严格使用给定选项。
- 不得修改或新增标签。
- `logic` 可包含 1-3 项。
- 如果不确定，选择最接近项，不得留空。

---

# 输入文本

{{CHUNK_TEXT}}
