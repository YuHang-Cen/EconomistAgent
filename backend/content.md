## 1. 本轮目标

1. 按 `backend/tech.md` 与 `backend/backend_design_v3.md` 完成后端第一阶段落地。
2. 先实现可运行的整体框架与目录骨架，不实现完整业务逻辑。
3. 完善 `backend/pyproject.toml` 的依赖、开发依赖、工具配置与常用命令入口。

## 2. 已完成内容（按模块）

### 2.1 工程与配置

1. 完成 `backend/pyproject.toml`：
   - 生产依赖：FastAPI、Uvicorn、SQLAlchemy、Alembic、Celery、Redis、python-dotenv、pydantic、pydantic-settings、PyMuPDF、langchain-openai。
   - 开发依赖组：Ruff、Mypy、Pytest、pytest-asyncio、httpx。
   - 工具配置：`tool.ruff`、`tool.mypy`、`tool.pytest`。
   - 常用脚本入口：`dev/worker/lint/format/typecheck/test`（可通过 `uv run <script>` 使用）。
   - 补充构建配置：`hatchling` 与 `tool.hatch.build.targets.wheel.packages = ["app"]`。
2. 新增 `backend/.env.example`，字段与参考 `.env` 保持一致。
3. 执行 `uv sync --all-groups`，生成 `backend/uv.lock`。

### 2.2 应用骨架（app）

1. 新增 `app/main.py`：
   - FastAPI 应用创建。
   - `request_id` 中间件。
   - 全局异常处理占位。
   - 统一 envelope 响应调用。
   - `/health` 健康检查。
2. 新增 `app/api/deps.py` 与三套路由骨架：
   - `app/api/routes/authors.py`
   - `app/api/routes/segments.py`
   - `app/api/routes/jobs.py`
3. 新增 `app/domain`：
   - `enums.py`（JobStatus/JobType/Stage/OutputType）。
   - `models.py`（authors、author_documents、document_chapters、document_segments、author_skill_snapshots、pipeline_jobs）。
   - `schemas.py`（统一 API envelope、错误体、请求响应模型，camelCase 输出能力）。
4. 新增 `app/services` 全量阶段骨架：
   - `author_service.py`
   - `segment_service.py`
   - `job_service.py`
   - `pipeline_service.py`
   - `stage_runners.py`
   - `extract_paragraphs.py`
   - `analyze_method_chunks.py`
   - `main_skill.py`
   - `sub_skill.py`
   - `select_skills.py`
   - `answer_with_skills.py`
   - `render.py`
5. 新增 `app/infra`：
   - `settings.py`：统一加载 `backend/.env`。
   - `db.py`：SQLAlchemy engine/session 初始化（默认 SQLite）。
   - `queue.py`：Celery app 初始化（Redis broker/backend）。
   - `storage.py`：作者分区存储路径骨架。
   - `logging.py`：日志初始化。
6. 新增 `app/prompts/*.md`，全部为英文占位提示词。

### 2.3 scripts / tests / alembic

1. 新增脚本：
   - `scripts/migrate.py`
   - `scripts/worker.py`
2. 新增测试结构：
   - `tests/conftest.py`
   - `tests/unit/test_health.py`
   - `tests/unit/.gitkeep`
   - `tests/integration/.gitkeep`
   - `tests/e2e/.gitkeep`
3. 新增 Alembic 结构：
   - `alembic/env.py`
   - `alembic/script.py.mako`
   - `alembic/versions/.gitkeep`

### 2.4 规范落实

1. 所有新建 `.py` 文件都以中文三引号职责注释开头。
2. Prompt 文件内容为英文。
3. 内部命名使用 `snake_case`。
4. 在 schema 层提供了 camelCase 输出基础（alias_generator）。
5. 保持 `PipelineJob + 轮询` 方向，未引入 SSE/WebSocket。

## 3. 关键文件变更清单

1. `backend/pyproject.toml`
2. `backend/.env.example`
3. `backend/app/main.py`
4. `backend/app/cli.py`
5. `backend/app/api/deps.py`
6. `backend/app/api/routes/authors.py`
7. `backend/app/api/routes/segments.py`
8. `backend/app/api/routes/jobs.py`
9. `backend/app/domain/enums.py`
10. `backend/app/domain/models.py`
11. `backend/app/domain/schemas.py`
12. `backend/app/services/*.py`（12 个骨架文件）
13. `backend/app/infra/*.py`（5 个基础文件）
14. `backend/app/prompts/*.md`（5 个英文提示词）
15. `backend/scripts/migrate.py`
16. `backend/scripts/worker.py`
17. `backend/tests/conftest.py`
18. `backend/tests/unit/test_health.py`
19. `backend/alembic/env.py`
20. `backend/alembic/script.py.mako`
21. `backend/uv.lock`

## 4. 验证结果（执行命令与结果）

1. `python -m compileall app scripts`：通过。
2. `uv sync --all-groups`：通过（首次因 wheel 打包目录未声明失败，已通过 `tool.hatch.build.targets.wheel.packages=["app"]` 修复）。
3. `uv run python -c "import app.main, app.domain.schemas, app.infra.settings; print('import-ok')"`：通过。
4. `uv run ruff format app scripts tests alembic`：通过。
5. `uv run ruff check app scripts tests alembic`：通过。
6. `uv run mypy app`：通过。
7. `uv run python -m pytest -q`：通过（`1 passed`）。

## 5. 未完成项与风险

1. 业务逻辑仍为骨架占位，尚未接入真实 DB CRUD。
2. `document_reload` / `author_skills` / `author_answer` 三类任务尚未完成真实阶段编排与状态推进。
3. `select_skills` 仍是占位实现，尚未实现真正的技能选择算法。
4. Alembic 目录已创建，但尚未产出首个真实迁移脚本。
5. API 响应 envelope 已统一，但错误码分类与异常映射仍需细化到全部业务场景。
6. 在当前 Windows 非 ASCII 路径（`D:\桌面\...`）下，`uv run <project-script>` 存在模块解析异常风险，当前验证采用直接命令（如 `uv run ruff ...`、`uv run python -m pytest ...`）可正常执行。

## 6. 下一步目标（第二阶段，可执行）

1. 完成数据库首版建模落地：
   - 输出首个 Alembic migration，创建 V3 约定的 6 张核心表。
   - 在 `models.py` 与 migration 间做一致性校验。
2. 打通作者与文档主链路最小闭环：
   - `POST /api/authors`
   - `POST /api/authors/{author_id}/documents`
   - 自动创建 `document_reload` 任务并写入 `pipeline_jobs`。
3. 打通任务轮询最小闭环：
   - `GET /api/jobs/{job_id}` 返回真实任务状态。
   - `POST /api/jobs/{job_id}/cancel` 与 `retry` 先做最小语义实现。
4. 落地 `document_reload` 最小可运行阶段：
   - 先完成 `extract -> segment_sync`，并将章节段落写入 DB。
5. 增加最小集成测试：
   - 作者创建、文档上传触发任务、任务轮询三条用例。

## 保守假设（按要求记录）

1. `uv run <script>` 通过 `project.scripts` 提供命令入口（`dev/worker/lint/format/typecheck/test`）。
2. 本阶段以“可运行骨架 + 配置”为边界，不提前实现完整业务逻辑与复杂错误处理。
3. lint 范围排除 `backend/references`（参考脚本不是当前实现代码，不纳入本阶段质量门禁）。
