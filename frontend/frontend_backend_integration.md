# 前后端对接方案（Archive / Segment / Methodology / Analysis）

本文以 `frontend/frontend_design.md` 与 `backend/backend_design_v3.md` 的当前实现为准，目标是让前端按统一契约对接后端。

## 全局约定
- Base URL: `http://127.0.0.1:8000/api`
- Header: `X-API-Key`
- 统一响应: `{ success, data, error, requestId, timestamp }`
- 命名统一使用后端字段: `authorId/documentId/chapterId/segmentId/jobId`
- 前端业务真值来自后端，不使用 `mockData/articles` 作为生产数据源

## 数据库到前端显示映射
- `authors` -> `AuthorVM`
  - `author_id -> authorId`
  - `author_name -> authorName`
  - `school -> school`
  - `avatar_url -> avatarUrl`
- `author_documents` -> `DocumentVM`
  - `document_id -> documentId`
  - `author_id -> authorId`
  - `book_title -> bookTitle`
  - `pdf_uri -> pdfUri`
  - `status -> status(processing/active/failed)`
- `document_chapters` -> `ChapterVM`
  - `chapter_id -> chapterId`
  - `chapter_title -> chapterTitle`
  - `order_index -> orderIndex`
- `document_segments` -> `SegmentVM`
  - `segment_id -> segmentId`
  - `chunk_id -> chunkId`
  - `content -> content`
  - `order_index -> orderIndex`
- `pipeline_jobs` -> `JobVM`
  - `job_id -> jobId`
  - `job_type -> jobType`
  - `status/current_stage/progress/error_message -> status/currentStage/progress/errorMessage`

## Archive
### 页面目标
- 管理作者
- 上传/重载文档
- 显示文档状态（`processing/active/failed`）

### 接口链路
1. `GET /authors` 获取作者列表
2. `GET /authors/{authorId}/documents` 获取作者文档
3. `POST /authors` 创建作者
4. `POST /authors/{authorId}/documents` 上传文档（返回 `reloadJobId`）
5. 轮询 `GET /jobs/{reloadJobId}` 到终态
6. `POST /authors/{authorId}/documents/{documentId}/reload` 手动重载
7. `DELETE /authors/{authorId}` 删除作者（级联清理）

### UI行为
- 上传后立即轮询 `reloadJobId`
- `success` 后刷新该作者 documents
- `failed` 时展示 `errorMessage`

## Segment
### 页面目标
- 三层结构浏览: `author -> document -> chapter`
- 查看章节下段落
- 删除章节/段落（软删除）

### 接口链路
1. `GET /authors/{authorId}/documents/{documentId}/chapters`
2. `GET /authors/{authorId}/documents/{documentId}/chapters/{chapterId}/segments`
3. `DELETE /authors/{authorId}/documents/{documentId}/chapters/{chapterId}`
4. `DELETE /authors/{authorId}/documents/{documentId}/segments/{segmentId}`

### UI行为
- 删除时可 optimistic 更新
- 失败则回滚并重新拉取章节/段落纠偏

## Methodology
### 页面目标
- 触发 `skills` 任务并显示进度
- 展示主/子技能结构与 Markdown 内容

### 接口链路
1. `POST /authors/{authorId}/jobs/skills`（可选 `modelConfig`）
2. 轮询 `GET /jobs/{jobId}`
   - 阶段进度: `35/55/70/85/100`
3. `GET /jobs/{jobId}/outputs`
4. 按需读取:
   - `main_skill_json`
   - `sub_skill_json`
   - `main_skills_md_json`
   - `sub_skills_md_json`
   - `sub_skills_md_zip`
   - `method_analysis_json`

### 说明
- 新任务不再暴露 `main_skill_md`
- `main_skills_md_json` / `sub_skills_md_json` 为 LLM 可直接消费内容

## Analysis
### 页面目标
- 查看作者分析历史
- 创建问答任务并读取 `answer_json`
- 显示 fallback 声明

### 接口链路
1. `GET /authors/{authorId}/jobs?jobType=author_answer&limit=...`
2. `POST /authors/{authorId}/jobs/answer`（`query` + 可选 `modelConfig`）
3. 轮询 `GET /jobs/{jobId}`
4. `GET /jobs/{jobId}/outputs/answer_json`

### `answer_json`关键字段
- `selectedSkillIndex`
- `selectedSectionId`
- `selectedMainSkillName`
- `selectedSubSkillNames`
- `selectionMode`
- `selectionWarning`
- `answer.{title,topic,summary,markdown}`

## 任务与错误处理
- 任务终态: `success/failed/canceled`
- 错误码映射:
  - `UNAUTHORIZED` -> 鉴权失败
  - `NOT_FOUND` -> 资源不存在
  - `TASK_CONFLICT` -> 状态冲突（不可取消/不可重试）
  - `INVALID_ARGUMENT` -> 参数错误
  - `INTERNAL_ERROR` -> 服务异常

## 轮询建议
- 统一轮询器:
  - 间隔 `1000ms`
  - 超时 `180s`
  - 终态即停止
- 如果 `failed/canceled`，展示 `errorMessage`
- `outputsReady` 仅表示公开输出存在；`document_reload` 成功时可能仍为 `false`

## 已知限制
- 当前没有全局“所有运行中任务”接口
- 前端需按作者维度调用 `GET /authors/{authorId}/jobs` 或维护本地关注 `jobId` 列表轮询
