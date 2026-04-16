# Economist Agent Backend 技术基线（V1）

- 文档版本：v1.0
- 日期：2026-04-16
- 适用范围：仅后端（`backend/`）
- 设计基准：`backend/backend_design_v3.md`

## 1. 目标

本文件用于一次性锁定后端实现基线，覆盖：

1. 技术栈确认。
2. 最终目录结构（文件级）。
3. 代码与接口规范。
4. 测试与质量门禁。

该文档是后续开发、评审、联调的唯一后端技术标准。

## 2. 技术栈确认

### 2.1 运行时与工程工具

1. Python：`3.11+`
2. 包管理与运行：`uv`
3. Web/API：`FastAPI + Uvicorn`
4. ORM 与迁移：`SQLAlchemy 2 + Alembic`
5. 异步任务：`Celery + Redis`（任务状态通过 `PipelineJob + 轮询` 暴露）
6. 配置加载：`python-dotenv`（统一加载 `backend/.env`）
7. LLM 调用：Provider 抽象层，默认 `DeepSeek`
8. PDF 解析：`PyMuPDF(fitz)`
9. 质量工具：`Ruff + Mypy + Pytest`

### 2.2 数据库策略

1. V1 默认数据库：`SQLite`
2. 迁移工具：`Alembic`（迁移脚本必须保持可切换到 `PostgreSQL`）
3. 禁止写死 SQLite 方言特性到业务层。

### 2.3 环境变量策略

1. 使用 `backend/.env` 保存本地环境变量。
2. 必须提供 `backend/.env.example`（只放占位值，不放真实密钥）。
3. 服务启动、脚本入口、worker 启动均需统一加载 dotenv。
4. 前端不传模型密钥；模型密钥只在后端读取与使用。

建议最小变量集合（与 `backend/references/.env` 对齐）：

```env
DEEPSEEK_API_KEY=your_key
PROVIDER=deepseek
MODEL_NAME=deepseek-chat
API_BASE=https://api.deepseek.com
DATABASE_URL=sqlite:///./storage/app.db
REDIS_URL=redis://127.0.0.1:6379/0
API_KEY=replace_with_service_api_key
```

## 3. 最终目录结构（目标态，文件级）

```text
backend/
  app/
    main.py
    api/
      deps.py
      routes/
        authors.py
        segments.py
        jobs.py
    domain/
      enums.py
      models.py
      schemas.py
    services/
      author_service.py
      segment_service.py
      job_service.py
      pipeline_service.py
      stage_runners.py
      extract_paragraphs.py
      analyze_method_chunks.py
      main_skill.py
      sub_skill.py
      select_skills.py
      answer_with_skills.py
      render.py
    infra/
      settings.py
      db.py
      queue.py
      storage.py
      logging.py
    prompts/
      method_analysis_prompt.md
      main_skills_prompt.md
      sub_skills_prompt.md
      select_skills_prompt.md
      answer_with_skills_prompt.md
  scripts/
    migrate.py
    worker.py
  tests/
    conftest.py
    unit/
    integration/
    e2e/
  alembic/
    env.py
    script.py.mako
    versions/
  .env
  .env.example
  pyproject.toml
  README.md
  tech.md
```

## 4. 代码规范（强制）

### 4.1 文档与注释

1. 每个 `.py` 文件开头必须使用中文三引号注释描述职责，例如：

```python
"""负责处理作者与文档管理相关的应用服务逻辑。"""
```

2. Prompt 文件与 Prompt 正文必须为英文。
3. 注释优先说明“为什么”和“边界条件”，避免重复代码字面含义。

### 4.2 命名与类型

1. Python 内部命名统一 `snake_case`。
2. 对外 API JSON 字段统一 `camelCase`。
3. 所有业务函数必须有类型注解。
4. 所有公共接口（请求/响应体）必须使用 Pydantic Schema。

### 4.3 时间、鉴权与安全

1. 时间字段统一 `UTC ISO 8601`。
2. 鉴权头统一 `X-API-Key`。
3. 后端负责密钥托管，禁止要求前端传入 Provider API Key。
4. 日志中禁止打印明文密钥与敏感凭据。

## 5. API 统一响应包裹（强制）

### 5.1 成功响应

```json
{
  "success": true,
  "data": {},
  "error": null,
  "requestId": "uuid",
  "timestamp": "2026-04-16T08:30:00Z"
}
```

### 5.2 失败响应

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "invalid authorId",
    "details": {}
  },
  "requestId": "uuid",
  "timestamp": "2026-04-16T08:30:00Z"
}
```

### 5.3 最小错误码集合

1. `INVALID_ARGUMENT`：参数错误。
2. `UNAUTHORIZED`：鉴权失败。
3. `NOT_FOUND`：资源不存在。
4. `TASK_CONFLICT`：任务冲突（重复执行、状态不允许重试等）。
5. `INTERNAL_ERROR`：服务内部错误。

## 6. 与 backend_design_v3 对齐的执行约束

1. 上传文档后，后端自动创建并触发 `document_reload`（自动完成 section/paragraph 切分）。
2. `document_reload` 只更新文档层数据，不自动触发 `author_skills`。
3. `author_answer` 请求必须携带 `author_id`。
4. 对外产物类型固定为：
   - `main_skill_json`
   - `sub_skill_json`
   - `answer_json`
   - `main_skill_md`
   - `sub_skills_md_zip`
5. V1 统一通过轮询接口查询任务状态，不引入 SSE/WebSocket。

## 7. 测试计划与质量门禁

### 7.1 测试计划

1. 配置测试：验证 dotenv 自动加载；缺失必填变量时启动失败并给出明确错误。
2. API 合约测试：所有路由返回统一 envelope，且对外字段为 camelCase。
3. 数据一致性测试：软删除章节/段落后不再参与后续流程输入。
4. 流水线测试：`author_skills`、`document_reload`、`author_answer` 的阶段推进与 progress 正确。
5. 队列测试：Celery worker 执行、失败重试、取消任务语义正确。

### 7.2 质量门禁（CI 必须通过）

1. `ruff check .`
2. `ruff format --check .`
3. `mypy app`
4. `pytest -q`

## 8. Assumptions

1. 本文档仅约束后端，不同步改写前端设计文档。
2. 默认 Provider 为 DeepSeek，但必须保留可扩展 Provider 抽象。
3. V1 保持轮询架构，不引入 SSE/WebSocket。
4. SQLite 为当前落地数据库，迁移路径由 Alembic 保证。
