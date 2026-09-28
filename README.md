# AI Agent 企业知识助手

一个面向 AI Agent 入门与工程实践的企业知识问答项目。用户通过 FastAPI 提交问题，Agent 使用本地 Ollama 上的 Qwen3 决定直接回答或调用工具；企业制度问题通过 Embedding 向量化，再由 ChromaDB 检索本地知识库。项目还包含 MCP 工具调用示例和 Docker Compose 配置。

## 项目介绍

本项目围绕一个企业知识助手，展示 AI Agent 应用中的几个基础工程环节：

- **Agent 决策：** 将用户问题和可用工具说明交给 Qwen3，解析模型返回的 JSON 决策。
- **RAG：** 将企业制度文档切分、生成向量并存入 ChromaDB，再检索相关原文。
- **Tool Calling：** 由 Python 工具分发器执行知识检索或字符统计工具。
- **MCP：** 使用 MCP Python SDK 注册并调用一个问候工具。
- **服务与部署：** FastAPI HTTP 接口、本地 Uvicorn 启动和 Docker Compose 配置。

## 技术栈

| 层 | 技术 | 用途 |
| --- | --- | --- |
| API 服务 | Python 3.12、FastAPI、Uvicorn、Pydantic | HTTP 接口与请求校验 |
| Agent / LLM | Ollama、Qwen3 1.7B | 分析问题并决定是否使用工具 |
| Embedding | Sentence Transformers、all-MiniLM-L6-v2 | 将问题和文档片段转换为向量 |
| 向量数据库 | ChromaDB | 持久化向量并执行相似度检索 |
| Tool Calling | Python、JSON 决策解析 | 执行 Agent 选择的工具 |
| MCP | MCP Python SDK | 演示 MCP Client / Server 调用 |
| 容器 | Docker、Docker Compose | 构建和运行应用 |

## 系统架构

~~~mermaid
flowchart LR
    User["用户 / API 客户端"] -->|"POST /agent"| API["FastAPI<br/>app.main"]
    API --> Agent["Agent<br/>run_agent"]
    Agent <-->|"问题 / JSON 决策"| LLM["Ollama<br/>Qwen3 1.7B"]

    Agent -->|"工具名 + 参数"| Dispatcher["Python 工具分发<br/>run_tool"]
    Dispatcher --> RAG["rag_search"]
    Dispatcher --> Length["text_length"]

    Docs["data/company_docs.txt"] --> Indexer["切分文档并生成向量"]
    Indexer --> Chroma["ChromaDB<br/>本地持久化索引"]
    RAG --> QueryEmbed["问题向量化<br/>all-MiniLM-L6-v2"]
    QueryEmbed --> Chroma
    Chroma --> RAG

    Agent -->|"打招呼分支"| MCPClient["MCP Client"]
    MCPClient --> MCPServer["MCP Server<br/>hello 工具"]

    Agent --> Answer["回答"]
    Answer --> API
    API --> User
~~~

## Agent 执行流程

1. 客户端向 **POST /agent** 发送问题，FastAPI 将其交给 **run_agent**。
2. 问题包含“打招呼”时，Agent 调用 MCP 的 **hello** 工具并返回结果。
3. 其他问题连同工具说明一起发给 Qwen3。
4. Qwen3 返回 JSON 决策：直接回答，或请求调用指定工具。
5. Python 解析决策并执行工具；需要时将 Observation 交回模型继续处理。
6. Agent 返回最终答案，决策循环最多执行 4 轮。

## RAG 流程

~~~mermaid
flowchart TD
    Source["data/company_docs.txt"] --> Split["按段落切分<br/>最长 180 字符，重叠 30 字符"]
    Split --> DocEmbedding["生成文档向量"]
    DocEmbedding --> Index["ChromaDB 持久化索引"]

    Question["用户问题"] --> QueryEmbedding["生成问题向量"]
    QueryEmbedding --> Search["余弦距离检索<br/>最多取 5 个候选片段"]
    Index --> Search
    Search --> Check["相似度与词面证据检查"]
    Check -->|"匹配"| Passage["返回最相关片段"]
    Check -->|"未匹配"| NoResult["提示未找到相关资料"]
~~~

索引会根据文档内容和 Embedding 配置检查是否需要更新。检索阶段最多取 5 个候选并进行相关性判断，当前实现返回最相关的知识片段。考虑到当前 Embedding 模型对中文语义匹配的能力有限，检索还结合了中文概念提示和词面证据作为补充。首次查询时，如果模型尚未缓存，Sentence Transformers 会下载 Embedding 模型。

## Tool Calling 流程

~~~mermaid
flowchart TD
    User["用户问题"] --> Agent["FastAPI / Agent"]
    Agent --> Greeting{"包含打招呼？"}
    Greeting -->|"是"| MCP["MCP Client 调用 hello"]
    MCP --> Return["返回结果"]
    Greeting -->|"否"| LLM["Qwen3 返回 JSON 决策"]
    LLM --> Action{"action"}
    Action -->|"answer"| Return
    Action -->|"tool"| Dispatch["Python run_tool"]
    Dispatch --> Tool{"选择工具"}
    Tool -->|"rag_search"| RAG["检索知识片段"]
    RAG --> HasResult{"找到相关资料？"}
    HasResult -->|"否"| Return
    HasResult -->|"是"| Count{"还要求统计字符？"}
    Count -->|"是"| Length["调用 text_length"]
    Length --> Return
    Count -->|"否"| Return
    Tool -->|"text_length"| Observation["将工具结果作为 Observation"]
    Observation --> LLM
