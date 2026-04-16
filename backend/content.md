## 1. 本轮目标

1. 严格按 `backend/backend_design_v3.md`、`backend/tech.md` 与 `backend/content.md`（第四阶段）完成本轮落地，不提前实现第五阶段内容。
2. 将三类任务执行从同步最小实现切换为 `Celery + Redis` 队列语义，保持 `PipelineJob + 轮询` 契约不变。
3. 将 `outputs_json` 统一为 `artifact_type -> uri`，并把产物落盘到 `storage/authors/...`。
4. 依据 `backend/references` 重构 `extract/analyze/main/sub/select/answer/render` 为可运行生产化版本（含 Prompt 装配与无密钥兜底）。
5. 补齐第四阶段测试：软删除一致性、重试/取消语义、`author_answer` 边界场景。

## 2. 已完成内容（按模块）

### 2.1 任务执行架构（Celery + 轮询）

1. `app/services/job_service.py` 已改为“创建任务即入队”（`delay`），不再直接同步执行 pipeline。
2. 三类任务全部走 Celery 分发：
   - `document_reload`
   - `author_skills`
   - `author_answer`
3. 保持 V3 轮询契约不变：`GET /api/jobs/{job_id}` 仍返回 `status/currentStage/progress/errorMessage/retryable/outputsReady`。
4. 新增阶段边界取消语义：
   - `pipeline_service` 在关键阶段推进前检查取消标记；
   - worker 执行层对取消状态做短路处理，保证“取消后不可继续执行”。

### 2.2 产物落盘与 URI 化

1. `app/infra/storage.py` 补齐作者分区路径与落盘能力：
   - `documents/{document_id}`
   - `jobs/{job_id}`
   - `snapshots/{snapshot_id}`
   - `answers/{job_id}`
2. 新增通用落盘能力：`write_json / write_text / write_zip_from_files`，并统一返回 storage URI。
3. `author_skills` 产物改为落盘并写 URI：
   - `main_skill_json`
   - `sub_skill_json`
   - `main_skill_md`
   - `sub_skills_md_zip`
4. `author_answer` 产物改为落盘并写 URI：
   - `answer_json`
5. `GET /api/jobs/{job_id}/outputs/{type}` 已改为按 URI 读取真实内容：
   - `.json` 解析后返回对象
   - `.md` 返回文本
   - `.zip` 返回可读清单（URI + 文件名列表）

### 2.3 阶段服务生产化重构（参考 references）

1. 新增 `app/services/llm_utils.py`：统一 Prompt 加载、占位符渲染、可选 LLM 初始化、JSON 解析恢复。
2. `extract_paragraphs.py`：接入章节识别/段落清洗逻辑，并保留无本地 PDF 的可复现 fallback。
3. `analyze_method_chunks.py`：实现 max_words 分块 + Prompt 装配 + LLM 可选调用（失败自动 fallback）。
4. `main_skill.py`：按章节聚合输入，生成章节级 main skill，并执行低置信度过滤（`floor(N*0.2)`）。
5. `sub_skill.py`：按 `section_id + normalized_pattern` 聚合，保证 `main_skill_id` 关联稳定。
6. `render.py`：将 main/sub skill 渲染为 markdown，并为子技能生成 zip 输入文件列表。
7. `answer_with_skills.py`：按 `{{SKILLS_CONTEXT}} + {{QUERY}}` 装配 Prompt，LLM 失败自动降级为 deterministic 回答。
8. Prompt 文件已与生产化装配对齐（全部英文且具备占位符）：
   - `method_analysis_prompt.md`
   - `main_skills_prompt.md`
   - `sub_skills_prompt.md`
   - `answer_with_skills_prompt.md`

### 2.4 第四阶段测试补齐

