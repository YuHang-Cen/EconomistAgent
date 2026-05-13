# Backend V3 前端对接手册（当前生效版）

> 本文档是前端联调的唯一参考，内容以当前 `backend/app` 实现与集成测试结果为准。  
> 目标：前端无需阅读后端代码即可完成作者管理、文档导入、任务轮询、产物读取与错误处理。

---

## 1. 快速接入

### 1.1 Base URL
- 本地开发：`http://127.0.0.1:8000`
- API 前缀：`/api`
- 健康检查：`GET /health`（不带 `/api`）

### 1.2 鉴权
- 请求头：`X-API-Key: <key>`
- 当后端 `api_key` 配置为空时，可不传；配置后必须传且匹配。

### 1.3 统一响应 Envelope
所有 API 返回统一结构：

```json
{
  "success": true,
  "data": {},
  "error": null,
  "requestId": "uuid",
  "timestamp": "2026-04-18T12:00:00+00:00"
}
```

失败示例：

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "NOT_FOUND",
    "message": "author not found",
    "details": null
  },
  "requestId": "uuid",
  "timestamp": "2026-04-18T12:00:00+00:00"
}
```

### 1.4 错误码映射
- `UNAUTHORIZED`：401
- `NOT_FOUND`：404
- `TASK_CONFLICT`：409
- `INVALID_ARGUMENT`：422
- `INTERNAL_ERROR`：500

---

## 2. 前端可见资源模型

### 2.1 Author
- `authorId`
- `authorName`
- `school`
- `avatarUrl`
- `manuscriptsCount`

### 2.2 Document
- `documentId`
- `authorId`
- `bookTitle`
- `pdfUri`
- `status`（当前常见值：`processing | active | failed`）

### 2.3 Job（轮询核心）
- `jobId`
- `authorId`
- `documentId`（仅 document_reload 有值）
- `jobType`：`author_skills | document_reload | author_answer`
- `status`：`queued | running | success | failed | canceled`
- `currentStage`：`extract | segment_sync | analyze | main_skill | sub_skill | render | select_skills | answer`
- `progress`：0~100
- `errorMessage`
- `finishedAt`
- `retryable`
- `outputsReady`

### 2.4 Chapter / Segment
- Chapter：`chapterId/documentId/chapterTitle/orderIndex`
- Segment：`segmentId/documentId/chapterId/chunkId/content/orderIndex`
- 查询默认只返回未软删除数据（`is_deleted=false`）

---

## 3. API 契约（按前端调用链）

## 3.1 作者与文档

### 创建作者
- `POST /api/authors`
- body:

```json
{
  "authorName": "Keynes",
  "school": "Cambridge",
  "avatarUrl": "https://..."
}
```

### 作者列表
- `GET /api/authors`

### 上传文档（自动触发 reload）
- `POST /api/authors/{author_id}/documents`
- body:

```json
{
  "bookTitle": "General Theory",
  "pdfUri": "D:/books/general-theory.pdf"
}
```

- 返回：

```json
{
  "documentId": "xxx",
  "reloadJobId": "yyy"
}
```

### 文档列表
- `GET /api/authors/{author_id}/documents`

### 手动重载单文档
- `POST /api/authors/{author_id}/documents/{document_id}/reload`
- 返回：`{ "reloadJobId": "..." }`

### 删除作者（硬删除）
- `DELETE /api/authors/{author_id}`
- 成功：`{ "deleted": true }`
- 行为：
  - 作者、文档、章节、段落、技能快照硬删除
  - 作者目录 `storage/authors/{author_id}` best-effort 清理
  - 该作者 `queued/running` 任务改为 `canceled`，`errorMessage="author deleted"`
  - 历史任务记录保留，但其 outputs 可能因目录被删而 404

## 3.2 章节与段落

- `GET /api/authors/{author_id}/documents/{document_id}/chapters`
- `GET /api/authors/{author_id}/documents/{document_id}/chapters/{chapter_id}/segments`
- `DELETE /api/authors/{author_id}/documents/{document_id}/chapters/{chapter_id}`（软删除章节及其段落）
- `DELETE /api/authors/{author_id}/documents/{document_id}/segments/{segment_id}`（软删除单段落）

删除成功统一返回：`{ "deleted": true }`

## 3.3 任务与产物

### 创建任务
- `POST /api/authors/{author_id}/jobs/skills`
- `POST /api/authors/{author_id}/jobs/answer`（body: `{ "query": "..." }`）

### 轮询任务
- `GET /api/jobs/{job_id}`

### 产物列表与读取
- `GET /api/jobs/{job_id}/outputs` → `[{ "type": "main_skill_json" }, ...]`
- `GET /api/jobs/{job_id}/outputs/{output_type}`
  - 非法 `output_type`：422 (`INVALID_ARGUMENT`)
  - 该任务无此产物：404 (`NOT_FOUND`)

### 重试与取消
- `POST /api/jobs/{job_id}/retry`
  - 仅 `failed/canceled` 可重试
  - 重置为 `queued`，并从任务类型默认起始阶段重跑
- `POST /api/jobs/{job_id}/cancel`
  - 仅 `queued/running` 可取消
  - 已终态取消会返回 409 (`TASK_CONFLICT`)

---

## 4. 三类任务执行规范（前端重点）

## 4.1 `document_reload`

### 流程
- `extract`（progress=60）→ `segment_sync` → success(100)

### 严格失败策略
以下情况直接 `failed`，`errorMessage` 可见：
- 路径不存在
- 不是 `.pdf`
- PDF 解析不可用/异常
- 无可提取有效段落

### 输出说明
- 内部会写 `document_reload_report`，但该类型不在对外 `OutputType` 枚举中  
- 结果：多数情况下 `outputsReady=false`（这是当前实现的正常表现）

## 4.2 `author_skills`

### 增量生成策略（当前实现）
- 每次从“当前可用章节 - 作者全历史已生成章节”中随机抽样生成
- 默认每次章节数：`skills_batch_size=2`
- `main_skill` 存储默认不限量：`skills_max_main_skills=0`
- 检索阶段默认先规则召回 `skills_select_recall_limit=20`，再让 LLM 在召回集合中选择

### 无剩余章节
- 若无剩余可生成章节：任务直接 success，复用 latest snapshot，不新建 snapshot，不再调用 LLM
- 若无剩余但也无 latest snapshot：任务 failed（数据不一致保护）

### 阶段进度
- `analyze=35`
- `main_skill=55`
- `sub_skill=70`
- `render=85`
- 完成 `=100`

## 4.3 `author_answer`

### 前置依赖
- 必须有该作者 latest snapshot（含 `main_skill_json/sub_skill_json`）

### 选择与回答链路
- `select_skills`：LLM 选择 `skill_indices` 数组，并映射为 `selected_section_ids`
- `answer`：按 `selected_section_ids` 顺序组装多段上下文并生成一份 JSON 回答

### 上下文优先级
1. 优先 `main_skills_md_json + sub_skills_md_json`（markdown 全文）
2. 缺失时回退 `main_skill_json + sub_skill_json` 摘要

### Fallback 可见性
- 选择阶段 fallback 通过返回字段暴露：`selection_mode/selection_warning`
- 任务成功不等于 LLM 一定成功：本地兜底仍可能输出 `answer`（结构始终保持 JSON）

---

## 5. 输出产物矩阵（任务 × output_type）

## 5.1 `author_skills`
- `method_analysis_json`
- `main_skill_json`
- `sub_skill_json`
- `main_skills_md_json`
- `sub_skills_md_json`
- `sub_skills_md_zip`

> 兼容说明：新任务不再写出 `main_skill_md`，但历史任务若已存在，仍可能可读。

## 5.2 `author_answer`
- `answer_json`

`answer_json` 关键字段（当前）：
- `query`
- `selected_skill_indices`
- `selected_section_ids`
- `selected_skill_index`
- `selected_section_id`
- `selected_main_skill_names`
- `selected_main_skill_name`
- `selected_sub_skill_names`
- `selection_mode`
- `selection_warning`
- `answer`（`title/topic/summary/markdown`）

## 5.3 `document_reload`
- 当前无公开 output_type（因此常见 `outputsReady=false`）

## 5.4 ZIP 读取语义
`GET /outputs/sub_skills_md_zip` 返回：

```json
{
  "type": "sub_skills_md_zip",
  "content": {
    "uri": "storage/...",
    "files": ["main_skill_001_xxx.md", "..."]
  }
}
```

即：返回 zip 文件清单，不直接返回解压后的 markdown 文本。

---

## 6. 前端 JS/TS 对接示例

```ts
type ApiOk<T> = {
  success: true;
  data: T;
  error: null;
  requestId: string;
  timestamp: string;
};

