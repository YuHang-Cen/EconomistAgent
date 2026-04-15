# 后端重建方案（V3，作者维度）：PipelineJob + 轮询

## 1. Summary
- 目标：将后端流程从“单 PDF / 项目中心”升级为“作者中心（Author-Centric）”：
1. 前端按作者管理书籍与文档；
2. 同一作者多 PDF 融合生成 author-level `main_skill/sub_skill`；
3. 问答必须显式选择作者，答案仅基于该作者知识域；
4. 支持文档级 `reload`，仅重处理单文档，不自动触发作者全量技能重建；
5. 支持章节/段落持久化与软删除，且软删除数据不参与后续流程。
- V3 仍保持 V1 简化原则：仅 `PipelineJob + 轮询`，不引入 `JobEvent/SSE`。

---

## 2. 推荐目录结构
```text
backend/
  app/
    main.py
    api/
      deps.py
      routes/
        authors.py              # 作者、文档、文档级 reload 相关接口
        segments.py             # chapter/segment 读取与删除接口
        jobs.py                 # 任务轮询、产物读取、重试、取消
    domain/
      enums.py                 # JobStatus / Stage / JobType / OutputType
      models.py                # PipelineJob + Author + Document + Snapshot + Chapter + Segment
    services/
      author_service.py        # 作者与文档管理
      segment_service.py       # 章节/段落查询、软删除
      job_service.py           # 创建/查询/重试/取消任务
      pipeline_service.py      # author_skills / document_reload / author_answer 流水线
      stage_runners.py         # 调用现有脚本执行各阶段
      extract_paragraphs.py    # 将 pdf 切分成 paragraphs_json
      analyze_method_chunks.py # 从 paragraphs_json 分析 method_analysis_json
      main_skill.py            # 生成 main_skill_json
      sub_skill.py             # 生成 sub_skill_json
      render.py                # 内部渲染 md 产物（对外可读但前端默认读 json）
      select_skills.py         # 从技能池中选择回答所需 main/sub skill（当前为设计占位）
      answer_with_skills.py    # 调用 llm 生成 answer_json
    infra/
      db.py
      queue.py
      storage.py
      settings.py
    prompts/
      method_analysis_prompt.md
      main_skills_prompt.md
      sub_skills_prompt.md
      select_skills_prompt.md
      answer_with_skills_prompt.md
  scripts/
    migrate.py
```

---

## 3. 领域模型（作者 + 文档 + 任务）

### 3.1 PipelineJob（核心）
1. `job_id`（UUID）
2. `author_id`（必填）
3. `document_id`（`document_reload` 必填，其余可空）
4. `job_type`：`author_skills` / `document_reload` / `author_answer`
5. `status`：`queued/running/success/failed/canceled`
6. `current_stage`：`extract/segment_sync/analyze/main_skill/sub_skill/render/select_skills/answer`
7. `progress`：0-100
8. `query`（`author_answer` 必填，其他可空）
9. `snapshot_id`（可选，技能任务成功后绑定）
10. `outputs_json`（`artifact_type -> uri`）
11. `error_message`（失败时）
12. `created_at`
13. `updated_at`
14. `finished_at`

### 3.2 业务实体
1. `authors`
- `author_id`
- `author_name`
- `school`
- `avatar_url`
- `created_at`
- `updated_at`

2. `author_documents`
- `document_id`
- `author_id`
- `book_title`
- `pdf_uri`
- `status`（`active/inactive/processing/failed`）
- `created_at`
- `updated_at`

3. `document_chapters`
- `chapter_id`
- `document_id`
- `chapter_title`
- `order_index`
- `is_deleted`
- `deleted_at`
- `created_at`
- `updated_at`

4. `document_segments`
- `segment_id`
- `document_id`
- `chapter_id`
- `chunk_id`
- `content`
- `order_index`
- `is_deleted`
- `deleted_at`
- `created_at`
- `updated_at`

5. `author_skill_snapshots`
- `snapshot_id`
- `author_id`
- `is_latest`
- `outputs_json`（作者级 json+md 产物 URI）
- `created_at`

### 3.3 状态机规则
1. 初始 `queued`
2. worker 拉起后 `running`
3. 所有阶段成功后 `success`
4. 任一阶段异常则 `failed`
5. 用户取消则 `canceled`

---

## 4. 数据库设计（sqlite，V3）

### 4.1 `pipeline_jobs`
1. `job_id TEXT PRIMARY KEY`
2. `author_id TEXT NOT NULL`
3. `document_id TEXT`
4. `job_type TEXT NOT NULL`
5. `status TEXT NOT NULL`
6. `current_stage TEXT`
7. `progress INTEGER NOT NULL DEFAULT 0`
8. `query TEXT`
9. `snapshot_id TEXT`
10. `outputs_json TEXT NOT NULL DEFAULT '{}'`
11. `error_message TEXT`
12. `created_at TEXT NOT NULL`
13. `updated_at TEXT NOT NULL`
14. `finished_at TEXT`

