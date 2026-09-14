# EconomistAgent 使用说明

`EconomistAgent` 是一个轻量全栈 Demo：前端使用 React + Vite，后端使用 FastAPI，运行数据保存在本机 SQLite 和 `backend/storage/` 中。

## 前置环境

- Python 3.11（可由 `uv` 自动安装）
- `uv`
- Node.js 20+
- npm

首次启动时，脚本会根据 `.env.example` 自动创建前后端 `.env`，并在缺少 `frontend/node_modules/` 时执行 `npm ci`。

## 方式一：个人开发与使用

适合本地开发、个人体验和现场演示。前后端都启用热更新，日志直接显示在当前终端；按一次 `Ctrl+C` 会同时停止两个服务。该模式不会创建 PID 文件。

### Linux / macOS

```bash
chmod +x start.sh
./start.sh
```

### Windows

```bat
start.bat
```

启动后访问：

- 前端：http://127.0.0.1:3000
- 后端健康检查：http://127.0.0.1:8000/health

## 方式二：部署上线

适合 Linux/macOS 服务器和当前校园网展示环境。脚本构建前端并把前后端放到后台运行；关闭终端或断开 SSH 后服务仍会继续。

```bash
chmod +x start-deploy.sh stop-deploy.sh
./start-deploy.sh
```

默认访问地址：

- 本机前端：http://127.0.0.1:8081
- 校园网前端：http://202.120.22.16:18181
- 本机后端健康检查：http://127.0.0.1:8000/health

停止部署：

```bash
./stop-deploy.sh
```

部署状态保存在 `.run/`：

```text
.run/
├── backend.pid
├── frontend.pid
└── logs/
    ├── backend.log
    └── frontend.log
```

PID 文件只用于停止对应后台进程，停止后会自动删除；整个 `.run/` 已被 Git 忽略。

### 自定义部署地址

部署入口支持以下环境变量：

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `DEPLOY_FRONTEND_HOST` | `0.0.0.0` | 前端监听地址 |
| `DEPLOY_FRONTEND_PORT` | `8081` | 前端监听端口 |
| `DEPLOY_BACKEND_HOST` | `127.0.0.1` | 后端监听地址 |
| `DEPLOY_BACKEND_PORT` | `8000` | 后端监听端口 |
| `DEPLOY_PUBLIC_URL` | `http://202.120.22.16:18181` | 启动完成后显示的公网或校园网地址 |

例如：

```bash
DEPLOY_FRONTEND_PORT=9000 \
DEPLOY_PUBLIC_URL=http://example.test:9000 \
./start-deploy.sh
```

## 环境配置

需要调用模型时，在 `backend/.env` 中配置：

```env
DEEPSEEK_API_KEY=你的密钥
```

服务可以在没有模型密钥的情况下启动，但创建需要模型的任务时会返回 `422 INVALID_ARGUMENT`。

后端接口认证默认为关闭。如果在 `backend/.env` 设置了 `API_KEY`，还需在 `frontend/.env` 设置相同的 `VITE_API_KEY`。

## 后台任务说明

任务由后端进程中的单线程执行器顺序处理，API 会先返回 `job_id`，前端通过轮询显示进度。该设计适合 Demo、个人使用和轻量部署：

- 同一时间只执行一个流水线任务，避免 SQLite 并发写入冲突。
- 停止应用时，尚未开始的任务会停止，并标记为失败以供重试。
- 异常退出遗留的 `queued` 或 `running` 任务会在下次启动时标记为失败，可以在界面或 API 中重试。
- 不适合多实例或大规模并发部署。

## 常见问题

- `Port ... is already in use`：已有程序占用了 3000、8000 或 8081；先停止旧服务再启动。
- 个人模式启动失败：错误会直接显示在终端。
- 部署模式启动失败：查看 `.run/logs/backend.log` 和 `.run/logs/frontend.log`。
- 修改 `backend/.env` 或部署变量后：停止并重新启动对应模式。
