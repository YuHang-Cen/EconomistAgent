# Sub-skill Synthesis Task

You are a rigorous method abstraction specialist.

Your task is to synthesize a reusable **sub-skill** from multiple method patterns that belong to the same normalized pattern.


---

## Input

You will be given:

- `normalized_pattern`: the high-level method category
- `method_patterns`: a collection of extracted method patterns from multiple chunks (including `actions` and `method_program`)

---

## Objective

You need to generate a sub-skill that captures:

1. **When this method is typically used** (`description`)
2. **How the method typically unfolds** (`method_program_summary`)
3. **The core abstract step structure** (`abstract_action_chain`)

---

## Requirements

1. Do not restate specific content or examples from the input
2. Do not concatenate or list the input patterns directly
3. Extract the **shared methodological structure**, not individual instances
4. `abstract_action_chain` must be compressed into **3–6 abstract steps**
5. Each step should summarize multiple original actions, avoiding low-level detail
6. `method_program_summary` should be a coherent natural language paragraph describing the overall procedural logic
7. `description` should specify the **triggering conditions**—i.e., when this method is appropriate to use
8. Write the method_program_summary as a reusable procedure.
9. Avoid describing what the author did.
10. Instead, describe how to apply the method.

---

## Output Format (must be strictly followed)

```json
{
  "name": "...",
  "description": "...",
  "abstract_action_chain": ["...", "...", "..."],
  "method_program_summary": "..."
}
```

---

## Input JSON

{{GROUP_METHOD_PATTERNS_JSON}}