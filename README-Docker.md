# 第六天：运行 Docker 版 AI Agent

项目目录：`C:\Users\26326\Desktop\ai-agent-study`

## 当前入口（2026-09-28）

应用入口已移动到 `app/main.py`。在项目根目录启动，所有启动命令使用 `app.main:app`：

```powershell
cd C:\Users\26326\Desktop\ai-agent-study
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

当前结构：

```text
ai-agent-study/
  app/
    __init__.py
    main.py
    agent.py
    embedding.py
    rag.py
    tools.py
    mcp_client.py
  data/
    company_docs.txt
  mcp_server.py
  Dockerfile
  docker-compose.yml
  requirements.txt
  requirements-embedding.txt
```

`mcp_server.py` 保留在根目录；现有 `from app...` 和 `from mcp_server import mcp` 导入仍适用。`app/embedding.py` 提供 `get_embedding(text)`，通过 SentenceTransformer 加载 `all-MiniLM-L6-v2`，返回 Python 向量列表。

当前 RAG 读取 `data/company_docs.txt`，切分文本、生成 embedding 并写入 ChromaDB，再将用户问题向量化，通过相似度搜索返回知识库原文。索引持久化在 `chroma_db/`；容器内对应 `/app/chroma_db`。

Agent 继续使用以下流程：用户请求 → FastAPI → `run_agent` → Qwen 输出 JSON 决策 → `run_tool` 执行 `rag_search` → Observation → Qwen 生成最终答案。`TOOLS`、`text_length()` 和 MCP 调用入口继续保留。

Docker Compose 继承 Dockerfile 的 `app.main:app` 启动命令，并通过 `OLLAMA_HOST` 连接本机 Ollama：

```powershell
docker compose up -d --build
```

Compose 将本地 `./data` 以只读方式挂载到 `/app/data`，并用命名卷 `chroma_db` 保存向量索引。修改本地知识库后，后续检索会检查并更新索引；重建容器后仍可使用该数据卷。不要使用 `docker compose down -v`，除非确实要删除数据卷。

如果已有通过 `docker run` 创建的同名 `ai-agent-study` 容器，请继续使用下文的 `docker run` 更新方式；两种方式任选一种管理同一服务。

## 历史实测结果（2026-09-24，迁移前版本）

- Docker 客户端和服务端版本：29.8.0，WSL 2 Linux 引擎正常。
- 镜像：`ai-agent-study:latest`；容器：`ai-agent-study`，已启动并保持运行。
- 端口映射：`127.0.0.1:8000` → 容器 `8000`。
- `GET /docs`：HTTP 200，包含 Swagger UI 页面内容。
- `GET /openapi.json`：HTTP 200，包含 `POST /agent` 接口定义。
- 字符统计：`请统计字符` → `字符数量是：5`。
- MCP 调用：`打招呼` → `你好，小明`。
- Qwen 问答：`请只回答：Docker实战成功。/no_think` → `Docker实战成功。`（约 10.42 秒）。

以上结果来自 2026-09-24 的旧版本。此次已更新真实 RAG 所需的依赖和 Docker 配置，未重新验证 Docker 镜像构建或容器端到端运行。

## 这几个文件做什么

- `requirements.txt`：安装 FastAPI、Uvicorn、Pydantic、Ollama、MCP，并包含 `requirements-embedding.txt`。
- `requirements-embedding.txt`：安装 SentenceTransformer 所在的 `sentence-transformers` 包及 ChromaDB。
- `Dockerfile`：以 Python 3.12 为基础，安装依赖，复制 `app/`、`data/` 和根目录的 `mcp_server.py`，以 `app.main:app` 启动 Uvicorn。
- `docker-compose.yml`：设置 Ollama 地址、端口、知识库挂载和 ChromaDB 数据卷。
- `.dockerignore`：构建时排除本地虚拟环境、模型缓存、Chroma 数据和环境变量文件。

Embedding 模型在首次使用时加载，并在同一进程内复用。加载时优先读取完整的本地模型缓存；缓存缺失时才下载 `all-MiniLM-L6-v2`。因此首次检索需要能够访问模型下载服务，耗时也会更长。已有完整缓存时，embedding 推理在本地进行。

Docker 镜像包含模型运行依赖，但没有预先下载模型权重。容器无法自动使用 Windows 上的模型缓存；下面的 `docker run` 命令额外挂载模型缓存卷，供后续重建容器复用。当前 Compose 配置只持久化 ChromaDB，模型缓存保存在容器内，重建容器后可能需要重新下载。Qwen 的 `qwen3:1.7b` 由主机 Ollama 单独管理。

## 构建与首次启动

在 PowerShell 中运行（Docker Desktop 需要先启动）：

```powershell
cd C:\Users\26326\Desktop\ai-agent-study
docker --version
docker info
docker build -t ai-agent-study:latest .
docker run -d --name ai-agent-study -p 127.0.0.1:8000:8000 -e OLLAMA_HOST=http://host.docker.internal:11434 -v ai_agent_chroma:/app/chroma_db -v ai_agent_models:/root/.cache/huggingface ai-agent-study:latest
```

如果旧终端提示找不到 `docker`，重新打开终端；或在当前窗口设置别名后继续：

```powershell
Set-Alias docker "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe"
```

本机首次构建时曾遇到 Docker Hub 认证连接超时；让构建命令使用系统中已有的本地代理后恢复。若在相同网络下重现，可在当前 PowerShell 窗口中设置以下变量，然后重试构建（先确保原有代理程序运行）：

```powershell
$env:HTTP_PROXY = 'http://127.0.0.1:7890'
$env:HTTPS_PROXY = 'http://127.0.0.1:7890'
$env:NO_PROXY = 'localhost,127.0.0.1,host.docker.internal'
docker build -t ai-agent-study:latest .
```

这些设置只影响当前终端会话，不修改系统代理。

镜像是打包后的应用；容器是启动后的应用进程。`127.0.0.1:8000:8000` 把本机 8000 端口连接到容器的 8000 端口。容器里的服务监听 `0.0.0.0`，本机通过 `127.0.0.1` 访问。

容器里的 `localhost` 指向容器本身，因此使用 Docker Desktop 提供的 `host.docker.internal` 连接本机 Ollama。参见 [Docker Desktop 网络说明](https://docs.docker.com/desktop/features/networking/)。

## 访问与验证

打开 [接口文档](http://127.0.0.1:8000/docs)，展开 `POST /agent`，点击 **Try it out**，输入：

```json
{"question": "员工培训政策查询"}
```

响应保持 `answer` 和 `version` 字段。`answer` 由 Qwen 根据检索到的资料生成，措辞可能变化，应包含知识库中的免费职业技能培训、新员工培训、培训费用等相关规定。

继续验证请假制度：

```json
{"question": "请假制度查询"}
```

答案应依据知识库说明提前申请、主管批准、连续请假超过三天需部门负责人审批、病假证明等规定。再查询资料中不存在的事项，例如 `{"question":"公司在火星建办公室的预算是多少？"}`，应明确说明资料中未找到答案。

查看 `docker logs --tail 100 ai-agent-study` 中的 Qwen 决策，确认出现 `"action":"tool"` 和 `"tool":"rag_search"`，随后生成最终答案。

再输入 `{"question": "打招呼"}`，应返回 `{"answer": "你好，小明", "version": "v3"}`，验证 MCP 工具调用。

通过 `/agent` 进行公司资料查询、普通问答或字符统计，都需要本机 Ollama 正在运行并已安装 `qwen3:1.7b`。公司资料查询还会执行本地 embedding 推理。`/docs` 和当前 MCP 打招呼分支不需要 Qwen 推理。

在项目根目录可以单独检查 embedding 导入和向量输出：

```powershell
.\.venv\Scripts\python.exe -c "from app.embedding import get_embedding; print(get_embedding('员工培训政策')[:5])"
```

## 后续使用

已创建过容器时，用 `start` 启动，无需重复 `run`：

```powershell
docker start ai-agent-study
docker ps --filter name=ai-agent-study
docker logs --tail 50 ai-agent-study
docker stop ai-agent-study
```

修改源代码后，需要重建镜像并重建这个容器；先停止并删除本练习容器，再重新运行：

```powershell
docker build -t ai-agent-study:latest .
docker stop ai-agent-study
docker rm ai-agent-study
docker run -d --name ai-agent-study -p 127.0.0.1:8000:8000 -e OLLAMA_HOST=http://host.docker.internal:11434 -v ai_agent_chroma:/app/chroma_db -v ai_agent_models:/root/.cache/huggingface ai-agent-study:latest
```

上述 `docker run` 命令使用 `ai_agent_chroma` 保存向量索引，使用 `ai_agent_models` 保存 embedding 模型缓存；删除容器不会删除这两个命名卷。知识库文件随镜像复制，修改 `data/company_docs.txt` 后需重新构建镜像和容器。使用 Compose 时，知识库来自本地挂载目录。

参考：[FastAPI 官方容器部署说明](https://fastapi.tiangolo.com/deployment/docker/)。