### 4.2 `authors`
1. `author_id TEXT PRIMARY KEY`
2. `author_name TEXT NOT NULL`
3. `school TEXT`
4. `avatar_url TEXT`
5. `created_at TEXT NOT NULL`
6. `updated_at TEXT NOT NULL`

### 4.3 `author_documents`
1. `document_id TEXT PRIMARY KEY`
2. `author_id TEXT NOT NULL`
3. `book_title TEXT NOT NULL`
4. `pdf_uri TEXT NOT NULL`
5. `status TEXT NOT NULL`
6. `created_at TEXT NOT NULL`
7. `updated_at TEXT NOT NULL`

### 4.4 `document_chapters`
1. `chapter_id TEXT PRIMARY KEY`
2. `document_id TEXT NOT NULL`
3. `chapter_title TEXT NOT NULL`
4. `order_index INTEGER NOT NULL`
5. `is_deleted INTEGER NOT NULL DEFAULT 0`
6. `deleted_at TEXT`
7. `created_at TEXT NOT NULL`
8. `updated_at TEXT NOT NULL`

### 4.5 `document_segments`
1. `segment_id TEXT PRIMARY KEY`
2. `document_id TEXT NOT NULL`
3. `chapter_id TEXT NOT NULL`
4. `chunk_id TEXT NOT NULL`
5. `content TEXT NOT NULL`
6. `order_index INTEGER NOT NULL`
7. `is_deleted INTEGER NOT NULL DEFAULT 0`
8. `deleted_at TEXT`
9. `created_at TEXT NOT NULL`
10. `updated_at TEXT NOT NULL`

### 4.6 `author_skill_snapshots`
1. `snapshot_id TEXT PRIMARY KEY`
2. `author_id TEXT NOT NULL`
3. `is_latest INTEGER NOT NULL`
4. `outputs_json TEXT NOT NULL`
5. `created_at TEXT NOT NULL`

### 4.7 查询口径约束
1. `manuscriptsCount` 为查询时聚合值（按 `author_documents` 计数），不落库。
2. 所有读取 chapter/segment 的查询默认过滤 `is_deleted=0`。

---

## 5. 执行阶段流水线（三类任务）

### 5.1 `author_skills`（作者级技能生成）
1. 拉取该 `author_id` 下全部 `active` 文档。
2. 读取这些文档下 `is_deleted=0` 的 chapter/segment 作为语料输入。
3. 执行 `analyze_method_chunks`（基于融合语料）。
   - 行为：按 max_words 合并段落，调用 LLM 进行方法分析，并输出 method_analysis JSON。
   - 参考：`backend\references\analyze_method_chunks_ref.py`
   - 提示词：`prompts\method_analysis_prompt.md`（参考 `backend\references\prompts\method_analysis_prompt_ref.md`）
   - 输出中必须包含：
      ```json
      "methodPatterns": {
        "raw_pattern": "...",
        "normalized_pattern": "...",
        "actions": ["..."],
        "method_program": "..."
      },
      "methodSignals": {
        "perspective": "...",
        "nature": "...",
        "time_orientation": "...",
        "system_scope": "...",
        "equilibrium_view": "...",
        "logic": ["..."]
      }
      ```
4. 执行 `generate_main_skills`。
   - 行为：每个章节只生成一个 `main_skill`，并要求唯一 `section_id`。
   - 低置信度过滤：按 `confidence` 排序，最低 20%（可调）标记删除。
   - 参考：`backend\references\generate_main_skills_ref.py`
   - 提示词：`prompts\main_skills_prompt.md`（参考 `backend\references\prompts\main_skills_prompt_ref.md`）
   - 输出 `main_skills_json` 必须包含：
      ```json
      {
        "section_id": "...",
        "main_skill_id": "...",
        "pattern_summary": {
          "name": "...",
          "description": "...",
          "applicability": "...",
          "core_steps": ["..."],
          "pattern_flow": ["..."],
          "chapter_method_summary": "..."
        },
        "signal_summary": {
          "perspective": {"value": "...", "notes": "..."},
          "nature": {"value": "...", "notes": "..."},
          "time_orientation": {"value": "...", "notes": "..."},
          "system_scope": {"value": "...", "notes": "..."},
          "equilibrium_view": {"value": "...", "notes": "..."},
          "logic": {"value": ["..."], "notes": "..."}
        },
        "confidence": 0.0
      }
      ```
