# Git Workflow（前后端一体项目）

## 1. 仓库模型
- 使用 Monorepo：`backend/` 与 `frontend/` 共用一个根仓库。
- 不在子目录单独 `git init`。

## 2. 分支策略
- `main`：稳定分支，可发布状态。
- 功能分支命名建议：
  - `feat/backend-xxx`
  - `feat/frontend-xxx`
  - `feat/fullstack-xxx`
  - `fix/backend-xxx`
  - `fix/frontend-xxx`

## 3. 提交规范（Conventional Commits）
- 格式：`type(scope): summary`
- 示例：
  - `feat(backend): add document_reload job flow`
  - `feat(frontend): wire polling status ui`
  - `fix(fullstack): align answer output schema`
  - `docs(project): update backend design v3`

常用 `type`：
- `feat` 新功能
- `fix` 缺陷修复
- `refactor` 重构（无功能变化）
- `docs` 文档更新
- `chore` 工程维护
- `test` 测试相关

## 4. Pull Request 要求
- 标题包含 scope（backend/frontend/fullstack）。
- 描述至少包含：
  - 变更内容
  - 影响范围（API/UI/DB）
  - 验证方式
  - 风险与回滚点（如有）

## 5. 建议检查项（提交前）
- Backend：测试通过、关键接口可用、迁移脚本可回放。
- Frontend：构建通过、关键页面无报错、接口字段匹配最新后端契约。
- Fullstack 变更：至少一次端到端手动验证（上传/轮询/结果展示）。

## 6. Tag 与发布建议
- 用语义化版本号：`v0.1.0`, `v0.2.0`。
- 发布说明中分两段：
  - Backend changes
  - Frontend changes

