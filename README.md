# EconomistAgent 使用说明（中文）

`EconomistAgent` 是一个完整的全栈应用，包含：

- `frontend`（React + Vite）
- `backend`（FastAPI）
- `worker`（Celery）
- `redis`

默认通过 Docker 启动（稳定模式）。

---

## 一键启动（Quick Start）

前提：已安装 Docker Desktop。

### Windows
运行：
```bash
./start.bat
```
开发环境下运行：
```bash
./start-dev.bat
```
开发模式说明：
- `start-dev.bat` 会本地启动 `backend`、`frontend`
- 它会优先检查本机 `127.0.0.1:6379` 的 Redis
- 如果本机没有 Redis，但 Docker 可用，会自动执行 `docker compose up -d redis`
- 如果 Redis 仍不可用，则会跳过 `worker`，此时部分后台任务会退回到 API 进程内同步执行

### macOS / Linux
运行：
```bash
chmod +x start.sh stop.sh  
./start.sh
```

启动后访问：

- 前端： http://localhost:3000  
- 后端健康检查： http://localhost:8000/health  
- Redis： localhost:6379  

停止服务：

- Windows： ./stop.bat  
- macOS / Linux： ./stop.sh  

### 启动与停止机制说明

- `./start.bat` / `./start.sh` 内部执行的是 `docker compose up -d --build`
- 其中 `-d` 表示 detached（后台运行），所以脚本本身在启动完成后会退出，但 `frontend`、`backend`、`worker`、`redis` 这几个容器会继续在 Docker 中运行
- 因此，启动脚本执行完以后，再在当前终端按 `Ctrl+C`，只能中断当前前台终端操作，不能停止已经在后台运行的 Docker 容器
- 正确的停止方式是执行 `./stop.bat` / `./stop.sh`，它们内部调用 `docker compose down`，会把当前项目相关的容器和网络一起停止

如果你希望使用 `Ctrl+C` 直接停止服务，可以改为手动执行前台模式：

```bash
docker compose up --build
```

这种方式不带 `-d`，日志会持续占用当前终端；按 `Ctrl+C` 时，会直接停止这次 `docker compose` 会话。

---

## 环境配置（Environment）

首次启动时，系统会自动根据 backend/.env.example 生成 backend/.env。

关键变量：

- DEEPSEEK_API_KEY：启动时可为空，但执行 LLM 任务时必须提供  
- API_KEY：后端认证密钥（可选），为空表示不启用认证  

如果设置了 API_KEY，需要在前端同步配置：

- 文件： frontend/.env  
- 添加： VITE_API_KEY=你的API_KEY  

---

## 无 API Key 行为

系统可以在未配置 DEEPSEEK_API_KEY 的情况下正常启动。

但在创建依赖 LLM 的任务（如 skills / answer）时：

- 后端会返回 422 INVALID_ARGUMENT  
- 并附带明确的操作提示  

---

## 示例数据与运行数据

- 示例数据（版本控制）： backend/demo_storage  
- 运行数据（不纳入版本控制）： backend/storage  

首次启动时：

- 系统会自动将 demo 数据初始化到 runtime storage  

---

## 手动 Docker 启动

运行：
```bash
docker compose up -d --build  
docker compose down  
```

---

## 故障排查（Troubleshooting）

- 端口冲突（3000 / 8000 / 6379）  
  - 关闭冲突服务  
  - 或修改 docker-compose.yml 中的端口映射  

- `start-dev.bat` 出现 `Cannot connect to redis://127.0.0.1:6379/0`
  - 含义：开发模式下 `worker` 需要 Redis，但本机 `6379` 没有可用 Redis
  - 处理：启动 Docker Desktop 后重新执行 `./start-dev.bat`，脚本会自动拉起 `redis`

- `vite` 出现 `http proxy error: /api/... ECONNREFUSED 127.0.0.1:8000`
  - 含义：前端已经启动，但后端 API 还没监听 `8000`
  - 处理：查看 `EconomistAgent API` 窗口中的报错；当前脚本会先等待 API 健康，再启动前端，以减少这个问题

- 修改 backend/.env 后，需要重启服务：
```bash
docker compose down  
docker compose up -d --build  
```