5. 执行 `generate_sub_skills`。
   - 行为：按 `section_id + normalized_pattern` 聚合（仅章节内聚合），不同章节和不同书籍互不干扰。
   - 每个 sub_skill 必须携带 `section_id` 与 `main_skill_id`，用于稳定关联。
   - 参考：`backend\references\generate_sub_skills_ref.py`（需补齐 section/main 关联字段）
   - 提示词：`prompts\sub_skills_prompt.md`（参考 `backend\references\prompts\sub_skills_prompt_ref.md`）
   - 输出 `sub_skills_json` 必须包含：
      ```json
      {
        "section_id": "...",
        "main_skill_id": "...",
        "name": "...",
        "description": "...",
        "abstract_action_chain": ["..."],
        "method_program_summary": "...",
        "normalized_pattern": "...",
        "source_chunk_ids": [1, 2, 3],
        "method_program_example": "..."
      }
      ```
6. 执行 `render` 生成 md（内部能力，可对外读取）。
   - 行为：校验并读取 main/sub skills json，渲染主技能与子技能 markdown 文档。
   - 参考：
     - `backend\references\transform_main_skill_2_md_ref.py`
     - `backend\references\transform_sub_skill_2_md_ref.py`
7. 生成 `author_skill_snapshot`，设置 `is_latest=true`，旧 latest 置为 false。

### 5.2 `document_reload`（文档级重处理）
1. 仅处理指定 `document_id` 的源 PDF。
2. 执行 `extract_paragraphs` 切分 section/paragraph。
   - 行为：章节检测、文本过滤、段落合并规则严格参考 `backend\references\extract_paragraphs_ref.py`。
3. 将 `section_title -> chapter_id` 映射写死在流程中：
   - 先按 `(document_id, section_title)` upsert `document_chapters`；
   - 再回填 `chapter_id` 写入 `document_segments`。
4. 段落识别采用 `(document_id, chunk_id)` 作为同段判断键。
5. 软删除保留：若已有软删除记录，不回填为有效数据。
6. 任务完成后仅更新文档层数据，不自动创建 `author_skills` 任务。

### 5.3 `author_answer`（作者级问答）
1. 读取指定 `author_id` 的最新 `author_skill_snapshot`。
2. 执行 `select_skills`：
   - 读取 main skills 关键字段并结合 query 选择目标 `main_skill_id`。
   - 当前为设计占位（`select_skills.py` 与 `select_skills_prompt.md` 暂无 reference 实现）。
3. 基于选中的 main/sub skill markdown，执行 `answer_with_skills` 生成结构化 `answer_json`。
   - 参考：`backend\references\answer_with_skills_ref.py`
   - 提示词：`prompts\answer_with_skills_prompt.md`（参考 `backend\references\prompts\answer_with_skills_prompt_ref.md`）
4. 产出 `answer_json` 并绑定到 `pipeline_jobs.outputs_json`。
5. 如需 `answer.md`，后续可通过 json->markdown 转换流程内部生成，不纳入对外输出类型枚举。

### 5.4 阶段进度建议
1. `author_skills`：`analyze=35/main_skill=55/sub_skill=70/render=85/snapshot=100`
2. `document_reload`：`extract=60/segment_sync=100`
3. `author_answer`：`select_skills=40/answer=100`

---

## 6. 契约统一

### 6.1 段落标准契约
`{document_id, chapter_id, chunk_id, content, order_index}`

### 6.2 对外输出类型枚举（JSON+MD 并存）
1. `main_skill_json`
2. `sub_skill_json`
3. `answer_json`
4. `main_skill_md`
5. `sub_skills_md_zip`

说明：`answer_md` 不在对外输出枚举中。

### 6.3 轮询返回契约（`GET /api/jobs/{job_id}`）
1. `status`
2. `current_stage`
3. `progress`
4. `error_message`
5. `retryable`
6. `outputs_ready`

### 6.4 全局技术契约
1. 鉴权头统一：`X-API-Key`。
2. 时间字段统一为 UTC ISO 8601。
3. 模型凭据由服务端托管，前端不传 API Key。

---

## 7. API 设计（作者路由优先，轮询版）

### 7.1 作者与文档
1. `POST /api/authors`：创建作者
2. `GET /api/authors`：作者列表（扁平结构，含聚合 `manuscriptsCount`）
3. `POST /api/authors/{author_id}/documents`：上传作者文档
   - 行为：保存 `source.pdf` 并创建 `author_documents(status=processing)`；
   - 自动创建 `document_reload` 任务（无需前端二次点击）；
   - 返回：`{document_id, reload_job_id}`
