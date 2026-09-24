# DeepResearch 项目学习文档

## 1. 项目概览

这个项目是一个 DeepResearch 多智能体研究助手。用户在前端输入问题后，后端会判断问题适合快速回答还是进入完整研究流程。

如果是简单问题，系统直接生成回答。如果是复杂问题，系统会进入 LangGraph 编排的多智能体链路，依次完成意图识别、任务规划、网页搜索、本地知识库检索、证据裁判、分析、反思补搜和最终报告写作。

当前项目主要由三部分组成：

- 后端 API：负责接收前端请求、启动工作流、返回流式事件。
- 多智能体核心：负责模型调用、LangGraph 编排、节点执行、证据处理和报告生成。
- 前端页面：负责聊天界面、用户输入、SSE 流式响应展示。

## 2. 技术栈

### 后端

- Python
- FastAPI
- Uvicorn
- Pydantic / pydantic-settings
- python-dotenv

### 多智能体与大模型

- LangGraph
- LangChain
- DashScope / 阿里云百炼
- OpenAI-compatible API
- Qwen 模型，例如 `qwen3.7-plus`

### 检索与记忆

- Bocha Web Search
- Milvus
- PostgreSQL
- Redis
- SQLite fallback
- LangGraph Checkpointer

当前快速启动模式下，为了先跑通项目，建议先关闭：

- Milvus
- 长期记忆
- PostgreSQL checkpointer

### 前端

- Vue 3
- TypeScript
- Vite
- SSE / `text/event-stream`

## 3. 推荐学习阶段

## 阶段一：先跑通项目

目标：知道项目如何启动，前后端如何连通。

重点文件：

- `config.json`
- `.env`
- `app/app_main.py`
- `front/agent_front/vite.config.ts`

学习内容：

- `.env` 负责放 API Key、数据库地址等本地配置。
- `config.json` 负责多智能体运行配置，例如模型名、记忆开关、Milvus 开关。
- 后端默认通过 Uvicorn 启动 FastAPI。
- 前端通过 Vite 启动，并把 `/api` 请求代理到后端。

推荐启动命令：

```cmd
cd /d C:\Users\27605\Desktop\项目\deep_research
.\.venv\Scripts\activate.bat
set PYTHONPATH=C:\Users\27605\Desktop\项目\deep_research\app
python -m uvicorn app_main:app --host 0.0.0.0 --port 8002 --reload
```

前端启动：

```cmd
cd /d C:\Users\27605\Desktop\项目\deep_research\front\agent_front
npm run dev
```

访问：

```text
http://localhost:5173/
```

## 阶段二：理解请求入口

目标：看懂用户输入是怎么进入后端的。

重点文件：

- `app/app_main.py`
- `app/backend/router/research_router.py`
- `app/backend/schemas/research.py`
- `app/backend/service/workflow_service.py`

文件作用：

| 文件 | 主要作用 |
| --- | --- |
| `app/app_main.py` | 创建 FastAPI 应用，注册 CORS、健康检查路由和研究路由 |
| `app/backend/router/research_router.py` | 定义 `/api/v1/research/run` 和 `/api/v1/research/stream` 接口 |
| `app/backend/schemas/research.py` | 定义前端请求体和后端响应体结构 |
| `app/backend/service/workflow_service.py` | 初始化多智能体工作流，执行任务，向前端流式返回状态和最终结果 |

学习重点：

- `/run` 是普通一次性返回。
- `/stream` 是流式返回，前端会实时看到阶段进度。
- `WorkflowService` 是后端连接 API 层和多智能体核心的桥梁。

## 阶段三：理解 LangGraph 工作流

目标：看懂多智能体流程是怎么被编排的。

重点文件：

- `app/mult_agents/graph.py`
- `app/mult_agents/state.py`

文件作用：

| 文件 | 主要作用 |
| --- | --- |
| `app/mult_agents/graph.py` | 定义 LangGraph 节点、边、条件路由和整体执行流程 |
| `app/mult_agents/state.py` | 定义工作流共享状态 `ResearchState`，保存 query、plan、evidence、analysis、final 等字段 |

核心流程：

```text
START
  -> intent
  -> direct_answer
  -> END
```

或者：

```text
START
  -> intent
  -> plan
  -> web_search + local_rag
  -> deep_dive
  -> analyze
  -> reflect 或 write
  -> END
```

学习重点：

- `intent` 决定走快速回答还是完整研究。
- `plan` 负责拆解问题。
- `web_search` 负责网页证据。
- `local_rag` 负责本地知识库证据。
- `deep_dive` 负责证据裁判。
- `analyze` 负责形成结论。
- `reflect` 负责证据不足时补搜。
- `write` 负责写最终报告。