1. 更新 `tests/conftest.py`：测试环境开启 Celery eager 模式，验证“走队列语义但本地可同步完成”。
2. 调整既有集成测试以适配异步轮询语义（创建任务后通过 `GET /jobs/{job_id}` 等待终态）。
3. 新增 `tests/integration/test_stage4_pipeline_behaviors.py`，覆盖：
   - 软删除章节/段落后再次 `document_reload` 不回填软删数据
   - 失败重试语义
   - 取消后不可继续执行语义
   - `author_answer` 无 latest snapshot / 空 query / 无可用技能
4. 当前测试总数通过：`10 passed`。

## 3. 关键文件变更清单

1. `backend/app/infra/settings.py`
2. `backend/app/infra/queue.py`
3. `backend/app/infra/storage.py`
4. `backend/app/services/llm_utils.py`
5. `backend/app/services/extract_paragraphs.py`
6. `backend/app/services/analyze_method_chunks.py`
7. `backend/app/services/main_skill.py`
8. `backend/app/services/sub_skill.py`
9. `backend/app/services/render.py`
10. `backend/app/services/select_skills.py`
11. `backend/app/services/answer_with_skills.py`
12. `backend/app/services/pipeline_service.py`
13. `backend/app/services/job_service.py`
14. `backend/app/prompts/method_analysis_prompt.md`
15. `backend/app/prompts/main_skills_prompt.md`
16. `backend/app/prompts/sub_skills_prompt.md`
17. `backend/app/prompts/answer_with_skills_prompt.md`
18. `backend/tests/conftest.py`
19. `backend/tests/integration/test_author_document_job_flow.py`
20. `backend/tests/integration/test_skills_answer_outputs.py`
21. `backend/tests/integration/test_stage4_pipeline_behaviors.py`
22. `backend/content.md`

## 4. 验证结果（命令 + 结果）

1. `uv run ruff check app scripts tests alembic`
- 结果：通过（`All checks passed!`）

2. `uv run ruff format --check app scripts tests alembic`
- 结果：通过（`37 files already formatted`）

3. `uv run mypy app`
- 结果：通过（`Success: no issues found in 28 source files`）

4. `uv run python -m pytest -q`
- 结果：通过（`10 passed in 10.85s`）

5. `uv run alembic -c alembic.ini upgrade head`
- 首次结果：失败（`table authors already exists`，原因是测试基座先 `Base.metadata.create_all`，但未写入 `alembic_version`）
- 修复动作：执行 `uv run alembic -c alembic.ini stamp head`
- 再次执行 `uv run alembic -c alembic.ini upgrade head`：通过

## 5. 未完成项与风险（含保守一致假设）

1. 第四阶段虽已接入 references 的结构与 Prompt 装配，但当前仍保留“LLM 不可用/调用失败自动 fallback”路径，线上质量仍取决于有效模型密钥与真实提示词调优。
2. `select_skills` 仍为 deterministic 规则；因 references 未提供该模块实现，本轮按 `tech.md + v3` 做最保守一致假设。
3. `outputs/{type}` 对 `sub_skills_md_zip` 当前返回文件清单而非二进制下载流；满足“可读”但尚未实现下载型接口。
4. 测试采用 Celery eager 模式验证队列语义，尚未覆盖“独立 worker + Redis 网络抖动”下的真实并发与重试时序。
5. 保守一致假设：在无可用 DeepSeek 密钥或鉴权失败（401）时，允许使用 deterministic fallback 保障流程可运行与可测。

## 6. 下一步目标（第五阶段，可执行）

1. 引入真实异步集成测试（独立 Redis + Celery worker 进程），覆盖并发任务、任务取消时序、失败重试与幂等性。
2. 将 `sub_skills_md_zip` 与其他产物补齐“下载能力”（流式返回或预签名 URI），并保持现有 envelope 契约不变。
3. 强化 Provider 抽象与错误分层：区分密钥错误、限流、超时、响应格式错误，映射统一错误码与可重试策略。
4. 增加 `author_skills/author_answer/document_reload` 的阶段级可观测日志字段（阶段耗时、产物 URI、错误分类）。
5. 增加迁移一致性与数据库初始化策略：统一处理“metadata 建表”与 Alembic 版本状态，消除 `upgrade head` 首次冲突风险。
