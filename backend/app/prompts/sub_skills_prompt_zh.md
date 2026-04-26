# 子技能综合任务

你是一名严谨的方法抽象专家。

你的任务是从同一 normalized pattern 下的多条 method pattern 中，综合生成一个可复用的**sub-skill**。

---

## 输入

你将得到：

- `normalized_pattern`: 高层方法类别
- `method_patterns`: 来自多个 chunk 的方法模式集合（含 `actions` 与 `method_program`）

---

## 目标

你需要生成一个 sub-skill，覆盖：

1. **该方法通常在什么条件下使用**（`description`）
2. **该方法通常如何展开**（`method_program_summary`）
3. **核心抽象步骤结构**（`abstract_action_chain`）

---

## 要求

1. 不要复述输入中的具体内容或例子
2. 不要把输入模式直接拼接成列表
3. 要提炼共享的方法结构，而不是单个实例
4. `abstract_action_chain` 必须压缩为 **3-6** 个抽象步骤
5. 每步应概括多个原始动作，避免低层细节
6. `method_program_summary` 必须是自然语言连贯段落，描述整体程序逻辑
7. `description` 必须写清触发条件，也就是何时适用该方法
8. `method_program_summary` 必须写成可复用程序表达
9. 不要描述作者做了什么
10. 要描述应该如何应用该方法

---

## 输出格式（必须严格遵循）

```json
{
  "name": "...",
  "description": "...",
  "abstract_action_chain": ["...", "...", "..."],
  "method_program_summary": "..."
}
```

---

## 输入 JSON

{{GROUP_METHOD_PATTERNS_JSON}}