4. `GET /api/authors/{author_id}/documents`：作者书单
5. `POST /api/authors/{author_id}/documents/{document_id}/reload`：文档级重处理
   - 返回：`{reload_job_id}`

### 7.2 章节与段落（嵌套路由）
1. `GET /api/authors/{author_id}/documents/{document_id}/chapters`
2. `GET /api/authors/{author_id}/documents/{document_id}/chapters/{chapter_id}/segments`
3. `DELETE /api/authors/{author_id}/documents/{document_id}/chapters/{chapter_id}`（软删除）
4. `DELETE /api/authors/{author_id}/documents/{document_id}/segments/{segment_id}`（软删除）

### 7.3 任务
1. `POST /api/authors/{author_id}/jobs/skills`：触发作者级技能生成
2. `POST /api/authors/{author_id}/jobs/answer`：触发作者级问答
3. `GET /api/jobs/{job_id}`：轮询任务状态（字段见 6.3）
4. `GET /api/jobs/{job_id}/outputs`：获取产物清单
5. `GET /api/jobs/{job_id}/outputs/{type}`：读取具体产物（类型见 6.2）
6. `POST /api/jobs/{job_id}/retry`：失败重试（后端保留 `from_stage`）
7. `POST /api/jobs/{job_id}/cancel`：取消任务

### 7.4 前端行为约束
1. 必须先选择作者，再触发 `skills` 或 `answer`。
2. `author_answer` 不允许“无作者”提交。
3. 前端仅提供“一键重试”，不暴露 `from_stage`。

---

## 8. 存储路径（作者分区）

1. `storage/authors/{author_id}/documents/{document_id}/source.pdf`
2. `storage/authors/{author_id}/jobs/{job_id}/...`
3. `storage/authors/{author_id}/snapshots/{snapshot_id}/main_skill.json`
4. `storage/authors/{author_id}/snapshots/{snapshot_id}/sub_skill.json`
5. `storage/authors/{author_id}/snapshots/{snapshot_id}/main_skill.md`
6. `storage/authors/{author_id}/snapshots/{snapshot_id}/sub_skills/*.md`
7. `storage/authors/{author_id}/answers/{job_id}/answer.json`
8. `storage/authors/{author_id}/answers/{job_id}/answer.md`（内部可选调试产物，不纳入对外类型枚举）

说明：
1. `outputs_json` 统一记录上述 URI，避免跨作者串读。
2. 前端默认消费 JSON 产物。

---

## 9. 失败、取消、重试策略

### 9.1 失败
1. 记录 `error_message`。
2. 保留已完成阶段产物。
3. 标记 `status=failed`，便于前端展示重试入口。

### 9.2 取消
1. `queued` 可直接取消。
2. `running` 在阶段边界检查取消标记并中断。

### 9.3 重试
1. 默认按任务类型选择起始阶段：
- `author_skills` 从 `analyze`（如无可用中间产物则回退到 `extract`）
- `document_reload` 从 `extract`
- `author_answer` 从 `select_skills`
2. 后端支持 `from_stage` 局部重跑（用于运维或高级接口）。
3. 重试时覆盖该阶段及后续产物。

---

## 10. 参考文件（V3 对照）
1. `extract_paragraphs.py`：参考 `backend\references\extract_paragraphs_ref.py`
2. `analyze_method_chunks.py`：参考 `backend\references\analyze_method_chunks_ref.py`，提示词参考 `backend\references\prompts\method_analysis_prompt_ref.md`
3. `generate_main_skills.py`：参考 `backend\references\generate_main_skills_ref.py`，提示词参考 `backend\references\prompts\main_skills_prompt_ref.md`
4. `generate_sub_skills.py`：参考 `backend\references\generate_sub_skills_ref.py`，提示词参考 `backend\references\prompts\sub_skills_prompt_ref.md`
5. `render.py`：参考
   - `backend\references\transform_main_skill_2_md_ref.py`
   - `backend\references\transform_sub_skill_2_md_ref.py`
6. `answer_with_skills.py`：参考 `backend\references\answer_with_skills_ref.py`，提示词参考 `backend\references\prompts\answer_with_skills_prompt_ref.md`
7. `select_skills.py` / `select_skills_prompt.md`：当前为设计占位，待补 reference 实现。

---

## 11. Assumptions
1. V3 仍采用轮询，不引入 SSE/事件流。
2. 文档级 `reload` 只更新文档层数据，不自动触发作者技能重建。
3. 章节/段落软删除不影响当前已生成快照，仅影响后续流程。
4. 前端作者选择是强约束：所有问答请求必须携带 `author_id`。
5. 前端导入文件后，后端默认自动触发 `document_reload` 以完成 section/paragraph 切分。
