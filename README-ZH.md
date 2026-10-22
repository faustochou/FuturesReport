<div align="center">

<img src="./static/image/futures-reports-logo.svg" alt="FuturesReport Logo" width="22%"/>

# FuturesReport 未境報告

未來學 AI 多智能體模擬引擎

[![Docker](https://img.shields.io/badge/Docker-Build-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/)
[![License](https://img.shields.io/badge/License-AGPLv3-blue?style=flat-square)](./LICENSE)

[English](./README.md) | [简体中文](./README-ZH.md) | [繁體中文](./README-ZH-TW.md)

</div>

## ⚡ 项目概述

**FuturesReport** 是一款基于多智能体技术的新一代 AI 预测引擎。通过提取现实世界的种子信息（如突发新闻、政策草案、金融信号），自动构建出高保真的平行数字世界。在此空间内，成千上万个具备独立人格、长期记忆与行为逻辑的智能体进行自由交互与社会演化。你可透过「上帝视角」动态注入变量，精准推演未来走向——**让未来在数字沙盘中预演，助决策在百战模拟后胜出**。

> 你只需：上传种子材料（数据分析报告或者有趣的小说故事），并用自然语言描述预测需求</br>
> FuturesReport 将返回：一份详尽的预测报告，以及一个可深度交互的高保真数字世界

### 我们的愿景

FuturesReport 致力于打造映射现实的群体智能镜像，通过捕捉个体互动引发的群体涌现，突破传统预测的局限：

- **于宏观**：我们是决策者的预演实验室，让政策与公关在零风险中试错
- **于微观**：我们是个人用户的创意沙盘，无论是推演小说结局还是探索脑洞，皆可有趣、好玩、触手可及

从严肃预测到趣味仿真，我们让每一个如果都能看见结果，让预测万物成为可能。

## 📸 系统截图

<div align="center">
<table>
<tr>
<td><img src="./static/image/Screenshot/运行截图1.png" alt="截图1" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图2.png" alt="截图2" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/运行截图3.png" alt="截图3" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图4.png" alt="截图4" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/运行截图5.png" alt="截图5" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图6.png" alt="截图6" width="100%"/></td>
</tr>
</table>
</div>

## 🎬 演示视频

### 1. 武汉大学舆情推演预测

<div align="center">
<a href="https://www.bilibili.com/video/BV1VYBsBHEMY/" target="_blank"><img src="./static/image/武大模拟演示封面.png" alt="演示视频" width="75%"/></a>

点击图片查看使用微舆BettaFish生成的《武大舆情报告》进行预测的完整演示视频
</div>

### 2. 《红楼梦》失传结局推演预测

<div align="center">
<a href="https://www.bilibili.com/video/BV1cPk3BBExq" target="_blank"><img src="./static/image/红楼梦模拟推演封面.jpg" alt="演示视频" width="75%"/></a>

点击图片查看基于《红楼梦》前80回数十万字的深度预测失传结局
</div>

> **金融方向推演预测**、**时政要闻推演预测**等示例陆续更新中...

## 🔄 工作流程

1. **图谱构建**：现实种子提取 & 个体与群体记忆注入 & GraphRAG构建
2. **环境搭建**：实体关系抽取 & 人设生成 & 环境配置Agent注入仿真参数
3. **开始模拟**：双平台并行模拟 & 自动解析预测需求 & 动态更新时序记忆
4. **未来学报告** *（未来学方法论驱动）*：STEEP分析 & 因果分层分析（CLA）& 多情节规划（可能／似乎／渴望的未来）& 浮现议题识别
5. **深度互动**：对话渴望的未来 — 与任意模拟Agent互动 & 检验情节假设 & 与ReportAgent深化分析

## 🔭 未来学研究方法论

FuturesReport 将学术级**未来学（Futures Studies）**方法论整合进 AI 多智能体模拟引擎，将模拟输出转化为结构化的多种未来分析。

| 方法论框架 | 说明 |
|-----------|------|
| **未来锥（Futures Cone）** | 将预测结果分类为*可能的未来*、*似乎的未来*、*渴望的未来* |
| **STEEP 分析** | 系统性覆盖社会、科技、环境、经济、政治五大维度 |
| **因果分层分析法（CLA）** | 四层次深度剖析：表象层 → 系统层 → 世界观 → 迷思／隐喻层 |
| **多情节规划** | 双变数情节矩阵：最佳想象、最糟想象、如常情节、骤变情节 |
| **浮现议题识别** | 从模拟数据中侦测边缘行为，作为未来重大转折的早期信号 |

> 术语遵循**台湾未来学学术标准**，以 Sohail Inayatullah 的因果分层分析法（CLA）框架为基础，采用台湾未来学学术界使用的标准中文译名。

## 🚀 快速开始

### 一、源码部署（推荐）

#### 前置要求

| 工具 | 版本要求 | 说明 | 安装检查 |
|------|---------|------|---------|
| **Node.js** | 18+ | 前端运行环境，包含 npm | `node -v` |
| **Python** | ≥3.11, ≤3.12 | 后端运行环境 | `python --version` |
| **uv** | 最新版 | Python 包管理器 | `uv --version` |

#### 1. 配置环境变量

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑 .env 文件，填入必要的 API 密钥
```

**必需的环境变量：**

```env
# LLM API配置（支持 OpenAI SDK 格式的任意 LLM API）
# 推荐使用阿里百炼平台qwen-plus模型：https://bailian.console.aliyun.com/
# 注意消耗较大，可先进行小于40轮的模拟尝试
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus

# FalkorDB（自架图谱引擎，取代 Zep Cloud）
# LLM/embedding 调用采用 BYOK——用每个用户自己的模型设定，不是平台统一的 key。
# 源码部署：先在本机跑一个 FalkorDB，例如：
#   docker run -p 6379:6379 -p 3000:3000 -d falkordb/falkordb:latest
# Docker / Coolify 部署：FALKORDB_HOST/PORT/PASSWORD 由部署环境自动注入，此处留空即可。
# FALKORDB_HOST=localhost
# FALKORDB_PORT=6379
# FALKORDB_PASSWORD=
```

#### 2. 安装依赖

```bash
# 一键安装所有依赖（根目录 + 前端 + 后端）
npm run setup:all
```

或者分步安装：

```bash
# 安装 Node 依赖（根目录 + 前端）
npm run setup

# 安装 Python 依赖（后端，自动创建虚拟环境）
npm run setup:backend
```

#### 3. 启动服务

```bash
# 同时启动前后端（在项目根目录执行）
npm run dev
```

**服务地址：**
- 前端：`http://localhost:3000`
- 后端 API：`http://localhost:5001`

**单独启动：**

```bash
npm run backend   # 仅启动后端
npm run frontend  # 仅启动前端
```

### 二、Docker 部署

```bash
# 1. 配置环境变量（同源码部署）
cp .env.example .env

# 2. 拉取镜像并启动
docker compose up -d
```

默认会读取根目录下的 `.env`，并映射端口 `5001`（Flask 同时提供 API 与前端正式构建）

> 在 `docker-compose.yml` 中已通过注释提供加速镜像地址，可按需替换

### 三、使用 Coolify 自建

FuturesReport 一台 VPS 就能跑（4 vCPU / 8 GB RAM 绰绰有余），并用 [Coolify](https://coolify.io) 管理。容器文件系统是**临时的（ephemeral）**：每次重新部署都会清空容器本地磁盘，所以持久化存储很重要。

1. **PostgreSQL**：创建 PostgreSQL 资源，并把应用的 `DATABASE_URL` 指向它的内部连接地址，记得开启定时备份。
2. **应用**：用本仓库创建应用，Build Pack 选 **Dockerfile**，*Ports Exposes* 设为 `5001`（Flask 同时提供 API 与前端正式构建）。第一次构建会下载 PyTorch / CUDA 包（数 GB），需要一些时间；Dockerfile 已经调高 uv 的 HTTP 超时。
3. **持久化存储**：把磁盘挂载到 `/data` 与 `/app/backend/uploads`。项目文件、模拟数据与报告默认存放在 `backend/uploads/`，没有持久化磁盘的话，每次重新部署都会被删除，但数据库记录还在，就会出现打开旧记录时「Project not found: proj_xxx」这类孤立引用。
4. **环境变量**（机密只在运行时提供）：`DATABASE_URL`、`SECRET_KEY`、`SITE_URL`（公开地址，用来拼装 Stripe Webhook 地址）、`LLM_*`，以及下方的 FalkorDB 变量。镜像已默认 `FLASK_DEBUG=false`。

> `SECRET_KEY` **必填**，请使用足够长的随机字符串。它用来签发登录凭证，并加密已保存的 API 密钥与支付设置。事后更换会让所有人被登出，且已保存的密钥需要重新输入。

#### Coolify 上的 FalkorDB

知识图谱引擎（Graphiti + FalkorDB）需要独立的持久化服务：

1. 在同一个 Coolify 项目新增 Docker Image 资源 `falkordb/falkordb:latest`，**不要设置公开域名或对外端口**。
2. 把持久化磁盘挂载到 **`/var/lib/falkordb/data`**，这是镜像实际的持久化目录（可用 `redis-cli CONFIG GET dir` 确认）。挂载 `/data` 并不会保存图谱。
3. 设置密码：`REDIS_ARGS=--requirepass <你的密码>`。
4. 在应用中设置 `FALKORDB_HOST=<FalkorDB 资源的内部主机名>`、`FALKORDB_PORT=6379`、`FALKORDB_PASSWORD=<同一个密码>`。

对 FalkorDB 的 LLM / 嵌入调用是 BYOK（使用每位用户自己账号中的模型设置），所以图谱引擎本身不需要平台级的 LLM 密钥。

> 请让 FalkorDB 保持私有：后端只需要通过 Coolify 的内部网络连接。

#### 自动部署

在 GitHub 仓库新增 Webhook（Content type 选 `application/json`，只勾选 *push* 事件），地址填 Coolify 的 `/webhooks/source/github/events/manual`，并在 Coolify 的应用中设置相同的密钥。之后推送到设定的分支就会自动重新部署。

## 📄 致谢

FuturesReport 的仿真引擎由 **[OASIS](https://github.com/camel-ai/oasis)** 驱动，我们衷心感谢 CAMEL-AI 团队的开源贡献！

## 📜 许可证

本项目基于 [GNU Affero General Public License v3.0](./LICENSE) 授权。
