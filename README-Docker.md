# 第六天：运行 Docker 版 AI Agent

项目目录：`C:\Users\26326\Desktop\ai-agent-study`

## 当前入口（2026-09-26）

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
    rag.py
    tools.py
    mcp_client.py
  mcp_server.py
  Dockerfile
  docker-compose.yml
  requirements.txt
```

`mcp_server.py` 保留在根目录；现有 `from app...` 和 `from mcp_server import mcp` 导入仍适用。`check_rag_local.py` 检查当前的模拟培训资料，不再引用早期版本的 `documents`、`search_document`。

Docker Compose 继承 Dockerfile 的 `app.main:app` 启动命令，并通过 `OLLAMA_HOST` 连接本机 Ollama：

```powershell
docker compose up -d --build
```

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

容器化过程中未改动现有 Python 源码。新增了三个 Docker 配置文件及本说明。

## 这几个文件做什么

- `requirements.txt`：安装当前 FastAPI 服务需要的 5 个直接依赖，版本与本地 Python 3.12 环境一致。
- `Dockerfile`：以 Python 3.12 为基础，安装依赖，复制 `app/` 和根目录的 `mcp_server.py`，以 `app.main:app` 启动 Uvicorn。
- `.dockerignore`：构建时排除本地虚拟环境、模型缓存、Chroma 数据和环境变量文件。

当前 `app/rag.py` 的 RAG 分支使用模拟资料，因此这个最小镜像不安装 FastEmbed/ChromaDB，也不复制历史练习数据。后续接入真实知识库时再添加依赖和数据卷。

## 构建与首次启动

在 PowerShell 中运行（Docker Desktop 需要先启动）：

```powershell
cd C:\Users\26326\Desktop\ai-agent-study
docker --version
docker info
docker build -t ai-agent-study:latest .
docker run -d --name ai-agent-study -p 127.0.0.1:8000:8000 -e OLLAMA_HOST=http://host.docker.internal:11434 ai-agent-study:latest
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
{"question": "公司培训规定有多少字符？"}
```

执行后应返回：

```json
{"answer": "公司培训规定：公司每年提供一次免费的职业技能培训。\n字符数：25", "version": "v3"}
```

再输入 `{"question": "打招呼"}`，应返回 `{"answer": "你好，小明", "version": "v3"}`，验证 MCP 工具调用。

普通问答需要本机 Ollama 正在运行并已安装 `qwen3:1.7b`。`/docs`、公司培训检索及其字符统计、MCP 打招呼不需要模型推理。

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
docker run -d --name ai-agent-study -p 127.0.0.1:8000:8000 -e OLLAMA_HOST=http://host.docker.internal:11434 ai-agent-study:latest
```

这里没有挂载数据卷，应用也没有持久化写入；真实数据库接入后，需要先配置数据持久化再重建容器。

参考：[FastAPI 官方容器部署说明](https://fastapi.tiangolo.com/deployment/docker/)。
