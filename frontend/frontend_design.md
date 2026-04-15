# 经济学家智能代理系统 (Economist Agent) - 前后端对接指南

## 1. 全局技术栈与架构
- **前端框架**：React 18 + Vite
- **样式处理**：Tailwind CSS (响应式布局)
- **动画库**：Framer Motion (用于平滑切换和状态过渡)
- **状态管理**：顶层 `App.tsx` 管理全局 Tab 切换、作者列表及 Segment 历史记录。

---

## 2. 核心模块布局与接口规范

### 2.1 Archive (文献档案库)
**布局说明：**
- **顶部栏**：包含“Create New Author”按钮。
- **主体内容**：按作者分块（`AuthorSection`），展示作者头像、基本信息及手稿列表。
- **手稿列表**：表格形式，包含标题、上传日期、状态（`indexed` / `pending`）及操作（Reload / Remove）。

**后端交互点：**
- `GET /api/authors`：获取所有作者及其手稿列表。
- `POST /api/authors`：创建新作者（包含姓名、流派、头像）。
- `POST /api/manuscripts/upload`：上传书籍/手稿。
    - **关键逻辑**：后端接收后需触发异步任务进行“章节-段落”切分。
- `POST /api/manuscripts/reload`：对应前端的 **Reload** 按钮，重新触发切分逻辑。
- `DELETE /api/manuscripts/:id`：删除手稿。

---

### 2.2 Segment (文献切分管理)
**布局说明：**
- **左侧导航**：三级树状结构（作者 -> 书籍 -> 章节）。支持删除章节。
- **右侧内容**：
    - **头部**：面包屑导航、撤销/反撤销（Undo/Redo）控制。
    - **左栏**：书籍统计数据（总段落数、总字数）。
    - **右栏**：段落流，每个段落卡片支持单独删除。

**后端交互点：**
- `GET /api/segments`：根据 `authorId`, `bookId`, `chapterId` 获取段落 JSON。
- `DELETE /api/chapters/:id`：同步左侧导航栏的删除操作。
- `DELETE /api/segments/:id`：同步右侧段落卡片的删除操作。
- **统一撤销逻辑**：前端目前在内存中维护历史栈。若需持久化，后端需支持批量更新接口。

---

### 2.3 Methodology (学术方法论)
**布局说明：**
- **左侧导航**：作者列表选择。
- **右侧内容**：
    - **初始态**：若未生成，显示“Generate All Skills”大按钮及占位文本。
    - **生成态**：展示“Main Skills”和“Sub Skills”卡片，点击卡片右侧弹出详细的技能分析（包含 Summary, When to Use, Execution Skeleton 等）。

**后端交互点：**
- `GET /api/methodology/:authorId`：获取该作者已生成的技能 JSON。
- `POST /api/methodology/generate`：**核心接口**。
    - **输入**：`authorId`。
    - **逻辑**：后端读取该作者所有段落 -> 调用 LLM 提取方法论 -> 存入数据库。
    - **返回**：符合前端定义的 Skills JSON 结构。

---

### 2.4 Analysis (智能分析/提问)
**布局说明：**
- **左侧导航**：历史分析文章列表。
- **右侧内容**：
    - **提问页**：选择作者（Persona）、输入研究课题、点击“Generate Article”。
    - **结果页**：精美的学术论文排版，包含标题、作者、日期、正文（支持多级标题和首字下沉）。

**后端交互点：**
- `GET /api/analysis/history/:authorId`：获取历史记录。
- `POST /api/analysis/query`：**核心接口**。
    - **输入**：`authorId`, `topic`, `modelConfig` (来自设置)。
    - **逻辑**：RAG 流程（检索相关段落 + 结合方法论 Skills） -> 调用 LLM 生成文章 JSON。
    - **返回**：包含 `title`, `content` (数组形式，区分 `heading` 和 `paragraph`) 的 JSON。

---

## 3. 全局设置 (Settings) 统一规范

**设置项内容：**
- **语言**：`zh-CN` / `en-US`。
- **模型配置**（分为 Skill 生成和 Analysis 引擎）：
    - `Provider`：OpenAI, Google, Anthropic, DeepSeek。
    - `Model Name`：如 `gpt-4o`, `claude-3-5-sonnet`。
    - `API Key`：前端加密存储/隐藏显示。
    - `API Base URL`：支持中转接口。

**统一要求：**
- 前端在发起 `generate` 或 `query` 请求时，应将这些配置项封装在 `config` 对象中发送给后端。
- 后端需具备动态调用不同 Provider SDK 的能力。

---

## 4. 统一数据实体 (Data Models)

### Author (作者)
```json
{
  "id": "string",
  "name": "string",
  "school": "string",
  "avatarUrl": "string",
  "manuscriptsCount": "number"
}
```

### Skill Detail (方法论详情)
```json
{
  "title": "string",
  "summary": "string",
  "whenToUse": "string",
  "methodProgram": "string",
  "executionSkeleton": ["string"],
  "patternFlow": "string"
}
```

### Analysis Article (分析文章)
```json
{
  "title": "string",
  "author": "string",
  "topic": "string",
  "date": "string",
  "content": [
    { "type": "heading", "text": "string" },
    { "type": "paragraph", "text": "string" }
  ]
}
```