type ApiErr = {
  success: false;
  data: null;
  error: { code: string; message: string; details?: unknown };
  requestId: string;
  timestamp: string;
};

type ApiResp<T> = ApiOk<T> | ApiErr;

const BASE = "http://127.0.0.1:8000/api";
const API_KEY = "your-api-key";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
      ...(init?.headers || {}),
    },
  });
  const payload = (await resp.json()) as ApiResp<T>;
  if (!payload.success) throw new Error(`${payload.error.code}: ${payload.error.message}`);
  return payload.data;
}

type Job = {
  jobId: string;
  status: "queued" | "running" | "success" | "failed" | "canceled";
  currentStage: string | null;
  progress: number;
  errorMessage: string | null;
  retryable: boolean;
  outputsReady: boolean;
};

async function pollJob(jobId: string, timeoutMs = 120_000, intervalMs = 1000): Promise<Job> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const job = await api<Job>(`/jobs/${jobId}`);
    if (job.status === "success") return job;
    if (job.status === "failed" || job.status === "canceled") {
      throw new Error(`job ${job.status}: ${job.errorMessage ?? "unknown error"}`);
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("job polling timeout");
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return !!v && typeof v === "object";
}
function isRecordArray(v: unknown): v is Record<string, unknown>[] {
  return Array.isArray(v) && v.every(isRecord);
}

