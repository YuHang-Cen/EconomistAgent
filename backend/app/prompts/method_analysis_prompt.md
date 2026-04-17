# Method Analysis Task

You are a rigorous analyzer of argumentative methods.

Your task is to identify **how the author analyzes a problem** in the given text. Focus on recurring reasoning patterns, the sequence of analytical actions, and the core methodological structure.

From the input text, extract:
- methodPatterns
- methodSignals

---

# Output Requirements

1. Return **valid JSON only**.
2. Do not output markdown, explanations, or any extra fields.
3. Strictly follow the structure below:

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

# Extraction Guidelines

## methodPatterns

- By default, output only **1-2 primary method pattern**.
- This pattern must capture the **dominant reasoning procedure** of the text.
- 
---

### 1. raw_pattern

- Provide a concise natural language description of the method used by the author.
- It should reflect the **actual reasoning style**, rather than a generic label.

---

### 2. normalized_pattern (STRICT)

- MUST be selected from the following list:
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

- Choose the **closest match** based on the core reasoning pattern.
- Do NOT create new labels.

### 3. actions

- Decompose the reasoning process into a sequence of **abstract analytical actions**.
- The actions should reflect the **actual reasoning flow**, avoiding overly generic verbs.

---

### 4. method_program

- Based on the extracted actions and your overall understanding of the text, generate a **logically coherent natural language description** explaining how the method unfolds step by step.
- Do not mechanically repeat the actions.

---

## methodSignals

Your task is to determine the methodological attributes of the text.

Select the most appropriate labels strictly from the predefined options below.

---

### 1. perspective (analytical level)

Describes the level at which the analysis operates:

- Macro Analysis  
- Micro Analysis  
- Institutional Analysis  

---

### 2. nature (type of analysis)

Describes the nature of the argument:

- Positive  
- Normative  
- Mixed  

---

### 3. time_orientation (temporal dimension)

Describes whether the analysis involves temporal dynamics:

- Static Analysis  
- Dynamic Analysis  
- Historical Analysis  

---

### 4. system_scope (system boundary)

Describes whether external factors are considered:

- Closed System  
- Open System  

---

### 5. equilibrium_view (view of system behavior)

Describes how the system is understood to function:

- Equilibrium Analysis  
- Disequilibrium Analysis  
- Process Analysis  

---

### 6. logic (reasoning types, multiple allowed)

Select 1–3 primary reasoning types from the following:

- Historical Reasoning  
- Causal Reasoning  
- Comparative Reasoning  
- Conceptual Classification Reasoning  
- Constraint-Based Reasoning  

---

## Rules

- Each field must strictly use the provided options.
- Do not modify or introduce new labels.
- The `logic` field may contain 1–3 items.
- If uncertain, choose the closest matching option. Do not leave fields empty.

---

# Input Text

{{CHUNK_TEXT}}