## 阶段四：理解 Agent 构建和模型调用

目标：知道每个 Agent 是如何创建、如何绑定模型的。

重点文件：

- `app/mult_agents/main.py`
- `app/mult_agents/prompts.py`

文件作用：

| 文件 | 主要作用 |
| --- | --- |
| `app/mult_agents/main.py` | 加载配置，创建模型，构建 AgentBundle，初始化记忆和 checkpointer |
| `app/mult_agents/prompts.py` | 集中保存每个 Agent 的 system prompt |

学习重点：

- `build_agent()` 负责创建单个 agent。
- `build_agents()` 负责创建完整 AgentBundle。
- `PROMPTS` 里定义了每个 Agent 的角色和输出格式。
- 新模型如 `qwen3.7-plus` 更适合走百炼 OpenAI-compatible API。
- 旧模型可走 `ChatTongyi` / DashScope 接口。

建议重点看：

```text
build_agent
build_agents
AgentBundle
PROMPTS
```

## 阶段五：理解每个节点怎么执行

目标：看懂真正的业务逻辑。

重点文件：

- `app/mult_agents/nodes.py`
- `app/mult_agents/tools.py`

文件作用：

| 文件 | 主要作用 |
| --- | --- |
| `app/mult_agents/nodes.py` | 实现 intent、plan、web_search、local_rag、deep_dive、analyze、reflect、write 等节点逻辑 |
| `app/mult_agents/tools.py` | 封装网页搜索、本地知识库搜索、工具函数和一些模拟工具 |

学习重点：

- `intent_node()`：识别用户问题类型。
- `plan_node()`：生成结构化研究计划。
- `web_search_node()`：调用 Bocha 搜索，整理网页证据。
- `local_rag_node()`：从本地向量库检索证据。
- `deep_dive_node()`：给证据评分、去重、发现冲突。
- `analyze_node()`：生成结论和缺口。
- `reflect_node()`：证据不足时生成补充查询。
- `write_node()`：生成最终 Markdown 报告。

建议从这几个函数开始读：

```text
intent_node
plan_node
web_search_node
analyze_node
write_node
```

## 阶段六：理解记忆系统

目标：知道项目如何保存和读取用户历史。

重点文件：

- `app/mult_agents/memory/manager.py`
- `app/mult_agents/memory/short_term.py`
- `app/mult_agents/memory/long_term.py`
- `app/mult_agents/memory/base.py`
- `app/mult_agents/memory/utils.py`

文件作用：

| 文件 | 主要作用 |
| --- | --- |
| `memory/manager.py` | 统一管理短期记忆、长期记忆、用户画像和任务历史 |
| `memory/short_term.py` | 管理当前对话线程的短期消息 |
| `memory/long_term.py` | 管理语义记忆、任务记忆、SQLite fallback |
| `memory/base.py` | 定义记忆基础数据结构 |
| `memory/utils.py` | 记忆抽取、格式化、用户画像合并等工具 |

学习重点：

- 快速启动阶段可以先关闭 `enable_memory`。
- 真正上线时可以接 PostgreSQL、Redis、Milvus。
- `build_personalized_prompt_context()` 会把记忆注入到 prompt。
- `persist_turn()` 会在每轮对话后保存用户输入和模型回答。

## 阶段七：理解 RAG 和知识库

目标：知道本地知识库如何接入。

重点文件：

- `app/mult_agents/rag/core.py`
- `app/mult_agents/rag/ingest.py`
- `app/mult_agents/rag_core.py`

文件作用：

| 文件 | 主要作用 |
| --- | --- |
| `rag/core.py` | 定义 RAGSystem，连接 Milvus，执行向量检索和文档入库 |
| `rag/ingest.py` | 文档入库脚本，目前需要修复路径和 import |
| `rag_core.py` | 旧版或兼容用 RAG 核心文件 |

学习重点：

- `RAGSystem` 使用 DashScope Embeddings。
- Milvus 用来保存和检索向量。
- 当前项目的 `ingest.py` 有明显本机路径残留，后续需要重构。
- 如果只是先学习主流程，可以暂时跳过 RAG。

## 阶段八：理解前端

目标：看懂页面如何发送问题和展示流式结果。

重点文件：

- `front/agent_front/src/App.vue`
- `front/agent_front/vite.config.ts`
- `front/agent_front/package.json`

文件作用：

| 文件 | 主要作用 |
| --- | --- |
| `src/App.vue` | 前端主页面，包含聊天 UI、输入框、SSE 解析、消息渲染 |
| `vite.config.ts` | Vite 配置，包含后端代理地址 |
| `package.json` | 前端依赖和启动脚本 |