async function fullFlow() {
  // 1) 创建作者
  const author = await api<{ authorId: string }>("/authors", {
    method: "POST",
    body: JSON.stringify({
      authorName: "Keynes",
      school: "Cambridge",
      avatarUrl: "",
    }),
  });

  // 2) 上传文档（自动触发 reload）
  const upload = await api<{ documentId: string; reloadJobId: string }>(
    `/authors/${author.authorId}/documents`,
    {
      method: "POST",
      body: JSON.stringify({
        bookTitle: "General Theory",
        pdfUri: "D:/books/general-theory.pdf",
      }),
    }
  );

  // 3) 轮询 reload
  await pollJob(upload.reloadJobId);

  // 4) 触发 skills
  const skills = await api<{ jobId: string }>(`/authors/${author.authorId}/jobs/skills`, {
    method: "POST",
  });
  await pollJob(skills.jobId);

  // 5) 读取 skills outputs
  const outputs = await api<Array<{ type: string }>>(`/jobs/${skills.jobId}/outputs`);
  if (outputs.some((o) => o.type === "main_skills_md_json")) {
    const out = await api<{ type: string; content: unknown }>(
      `/jobs/${skills.jobId}/outputs/main_skills_md_json`
    );
    if (!isRecordArray(out.content)) throw new Error("main_skills_md_json content invalid");
  }

  // 6) 触发 answer
  const answerJob = await api<{ jobId: string }>(`/authors/${author.authorId}/jobs/answer`, {
    method: "POST",
    body: JSON.stringify({ query: "分析凯恩斯政策机制" }),
  });
  await pollJob(answerJob.jobId);

  // 7) 读取 answer_json
  const answerOut = await api<{ type: "answer_json"; content: unknown }>(
    `/jobs/${answerJob.jobId}/outputs/answer_json`
  );
  if (!isRecord(answerOut.content)) throw new Error("answer_json invalid");
  return answerOut.content;
}
```

---

## 7. 兼容迁移（旧前端 -> 当前后端）

## 7.1 产物迁移
- 旧：`main_skill_md`
- 新：`main_skills_md_json`（按主技能拆分，含 markdown 全文）

- 旧：只消费 `sub_skills_md_zip`
- 新：优先 `sub_skills_md_json`（可直接按 section/filter 喂 LLM），zip 保留

## 7.2 回答字段迁移
- 旧思路：`selected_main_skill_id` / `selected_sub_skill_names`（按 main_skill_id）
- 当前：`selected_skill_indices -> selected_section_ids`
- `answer_json` 新增：
  - `selected_skill_indices`
  - `selected_section_ids`
  - `selected_main_skill_names`
  - `selected_main_skill_name`
  - `selected_sub_skill_names`（数组）

## 7.3 `outputsReady` 认知修正
- `outputsReady` 只看“公开 output_type”是否存在
- 因 `document_reload_report` 非公开类型，`document_reload` 即使成功也可能 `outputsReady=false`

## 7.4 任务可见性限制
- 当前无 `GET /api/jobs/running` 之类聚合接口
- 前端需自行维护关注的 `jobId` 列表并逐个轮询

---

## 8. 联调建议（前端）

- 统一封装 `api()` 与 `pollJob()`，避免每个页面重复状态机。
- 页面展示优先依据 `status/currentStage/progress/errorMessage`，不要只看 `outputsReady`。
- 对 422/404/409 分支做显式 UI 提示（尤其 `invalid output type`、`output not found`）。
- `author_answer` 若看到 `selection_mode="fallback_rule"`，建议在 UI 给出“已使用兜底策略”提示。

---

## 9. 说明

- 本文档仅描述当前行为，不追溯旧版设计目标。
- 若后端新增公开 output_type、任务聚合查询或 SSE 推送，需同步更新本手册。
