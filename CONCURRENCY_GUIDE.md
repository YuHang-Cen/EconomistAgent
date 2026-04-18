# Celery/Redis 并发架构分析

## 📊 当前架构概览

```
┌─────────────┐
│   Frontend  │ (React/Vite)
│ @ port 3000 │
└──────┬──────┘
       │轮询 GET /jobs/{jobId}
       ▼
┌─────────────────────┐
│   Backend API       │ (FastAPI @ port 8000)
│   - 创建任务        │ POST /authors/{id}/jobs/skills
│   - 轮询状态        │ GET /jobs/{jobId}
│   - 读取产物        │ GET /jobs/{jobId}/outputs
└──────┬──────────────┘
       │异步分发
       ▼
┌─────────────────────┐      ┌──────────────┐
│   Celery Worker     │◄────►│    Redis     │
│ (1+ 并发线程)       │      │  (消息队列)  │
└─────────────────────┘      └──────────────┘
       │
       ▼
┌─────────────────────┐
│   SQLite Database   │
│   (任务状态存储)    │
└─────────────────────┘
```

---

## 🔄 任务处理流程

### 1️⃣ **任务创建（同步）**
```python
# 前端调用
POST /authors/{author_id}/jobs/skills

# 后端处理
1. 创建 PipelineJob 记录（status=QUEUED）
2. 保存到数据库
3. 通过 Celery 异步分发任务：
   stage_runners.run_author_skills_pipeline.delay(job_id)
4. 立即返回任务信息给前端
```

**耗时**: ~10-50ms（数据库写入）

### 2️⃣ **任务分发（异步）**
```python
# Redis 消息队列中的任务
{
    "jobId": "uuid-xxx",
    "jobType": "AUTHOR_SKILLS",  # 长任务（LLM 调用）
    "status": "QUEUED",
    "task_name": "pipeline.author_skills"
}

{
    "jobId": "uuid-yyy",
    "jobType": "AUTHOR_ANSWER",   # 中等任务
    "status": "QUEUED",
    "task_name": "pipeline.author_answer"
}

{
    "jobId": "uuid-zzz",
    "jobType": "AUTHOR_ANSWER",   # 简单任务（增加 author）
    "status": "QUEUED",
    "task_name": "pipeline.author_answer"
}
```

### 3️⃣ **Worker 并发处理**
```
时间轴：

t=0ms   ┌─────────────────────────────────────────┐
        │ Worker Thread Pool (默认 4-8 线程)      │
        └─────────────────────────────────────────┘

t=10ms  任务 A (LLM Skills): 15 秒
        │◄─────────────────────────────────►│ (线程 1)
        
        任务 B (简单 Add Author): 100ms
        ├►│ (线程 2)
        
        任务 C (LLM Answer): 10 秒
        │      ├►│ (线程 3)

        任务 D (简单查询): 50ms
        │      ├►│ (线程 4)

t=110ms 任务 B 完成 ✓ (线程 2 释放，可接收新任务)
        任务 D 完成 ✓ (线程 4 释放)

t=10.1s 任务 C 完成 ✓ (线程 3 释放)

t=15.0s 任务 A 完成 ✓ (线程 1 释放)
```

---

## ✅ 并发能力

### **多 Worker 支持**

#### 启动单个 Worker（当前配置）
```bash
# Windows 默认配置
uv run worker
# 等价于: celery -A app.infra.queue:celery_app worker --pool=threads

# 实际上是：
# - Pool type: threads (Windows 友好)
# - Concurrency: 4 (默认 CPU 核心数)
```

#### 启动多个 Worker（生产推荐）
```bash
# 终端 1
export CELERY_WORKER_CONCURRENCY=4
uv run worker

# 终端 2
export CELERY_WORKER_CONCURRENCY=4
uv run worker

# 结果：2 个 worker，每个 4 个线程 = 总共 8 个并发任务
```

#### 配置方案对比

| 配置 | Pool | Concurrency | 场景 | 并发能力 |
|------|------|------------|------|---------|
| **开发默认** | threads | 4 | 本地开发 | ⭐⭐⭐ |
| **生产单工** | threads | 8 | 中等负载 | ⭐⭐⭐⭐ |
| **生产多工** | threads | 4×2 worker | 高负载 | ⭐⭐⭐⭐⭐ |
| **超高负载** | threads | 4×4 worker | 超大规模 | ⭐⭐⭐⭐⭐⭐ |

---

## 🎯 场景分析：长任务 + 简单任务

### **场景：Skills 分析 + 创建 Author**

```
时间轴（秒）
┌───────────────────────────────────────┐
│ 时刻   │ 队列                │ 线程状态  │
├────────┼──────────────────┼──────────┤
│ 0.0s   │ [Skills(15s),    │ T1:运行  │
│        │  Add_Author(1s)] │ T2:空闲  │
├────────┼──────────────────┼──────────┤
│ 0.01s  │ [Add_Author(1s)] │ T1:Skills│
│        │                  │ T2:Add   │
├────────┼──────────────────┼──────────┤
│ 1.01s  │ []               │ T1:Skills│
│        │                  │ T2:✓完成 │
│        │                  │ T2:空闲  │
├────────┼──────────────────┼──────────┤
│15.0s   │ []               │ T1:✓完成 │
└───────────────────────────────────────┘
```