学习重点：

- `runResearch()` 负责发送请求。
- `fetch('/api/v1/research/stream')` 连接后端 SSE 接口。
- 前端会解析 `status`、`phase`、`route`、`final`、`error` 事件。
- `markdownToHtml()` 把后端 Markdown 回答渲染成 HTML。

## 4. 核心文件总览

| 文件 | 学习优先级 | 主要作用 |
| --- | --- | --- |
| `app/app_main.py` | 高 | FastAPI 应用入口 |
| `app/backend/router/research_router.py` | 高 | 后端研究接口 |
| `app/backend/service/workflow_service.py` | 高 | API 层和 LangGraph 工作流的连接器 |
| `app/mult_agents/graph.py` | 最高 | 多智能体工作流编排 |
| `app/mult_agents/state.py` | 高 | 工作流共享状态定义 |
| `app/mult_agents/main.py` | 最高 | 模型、Agent、记忆、checkpointer 初始化 |
| `app/mult_agents/nodes.py` | 最高 | 每个智能体节点的业务逻辑 |
| `app/mult_agents/prompts.py` | 高 | 各 Agent 的提示词 |
| `app/mult_agents/tools.py` | 中 | 搜索、RAG、工具函数 |
| `app/mult_agents/memory/manager.py` | 中 | 记忆系统总入口 |
| `app/mult_agents/rag/core.py` | 中 | Milvus RAG 核心 |
| `front/agent_front/src/App.vue` | 高 | 前端聊天页面 |
| `front/agent_front/vite.config.ts` | 中 | 前端代理配置 |
| `config.json` | 高 | 项目运行配置 |
| `.env` | 高 | 本地密钥和环境变量 |

## 5. 推荐阅读顺序

建议按下面顺序阅读：

```text
1. app/app_main.py
2. app/backend/router/research_router.py
3. app/backend/service/workflow_service.py
4. app/mult_agents/graph.py
5. app/mult_agents/state.py
6. app/mult_agents/main.py
7. app/mult_agents/prompts.py
8. app/mult_agents/nodes.py
9. app/mult_agents/tools.py
10. front/agent_front/src/App.vue
```

如果时间有限，优先读：

```text
app/mult_agents/graph.py
app/mult_agents/main.py
app/mult_agents/nodes.py
app/backend/service/workflow_service.py
front/agent_front/src/App.vue
```

## 6. 建议动手任务

### 任务一：修改意图分流

目标：让简单问题走快速回答，复杂问题走多智能体研究。

相关文件：

- `app/mult_agents/nodes.py`
- `app/mult_agents/prompts.py`

可观察现象：

- 简单问题日志只走 `intent -> direct_answer`。
- 复杂问题日志走完整链路。

### 任务二：修改最终报告格式

目标：调整最终输出结构，比如增加“行动建议”或“风险等级”。

相关文件：

- `app/mult_agents/prompts.py`
- `app/mult_agents/nodes.py`

重点函数：

```text
write_node
```

### 任务三：修复前端乱码文案

目标：让页面中文正常显示。

相关文件：

- `front/agent_front/src/App.vue`
- `front/agent_front/src/assets/main.css`

说明：

当前项目部分中文经历过编码错配，优先修前端文案会最直观。

### 任务四：修复 RAG 入库脚本

目标：让本地 Markdown/TXT 文档可以入库到 Milvus。

相关文件：

- `app/mult_agents/rag/ingest.py`
- `app/mult_agents/rag/core.py`
- `config.json`

说明：

当前 `ingest.py` 里有作者本机路径和错误 import，需要重构。

## 7. 当前项目需要注意的问题

### 编码乱码

项目里不少中文注释、日志、prompt 和前端文案出现乱码。学习时可以先理解结构，后面再逐步修复文案。

### 模型接口差异

`qwen3.7-plus` 这类新模型更适合走百炼 OpenAI-compatible API。

旧的 `ChatTongyi` / DashScope Generation 接口可能会返回：

```text
InvalidParameter: url error
```

### 外部依赖较多

完整能力依赖：

- DashScope / 百炼
- Bocha
- PostgreSQL
- Redis
- Milvus

学习阶段建议先只保留模型调用，把记忆和 RAG 关闭。

### API Key 安全

不要把真实 API Key 提交到仓库或截图传播。已经暴露过的 key 建议在控制台作废并重新生成。

## 8. 一句话理解这个项目

这个项目的核心不是简单聊天，而是用 LangGraph 把多个 Agent 编排成一条研究流水线：先判断问题，再拆解任务，再检索证据，再评估证据，再形成结论，最后输出带来源意识的研究报告。