~~~

当前实现通过提示词约定 JSON 决策，再由 Python 执行工具；尚未使用 Ollama 原生 tool_calls 接口。

| 工具 | 作用 |
| --- | --- |
| **rag_search** | 检索培训、请假、报销等企业制度 |
| **text_length** | 统计传入文本的字符数 |

系统提示词要求模型对公司制度问题先调用 **rag_search**，但工具选择仍由模型输出，后端没有额外的关键词规则强制路由。当前 Agent 直接返回检索到的原文片段；若同时要求统计字符数，则继续调用 **text_length** 统计该片段。

## MCP 说明

MCP（Model Context Protocol）为 AI 应用提供统一的工具发现和调用方式。本项目使用 MCP Python SDK 展示一个最小示例：

- 根目录 **mcp_server.py** 使用 MCPServer 注册 **hello(name)**。
- **app/mcp_client.py** 使用 MCP Client 调用工具。
- 用户输入包含“打招呼”时，Agent 调用 **hello("小明")**，返回“你好，小明”。

该示例在当前 Python 进程内连接 Client 和 Server。MCP **hello** 分支由关键词触发；RAG 和字符统计使用项目自己的 JSON 工具分发流程，并未注册为 MCP 工具。

## 关键项目文件

以下列出主要运行文件；本地开发脚本、环境目录和生成的数据目录未展开。

~~~text
ai-agent-study/
├── app/
│   ├── main.py            # FastAPI 应用与 POST /agent
│   ├── agent.py           # Agent 决策循环、Ollama 调用
│   ├── tools.py           # 工具定义与分发
│   ├── rag.py             # 文档切分、索引维护与向量检索
│   ├── embedding.py       # Sentence Transformers 向量生成
│   └── mcp_client.py      # Agent 使用的 MCP Client
├── data/
│   └── company_docs.txt   # 示例企业知识库
├── mcp_server.py          # MCP hello 工具
├── mcp_client.py          # 独立 MCP Client 示例
├── README-Docker.md       # Docker 补充说明
├── requirements.txt
├── requirements-embedding.txt
├── Dockerfile
└── docker-compose.yml
~~~

## 启动方式

### 环境准备

需要 Python 3.12、[Ollama](https://ollama.com/) 和 **qwen3:1.7b** 模型。确保 Ollama 服务已启动，并下载模型：

~~~powershell
ollama pull qwen3:1.7b
~~~

若 Ollama 服务没有自动运行，可在独立终端执行 **ollama serve**。

### 本地启动（Windows PowerShell）

在项目根目录运行：

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
~~~

API 地址为 **http://127.0.0.1:8000/agent**，Swagger UI 为 **http://127.0.0.1:8000/docs**。第一次进行 RAG 查询时，若本地没有缓存，程序会下载 **all-MiniLM-L6-v2**；下载完成后在本机执行向量推理。

### Docker Compose 启动

确保 Docker Desktop、主机上的 Ollama 服务和 **qwen3:1.7b** 均可用，在项目根目录运行：

~~~powershell
docker compose up --build -d
~~~

Compose 将服务映射到本机 8000 端口，通过 **host.docker.internal** 连接主机 Ollama，并用命名卷保存 ChromaDB 数据。Embedding 模型缓存没有挂载持久卷；容器重建后，首次 RAG 请求可能需要重新下载模型。查看日志：

~~~powershell
docker compose logs -f agent
~~~

## API 调用示例

接口为 **POST /agent**，请求体为 JSON：

~~~json
{
  "question": "我们公司的培训政策是什么？"
}
~~~

Windows PowerShell 调用：

~~~powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/agent" -Method Post -ContentType "application/json" -Body (@{ question = "我们公司的培训政策是什么？" } | ConvertTo-Json -Compress)
~~~

返回结构示例：

~~~json
{
  "answer": "公司培训制度：\n1. 公司每年为员工提供一次免费的职业技能培训。\n2. 新员工入职后需要参加基础岗位培训。\n3. 员工可以根据岗位需求申请额外培训。\n4. 培训费用原则上由公司承担。\n5. 参加培训的员工需要完成培训考核。",
  "version": "v3"
}
~~~

也可以打开 Swagger UI，在 **POST /agent** 中点击 **Try it out**。示例问题：

- “公司的请假制度是什么？”：检索请假制度。
- “查询公司的培训政策，并统计字符数量。”：检索制度并统计返回片段的字符数。
- “打招呼”：调用 MCP **hello** 工具。
- “Python 是什么？”：由 Qwen3 直接回答。

## 当前实现范围

这是一个用于学习和作品展示的最小示例：知识库来自本地文本文件，Agent 仅保留单次请求上下文，MCP 部分演示进程内工具调用。后续可扩展原生函数调用、文件导入、检索来源引用、会话记忆和更完整的错误处理。
