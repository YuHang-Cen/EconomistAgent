# 开发环境启动指南

## 📋 前置要求

- ✅ Python 3.11+
- ✅ Node.js (npm)
- ✅ Redis 服务运行中
- ✅ uv 包管理器

### 检查 Redis 状态

```bash
# 检查 Redis 是否运行
redis-cli ping
# 应该返回：PONG

# 如果没有运行，启动 Redis（Windows）
redis-server

# 或使用 WSL/Docker
docker run -d -p 6379:6379 redis:latest
```

---

## 🚀 启动方案

### **方案 A：Windows 批处理脚本（推荐新手）**

双击运行：[start-dev.bat](start-dev.bat)

```bash
# 或在命令行中
start-dev.bat               # 交互式菜单
start-dev.bat single        # 启动单工 (4 并发)
start-dev.bat multi         # 启动多工 (16 并发)
```

**特点**：
- ✅ 一键启动所有服务
- ✅ 自动检查依赖
- ✅ 在新终端中显示实时日志
- ✅ 支持单工/多工模式选择

---

### **方案 B：VS Code Tasks（推荐开发者）**

1. 在 VS Code 中按 `Ctrl+Shift+P`
2. 搜索并选择 **"Run Task"**
3. 选择启动任务：

```
🚀 启动全栈 (单工 4并发)      ← 开发推荐
🚀 启动全栈 (多工 8并发)      ← 高负载测试
```

**特点**：
- ✅ 集成在 VS Code 中，直观方便
- ✅ 所有输出在同一个任务面板
- ✅ 支持快捷键启动
- ✅ 便于调试

**快捷配置**：在 `.vscode/settings.json` 中添加快捷键

```json
{
  "key": "ctrl+alt+d",
  "command": "workbench.action.tasks.runTask",
  "args": "🚀 启动全栈 (单工 4并发)"
}
```

---

### **方案 C：手动在终端中启动（完全控制）**

#### 单工模式（4 并发）

**终端 1：后端 API**
```bash
cd backend
uv run dev
# 输出示例：
# Uvicorn running on http://127.0.0.1:8000
```

**终端 2：Celery Worker**
```bash
cd backend
set CELERY_WORKER_CONCURRENCY=4
uv run worker
# 输出示例：
# ---------- celery@DESKTOP-XXXX v5.x.x -----------
# ---- **** ----- 
# --- ***---- **** ----- 
# [2026-04-18 10:30:15,123: INFO/MainProcess] Connected to redis://127.0.0.1:6379/0
# [2026-04-18 10:30:15,456: INFO/MainProcess] mingle: searching for executable celery script in /venv/Scripts
# [2026-04-18 10:30:16,789: INFO/MainProcess] worker ready.
```

**终端 3：前端 UI**
```bash
cd frontend
npm run dev
# 输出示例：
# VITE v6.2.0  ready in 1234 ms
#
# ➜  Local:   http://localhost:3000/
```

#### 多工模式（16 并发）

在上面的基础上，添加第 4 个终端：

**终端 4：第二个 Worker**
```bash
cd backend
set CELERY_WORKER_CONCURRENCY=8
uv run worker
```

---

## 🔍 验证启动成功

### 1. 检查所有服务都在运行

```bash
# 后端 API
curl http://localhost:8000/docs  # 应该返回 Swagger UI

# Redis
redis-cli ping  # 应该返回 PONG

# Worker（通过日志确认）
# 应该看到：[INFO/MainProcess] worker ready.
```

### 2. 测试任务创建

```bash
# 创建一个作者
curl -X POST http://localhost:8000/authors \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test" \
  -d '{"name": "Adam Smith"}'

# 应该返回：
# {
#   "authorId": "uuid-xxx",
#   "name": "Adam Smith"
# }

# 创建一个技能生成任务
curl -X POST http://localhost:8000/authors/{authorId}/jobs/skills \
  -H "X-API-Key: test"

# 应该返回：
# {
#   "jobId": "uuid-yyy",
#   "status": "QUEUED",
#   "currentStage": "ANALYZE"
# }

# 轮询任务状态
curl http://localhost:8000/jobs/{jobId} \
  -H "X-API-Key: test"

# 应该看到状态更新：
# {
#   "jobId": "uuid-yyy",
#   "status": "RUNNING",
#   "currentStage": "ANALYZE",
#   "progress": 45
# }
```

---

## 📊 选择启动模式

### **单工模式 (4 并发) - 推荐开发**