✅ **结论**：
- Add_Author 任务 **不会被阻塞**
- 简单任务会在另一个线程立即执行
- 前端轮询会立即获得 Add_Author 的完成状态

---

## 🖥️ 前端显示中的并发体现

### **前端轮询逻辑**

```typescript
// 伪代码：前端如何获取任务状态
async function pollJobStatus(jobId: string) {
  const response = await fetch(`/jobs/${jobId}`);
  return {
    jobId: "uuid-xxx",
    status: "RUNNING",      // QUEUED | RUNNING | COMPLETED | FAILED
    currentStage: "ANALYZE",
    progress: 45,            // 进度百分比
    outputsReady: false
  };
}

// 轮询间隔（通常 500-2000ms）
setInterval(() => pollJobStatus(jobId), 1000);
```

### **不会出现阻塞的原因**

1. **API 层是同步的**：
   ```python
   @router.get("/jobs/{job_id}")
   def get_job(job_id: str):
       # 这只是数据库查询，不等待任务完成
       job = session.get(PipelineJob, job_id)
       return _serialize_job(job)  # 毫秒级返回
   ```

2. **任务执行在后台 Worker 中**：
   - FastAPI 不阻塞等待 Worker 完成
   - 只读取数据库中的最新状态

3. **前端并发轮询**：
   ```javascript
   // 可同时轮询多个任务
   Promise.all([
     pollJobStatus(jobId1),  // Skills 分析
     pollJobStatus(jobId2),  // Add Author
     pollJobStatus(jobId3)   // Answer 查询
   ]);
   ```

---

## 📈 当前默认配置分析

### **Windows 默认启动**

```bash
$ uv run worker
# 实际执行的命令：
# celery -A app.infra.queue:celery_app worker --pool=threads

# 配置详情：
{
  "pool": "threads",              # Windows 友好（避免 fork 问题）
  "concurrency": 4,               # 通常等于 CPU 核心数
  "broker": "redis://127.0.0.1:6379/0",
  "backend": "redis://127.0.0.1:6379/0",
  "serializer": "json"
}
```

### **验证当前配置**

```python
# backend/app/cli.py 中的逻辑
def _build_worker_options():
    # Windows 上自动选择 threads pool
    if sys.platform.startswith("win"):
        pool = "threads"  # ✅ 你的系统
    else:
        pool = ""  # Unix 使用默认（通常是 prefork）
    
    # 支持环境变量覆盖
    if os.environ.get("CELERY_WORKER_POOL"):
        pool = os.environ["CELERY_WORKER_POOL"]
    
    if os.environ.get("CELERY_WORKER_CONCURRENCY"):
        concurrency = os.environ["CELERY_WORKER_CONCURRENCY"]
```

---

## 🚀 优化建议

### **方案 1：增加单个 Worker 的并发度**

```bash
# 当前（4 个并发）
uv run worker

# 优化（8 个并发）
set CELERY_WORKER_CONCURRENCY=8
uv run worker
```

**何时用**：
- 中等负载（CPU 密集不多，I/O 为主）
- 避免过多线程上下文切换

### **方案 2：启动多个 Worker（生产推荐）**

在 VS Code Tasks 中添加多个 Worker：

```json
{
  "label": "后端: Celery Worker 1",
  "command": "cmd",
  "args": ["/c", "set CELERY_WORKER_CONCURRENCY=4 && uv run worker"],
  "isBackground": true
},
{
  "label": "后端: Celery Worker 2",
  "command": "cmd",
  "args": ["/c", "set CELERY_WORKER_CONCURRENCY=4 && uv run worker"],
  "isBackground": true
}
```

**何时用**：
- 高并发场景（10+ 同时任务）
- 长任务较多，需要更多隔离

### **方案 3：优化任务队列优先级**

```python
# 在 job_service.py 中修改分发逻辑
def _dispatch_job(job_id: str, job_type: str) -> None:
    from app.services import stage_runners

    # 简单任务提高优先级
    priority_map = {
        JobType.DOCUMENT_RELOAD: 9,  # 高优先级
        JobType.AUTHOR_SKILLS: 5,    # 普通
        JobType.AUTHOR_ANSWER: 7,    # 中等
    }
    
    if job_type == JobType.DOCUMENT_RELOAD.value:
        # priority 越高，越早执行
        stage_runners.run_document_reload_pipeline.apply_async(
            (job_id,),
            priority=priority_map[JobType.DOCUMENT_RELOAD]
        )
```

---

## 📊 性能指标参考

| 指标 | 数值 | 说明 |
|------|------|------|
| API 响应时间（创建任务） | < 50ms | 只是数据库写入 |
| 轮询延迟 | < 100ms | 只是数据库查询 |
| 简单任务执行时间 | 100ms | Add Author |
| LLM Skills 分析时间 | 10-30s | 取决于 API |
| 默认并发数 | 4 | CPU 核心数 |
| 最大推荐并发 | CPU × 4 | 线程池最优值 |

---

## ✨ 总结

### **你的项目支持多 Worker 吗？**
✅ **完全支持**

### **长任务会阻塞简单任务吗？**
❌ **不会**（使用不同的线程）

### **前端会出现阻塞吗？**
❌ **不会**（API 只读数据库）

### **当前默认并发度**
⭐ **4 个同时任务**（可优化到 8+ 个）

### **推荐生产配置**
🚀 **2-4 个 Worker，每个 4-8 并发线程**
