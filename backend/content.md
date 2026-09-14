## 当前后端实现摘要

### 任务执行

三类流水线任务（`document_reload`、`author_skills`、`author_answer`）由进程内单线程执行器顺序运行，保持 `PipelineJob + HTTP 轮询` 契约不变。创建任务立即返回，执行器在后台推进状态和进度。

取消操作通过数据库状态在阶段边界生效；失败或取消任务可以重试。应用重启时，遗留的 `queued` 和 `running` 任务会被标记为失败，避免任务永久卡住。

### 产物和存储

运行数据使用 SQLite，并按作者、文档、任务和快照写入 `backend/storage/`。`outputs_json` 保存 `artifact_type -> storage URI` 映射，现有产物读取 API 保持不变。

### 运行约束

- 单进程、单任务执行并发，适合 Demo 和轻量部署。
- 应用进程退出后，内存中的待执行任务不会恢复，但数据库记录仍可查询和重试。
- 多实例和高并发场景需要另行设计持久化任务系统。

### 质量门禁

```bash
uv run ruff check app scripts tests alembic
uv run ruff format --check app scripts tests alembic
uv run mypy app
uv run python -m pytest -q
```
