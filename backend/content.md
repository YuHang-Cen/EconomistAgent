## 1. 本轮目标

1. 严格按 `backend/tech.md` 与 `backend/backend_design_v3.md` 完成第二阶段落地，不扩展到第三阶段。
2. 完成数据库首个迁移与核心表落地，打通作者创建、文档上传自动触发 `document_reload`、任务轮询/取消/重试最小闭环。
3. 完成 `document_reload` 最小链路（`extract -> segment_sync`）并将章节/段落写入数据库。
4. 新增至少三条集成测试并完成规定验证命令。

## 2. 已完成内容（按模块）

### 2.1 数据库与迁移

1. 新增 `alembic.ini`，支持 `alembic -c alembic.ini` 运行迁移。
2. 新增首个迁移 `backend/alembic/versions/20260416_0001_init_core_tables.py`，创建 6 张核心表：
   - `authors`
   - `author_documents`
   - `document_chapters`
   - `document_segments`
   - `author_skill_snapshots`
   - `pipeline_jobs`
3. `models.py` 与迁移对齐：
   - 新增 `(document_id, chapter_title)` 唯一约束。
   - 新增 `(document_id, chunk_id)` 唯一约束。
   - `pipeline_jobs` 字段与 V3 约定保持一致（含 `status/current_stage/progress/error_message/outputs_json` 等）。
4. 解决 SQLite 文件路径问题：
   - `app/infra/db.py` 与 `alembic/env.py` 在启动时自动创建 sqlite 文件目录，避免 `unable to open database file`。

### 2.2 作者与文档闭环

1. `POST /api/authors` 已落库，返回统一 envelope + camelCase 数据字段。
2. `POST /api/authors/{author_id}/documents` 已落库并自动创建 `document_reload` 任务。
3. 上传文档后自动执行 `document_reload`，并将文档状态从 `processing` 更新为 `active/failed`。
4. `POST /api/authors/{author_id}/documents/{document_id}/reload` 可手动触发单文档重处理并返回 `reloadJobId`。

### 2.3 任务轮询与状态机

1. `GET /api/jobs/{job_id}` 返回轮询契约字段：
   - `status`
   - `currentStage`
   - `progress`
   - `errorMessage`
   - `retryable`
   - `outputsReady`
2. `POST /api/jobs/{job_id}/cancel` 实现最小合法状态机：
   - 仅允许取消 `queued/running`
   - 对 `success/failed/canceled` 返回冲突错误
3. `POST /api/jobs/{job_id}/retry` 实现最小合法状态机：
   - 仅允许重试 `failed/canceled`
   - 重置阶段与状态后执行对应最小逻辑

### 2.4 document_reload 最小链路

1. 已实现 `extract -> segment_sync` 最小流水线：
   - `extract`：`app/services/extract_paragraphs.py`
   - `segment_sync`：`app/services/pipeline_service.py`
2. 章节映射与段落写入规则：
   - 按 `(document_id, section_title)` upsert `document_chapters`
   - 按 `(document_id, chunk_id)` upsert `document_segments`
3. 软删除约束已执行：
   - 已软删除章节不会被回填
   - 已软删除段落不会被回填为有效数据
4. 明确保持 V3 约束：
   - `document_reload` 不自动触发 `author_skills`
   - 架构仍是 `PipelineJob + 轮询`，未引入 SSE/WebSocket

### 2.5 测试

1. 新增 `tests/integration/test_author_document_job_flow.py`，覆盖 3 条集成测试：
   - 作者创建
   - 文档上传触发 `document_reload`
   - 任务轮询状态读取
2. 更新 `tests/conftest.py`：
   - 每个用例前重建数据库
   - 统一注入 `X-API-Key`
3. 当前测试总计通过：`4 passed`

## 3. 关键文件变更清单

1. `backend/alembic.ini`
2. `backend/alembic/env.py`
3. `backend/alembic/versions/20260416_0001_init_core_tables.py`
4. `backend/app/domain/models.py`
5. `backend/app/domain/schemas.py`
6. `backend/app/infra/db.py`
7. `backend/app/main.py`
8. `backend/app/api/routes/authors.py`
9. `backend/app/services/author_service.py`
10. `backend/app/services/job_service.py`
11. `backend/app/services/pipeline_service.py`
12. `backend/app/services/extract_paragraphs.py`
13. `backend/app/services/segment_service.py`
14. `backend/app/services/stage_runners.py`
15. `backend/scripts/migrate.py`
16. `backend/tests/conftest.py`
17. `backend/tests/integration/test_author_document_job_flow.py`

## 4. 验证结果（执行命令与结果）

1. `uv run ruff check app scripts tests alembic`：通过。
2. `uv run ruff format --check app scripts tests alembic`：通过。
3. `uv run mypy app`：通过。
4. `uv run python -m pytest -q`：通过（`4 passed`）。
5. `uv run alembic -c alembic.ini upgrade head`：通过。
6. `uv run python -c "import sqlite3; ..."` 验证表结构：数据库中存在
   - `authors`
   - `author_documents`
   - `document_chapters`
   - `document_segments`
   - `author_skill_snapshots`
   - `pipeline_jobs`
   - `alembic_version`

## 5. 未完成项与风险

1. `author_skills` 与 `author_answer` 仍为占位执行逻辑，仅 document_reload 达到最小可运行。
2. `select_skills` 仍未实现真实选择策略，后续问答链路尚未与技能快照打通。
3. 当前 `extract` 为最小实现（本地 PDF 可提取，非本地 URI 走兜底段落），未接入 references 中完整切分策略。
4. 未实现 `GET /api/jobs/{job_id}/outputs` 的真实产物文件读取能力，仅提供最小 JSON 索引读取。
5. 保守假设：第二阶段允许 `document_reload` 同步执行（在创建任务后立即跑完），后续可切到 Celery 异步消费而不改外部接口。

## 6. 下一步目标（第三阶段，可执行）

1. 打通 `author_skills` 最小闭环：
   - 读取作者 active 文档章节段落
   - 接入 `analyze_method_chunks -> main_skill -> sub_skill -> render` 阶段骨架
   - 产出并写入 `author_skill_snapshots`
2. 打通 `author_answer` 最小闭环：
   - 强制携带 `author_id`
   - 读取 latest snapshot
   - 实现 `select_skills` 最小规则并输出 `answer_json`
3. 完善任务产物读取接口：
   - `GET /api/jobs/{job_id}/outputs`
   - `GET /api/jobs/{job_id}/outputs/{type}`
   - 对齐 V3 对外产物类型枚举
4. 增加软删除一致性测试：
   - 删除章节/段落后再次 `document_reload` 不回填软删数据
5. 将 `document_reload` 从同步执行切换到 Celery 异步执行，并保持轮询契约不变。

