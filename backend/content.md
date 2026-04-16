## 1. 本轮目标

1. 严格按 `backend/backend_design_v3.md`、`backend/tech.md` 与 `backend/content.md`（第三阶段）完成后端第三阶段落地。
2. 打通 `author_skills` 最小闭环：读取作者 active 文档与未软删段落，串联 `analyze_method_chunks -> main_skill -> sub_skill -> render`，写入 `author_skill_snapshots` 并维护 latest 语义。
3. 打通 `author_answer` 最小闭环：强制 `author_id`，读取 latest snapshot，执行可复现 `select_skills`，产出 `answer_json`。
4. 完善任务产物读取：`GET /api/jobs/{job_id}/outputs` 与 `GET /api/jobs/{job_id}/outputs/{type}` 对齐 V3 输出类型与错误语义。
5. 增加第三阶段集成测试并执行规定校验命令。

## 2. 已完成内容（按模块）

### 2.1 author_skills 最小闭环

1. 在 `app/services/pipeline_service.py` 实现 `run_author_skills`：
   - 读取作者下 `active` 文档。
   - 仅读取 `is_deleted=0` 的 `document_chapters/document_segments`。
   - 串联阶段：`analyze -> main_skill -> sub_skill -> render`。
2. 按 V3 语义推进任务状态与进度：
   - `analyze=35`、`main_skill=55`、`sub_skill=70`、`render=85`、完成 `100`。
3. 产出并写入任务产物：
   - `main_skill_json`
   - `sub_skill_json`
   - `main_skill_md`
   - `sub_skills_md_zip`
4. 写入 `author_skill_snapshots` 并维护 latest：
   - 新快照 `is_latest=true`
   - 旧快照批量切换 `is_latest=false`
5. 回填 `pipeline_jobs.snapshot_id` 与 `pipeline_jobs.outputs_json`，轮询接口可见。

### 2.2 author_answer 最小闭环

1. 在 `app/services/pipeline_service.py` 实现 `run_author_answer`：
   - 强制依赖 `author_id`（路由层已通过 `/api/authors/{author_id}/jobs/answer` 保证）。
   - 读取该作者 latest snapshot。
2. 实现最小可复现选择链路：
   - `select_skills` 使用 deterministic 规则（基于 query 与技能文本匹配）选择技能。
3. 生成 `answer_json` 并写入 `pipeline_jobs.outputs_json`。
4. 阶段推进与进度对齐 V3：
   - `select_skills=40`
   - `answer=100`

### 2.3 任务执行与产物读取能力

1. 在 `app/services/job_service.py` 增加三类任务执行分发与重试分发：
   - `document_reload`
   - `author_skills`
   - `author_answer`
2. 对齐 V3 对外产物类型枚举过滤：
   - `main_skill_json`
   - `sub_skill_json`
   - `answer_json`
   - `main_skill_md`
   - `sub_skills_md_zip`
3. `GET /api/jobs/{job_id}/outputs/{type}` 行为补齐：
   - 非法 `type` 返回 `422 INVALID_ARGUMENT`
   - 缺失产物返回 `404 NOT_FOUND`
4. 统一响应 envelope 继续生效：`success/data/error/requestId/timestamp`。

### 2.4 第三阶段测试补齐

1. 新增 `tests/integration/test_skills_answer_outputs.py`，覆盖：
   - `author_skills` 跑通并写入 snapshot/产物。
   - `author_answer` 跑通并产出 `answer_json`。
   - `outputs` 与 `outputs/{type}` 成功/非法 type/缺失产物分支。
2. 测试通过，当前后端测试总数 `7 passed`。

## 3. 关键文件变更清单

1. `backend/app/services/pipeline_service.py`
2. `backend/app/services/job_service.py`
3. `backend/app/services/stage_runners.py`
4. `backend/app/services/analyze_method_chunks.py`
5. `backend/app/services/main_skill.py`
6. `backend/app/services/sub_skill.py`
7. `backend/app/services/render.py`
8. `backend/app/services/select_skills.py`
9. `backend/app/services/answer_with_skills.py`
10. `backend/tests/integration/test_skills_answer_outputs.py`
11. `backend/content.md`

## 4. 验证结果（命令 + 结果）

1. `uv run ruff check app scripts tests alembic`
- 结果：通过（`All checks passed!`）
2. `uv run ruff format --check app scripts tests alembic`
- 结果：通过（`35 files already formatted`）
3. `uv run mypy app`
- 结果：通过（`Success: no issues found in 27 source files`）
4. `uv run python -m pytest -q`
- 结果：通过（`7 passed in 0.54s`）
5. `uv run alembic -c alembic.ini upgrade head`
- 结果：通过（SQLite migration context 正常，无报错）

## 5. 未完成项与风险（含假设说明）

1. 第三阶段按“最小闭环”实现，`analyze/main/sub/select/answer/render` 仍是可运行简化逻辑，尚未完全接入 references 对应的完整 Prompt/LLM 生产策略。
2. 当前任务创建后默认在服务内同步执行（`auto_run=True` 的最小实现），尚未切换为 Celery Worker 异步消费；但对外仍保持 `PipelineJob + 轮询` 契约。
3. 当前 `outputs_json` 存储的是可直接读取的结构化内容；尚未全部切换为 storage URI 映射（`artifact_type -> uri`）的最终形态。
4. 本轮运行产生了本地数据库文件变更（`backend/storage/app.db`），属于运行态产物，不属于第三阶段功能代码。
5. 保守一致假设：在未接入完整模型编排前，deterministic `select_skills` 与模板化 `answer_json` 可作为第三阶段验收口径。

## 6. 下一步目标（第四阶段，可执行）

1. 将三类任务执行从同步 `auto_run` 切换为 Celery + Redis 异步执行，保持现有轮询契约不变。
2. 将任务产物落盘到 `storage/authors/...`，并把 `outputs_json` 统一收敛为 `artifact_type -> uri`。
3. 依据 `backend/references` 完成 `extract/analyze/main/sub/select/answer/render` 的生产版实现与 Prompt 装配。
4. 补充软删除一致性与重试/取消语义的集成测试（覆盖失败重试、取消后不可继续执行等分支）。
5. 增加 `author_answer` 无 latest snapshot、无可用技能、空查询等边界场景测试与错误码校验。