```
场景: 本地开发、单人调试
特点:
  - 资源占用少（内存 < 500MB）
  - 启动速度快
  - CPU 使用率低
  - 适合处理 1-5 个同时任务

启动:
  start-dev.bat single
  或 Ctrl+Shift+P > Run Task > "🚀 启动全栈 (单工 4并发)"
```

### **多工模式 (16 并发) - 推荐高负载测试**

```
场景: 性能测试、模拟多用户
特点:
  - 资源占用中等（内存 1-2GB）
  - 启动速度较快
  - CPU 使用率适中
  - 适合处理 10+ 个同时任务

启动:
  start-dev.bat multi
  或 Ctrl+Shift+P > Run Task > "🚀 启动全栈 (多工 8并发)"
```

---

## 🛠️ 常见问题

### Q1: Redis 连接失败

**错误信息**：
```
redis.exceptions.ConnectionError: Error 111 connecting to 127.0.0.1:6379. Connection refused.
```

**解决方案**：
```bash
# 启动 Redis
redis-server

# 验证连接
redis-cli ping  # 应该返回 PONG
```

### Q2: Worker 一直显示 "worker ready" 但没有执行任务

**原因**：任务没有被分发到队列

**调试**：
```bash
# 查看 Redis 中的任务
redis-cli
> LLEN celery  # 应该有待处理任务数
> KEYS "*"     # 查看所有键

# 或检查后端日志
# 应该看到：stage_runners.run_author_skills_pipeline.delay(job_id)
```

### Q3: 长任务阻塞了简单任务

**这应该不会发生**，但如果确实发生：

```bash
# 1. 增加并发数
set CELERY_WORKER_CONCURRENCY=8  # 从 4 增加到 8

# 2. 启动第二个 Worker
start cmd /k "set CELERY_WORKER_CONCURRENCY=8 && uv run worker"

# 3. 添加任务优先级（见 CONCURRENCY_GUIDE.md）
```

### Q4: 前端无法连接后端

**错误信息**：
```
Failed to fetch: http://localhost:8000/...
```

**解决方案**：
```bash
# 1. 确保后端 API 在运行
curl http://localhost:8000/docs

# 2. 检查前端 API 基础 URL 配置（frontend/src/）
# 应该是：http://localhost:8000 或相对路径

# 3. 检查 CORS 设置（backend/app/main.py）
```

---

## 📈 性能监控

### 实时监控 Worker 状态

```bash
# 方案 1：Celery Flower UI（可视化监控）
pip install flower
celery -A app.infra.queue:celery_app flower
# 访问：http://localhost:5555

# 方案 2：Redis Monitor
redis-cli monitor  # 实时显示所有 Redis 命令

# 方案 3：Celery 日志级别
set CELERY_LOGLEVEL=debug
uv run worker
```

### 查看任务队列

```bash
redis-cli
> LRANGE celery 0 -1        # 查看所有待处理任务
> HGETALL celery-task-meta: # 查看任务元数据
> KEYS "*"                  # 查看所有键
> INFO                      # 查看 Redis 统计信息
```

---

## 🔧 高级配置

### 增加 Worker 并发度

```bash
# 当前（4 并发）
uv run worker

# 优化（8 并发）
set CELERY_WORKER_CONCURRENCY=8
uv run worker

# 最大（16 并发，需要 >= 8 核 CPU）
set CELERY_WORKER_CONCURRENCY=16
uv run worker
```

### 改变 Worker 池类型

```bash
# 当前（threads - Windows 友好）
uv run worker

# 更改为 solo（单线程，调试用）
set CELERY_WORKER_POOL=solo
uv run worker

# 更改为 prefork（Unix 推荐，Windows 不支持）
set CELERY_WORKER_POOL=prefork
uv run worker
```

---

## 📝 快速参考

| 命令 | 作用 |
|------|------|
| `start-dev.bat single` | 启动单工 |
| `start-dev.bat multi` | 启动多工 |
| `Ctrl+Shift+P` > "Run Task" | VS Code 启动任务 |
| `redis-cli ping` | 检查 Redis |
| `redis-cli monitor` | 监控 Redis 操作 |
| `curl http://localhost:8000/docs` | 打开 API 文档 |
| `curl http://localhost:3000` | 打开前端页面 |

---

## 📚 相关文档

- [并发架构详解](CONCURRENCY_GUIDE.md)
- [Git 工作流](GIT_WORKFLOW.md)
- [项目概览](PRD.md)
