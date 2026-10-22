<div align="center">

<img src="./static/image/futures-reports-logo.svg" alt="FuturesReport Logo" width="22%"/>

# FuturesReport

A Futures Studies AI Multi-Agent Simulation Engine

[![Docker](https://img.shields.io/badge/Docker-Build-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/)
[![License](https://img.shields.io/badge/License-AGPLv3-blue?style=flat-square)](./LICENSE)

[English](./README.md) | [简体中文](./README-ZH.md) | [繁體中文](./README-ZH-TW.md)

</div>

## ⚡ Overview

**FuturesReport** is a next-generation AI prediction engine powered by multi-agent technology. By extracting seed information from the real world (such as breaking news, policy drafts, or financial signals), it automatically constructs a high-fidelity parallel digital world. Within this space, thousands of intelligent agents with independent personalities, long-term memory, and behavioral logic freely interact and undergo social evolution. You can inject variables dynamically from a "God's-eye view" to precisely deduce future trajectories — **rehearse the future in a digital sandbox, and win decisions after countless simulations**.

> You only need to: Upload seed materials (data analysis reports or interesting novel stories) and describe your prediction requirements in natural language</br>
> FuturesReport will return: A detailed prediction report and a deeply interactive high-fidelity digital world

### Our Vision

FuturesReport is dedicated to creating a swarm intelligence mirror that maps reality. By capturing the collective emergence triggered by individual interactions, we break through the limitations of traditional prediction:

- **At the Macro Level**: We are a rehearsal laboratory for decision-makers, allowing policies and public relations to be tested at zero risk
- **At the Micro Level**: We are a creative sandbox for individual users — whether deducing novel endings or exploring imaginative scenarios, everything can be fun, playful, and accessible

From serious predictions to playful simulations, we let every "what if" see its outcome, making it possible to predict anything.

## 📸 Screenshots

<div align="center">
<table>
<tr>
<td><img src="./static/image/Screenshot/运行截图1.png" alt="Screenshot 1" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图2.png" alt="Screenshot 2" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/运行截图3.png" alt="Screenshot 3" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图4.png" alt="Screenshot 4" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/运行截图5.png" alt="Screenshot 5" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图6.png" alt="Screenshot 6" width="100%"/></td>
</tr>
</table>
</div>

## 🎬 Demo Videos

### 1. Wuhan University Public Opinion Simulation

<div align="center">
<a href="https://www.bilibili.com/video/BV1VYBsBHEMY/" target="_blank"><img src="./static/image/武大模拟演示封面.png" alt="Demo Video" width="75%"/></a>

Click the image to watch the complete demo video for prediction using BettaFish-generated "Wuhan University Public Opinion Report"
</div>

### 2. Dream of the Red Chamber Lost Ending Simulation

<div align="center">
<a href="https://www.bilibili.com/video/BV1cPk3BBExq" target="_blank"><img src="./static/image/红楼梦模拟推演封面.jpg" alt="Demo Video" width="75%"/></a>

Click the image to watch a deep prediction of the lost ending based on hundreds of thousands of words from the first 80 chapters of "Dream of the Red Chamber"
</div>

> **Financial Prediction**, **Political News Prediction** and more examples coming soon...

## 🔄 Workflow

1. **Graph Building**: Seed extraction & Individual/collective memory injection & GraphRAG construction
2. **Environment Setup**: Entity relationship extraction & Persona generation & Agent configuration injection
3. **Simulation**: Dual-platform parallel simulation & Auto-parse prediction requirements & Dynamic temporal memory updates
4. **Foresight Report** *(Futures Studies Powered)*: STEEP analysis & Causal Layered Analysis (CLA) & multi-scenario planning (possible/plausible/preferred futures) & emerging issues identification
5. **Deep Interaction**: Engage preferred futures — chat with any simulated agent & test scenario hypotheses & deep analysis with ReportAgent

## 🔭 Futures Studies Methodology

FuturesReport embeds academic **Futures Studies** methodology into its AI multi-agent simulation engine, transforming raw simulation output into structured, multi-futures analysis:

| Framework | Description |
|-----------|-------------|
| **Futures Cone** | Classifies outcomes into *Possible*, *Plausible*, and *Preferred* futures |
| **STEEP Analysis** | Systematic evaluation across Social, Technological, Environmental, Economic, and Political dimensions |
| **Causal Layered Analysis (CLA)** | Four-layer deep dive: Litany (surface events) → Systemic (structures) → Worldview (values) → Myth/Metaphor (deep culture) |
| **Multi-Scenario Planning** | Dual-variable matrix producing four scenario types: Best Case, Worst Case, Business as Usual, and Outlier (wild card) |
| **Emerging Issues** | Detects edge behaviors in simulation data as early signals of potential futures turning points |

> Terminology follows **Taiwan Futures Studies academic standards**, grounded in Sohail Inayatullah's CLA framework and standard Chinese academic translations used in Taiwan's futures studies scholarship.

## 🚀 Quick Start

### Option 1: Source Code Deployment (Recommended)

#### Prerequisites

| Tool | Version | Description | Check Installation |
|------|---------|-------------|-------------------|
| **Node.js** | 18+ | Frontend runtime, includes npm | `node -v` |
| **Python** | ≥3.11, ≤3.12 | Backend runtime | `python --version` |
| **uv** | Latest | Python package manager | `uv --version` |

#### 1. Configure Environment Variables

```bash
# Copy the example configuration file
cp .env.example .env

# Edit the .env file and fill in the required API keys
```

**Required Environment Variables:**

```env
# LLM API Configuration (supports any LLM API with OpenAI SDK format)
# Recommended: Alibaba Qwen-plus model via Bailian Platform: https://bailian.console.aliyun.com/
# High consumption, try simulations with fewer than 40 rounds first
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus

# FalkorDB (self-hosted graph engine, replaces Zep Cloud)
# LLM/embedding calls are BYOK — each user's own model settings, not a platform-wide key.
# Source deployment: run FalkorDB locally first, e.g.:
#   docker run -p 6379:6379 -p 3000:3000 -d falkordb/falkordb:latest
# Docker / Coolify deployment: FALKORDB_HOST/PORT/PASSWORD are auto-injected, leave unset here.
# FALKORDB_HOST=localhost
# FALKORDB_PORT=6379
# FALKORDB_PASSWORD=
```

#### 2. Install Dependencies

```bash
# One-click installation of all dependencies (root + frontend + backend)
npm run setup:all
```

Or install step by step:

```bash
# Install Node dependencies (root + frontend)
npm run setup

# Install Python dependencies (backend, auto-creates virtual environment)
npm run setup:backend
```

#### 3. Start Services

```bash
# Start both frontend and backend (run from project root)
npm run dev
```

**Service URLs:**
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:5001`

**Start Individually:**

```bash
npm run backend   # Start backend only
npm run frontend  # Start frontend only
```

### Option 2: Docker Deployment

```bash
# 1. Configure environment variables (same as source deployment)
cp .env.example .env

# 2. Pull image and start
docker compose up -d
```

Reads `.env` from root directory by default, maps port `5001` (Flask serves the API and the built frontend)

> Mirror address for faster pulling is provided as comments in `docker-compose.yml`, replace if needed.

### Option 3: Self-hosted with Coolify

FuturesReport runs well on a single VPS (4 vCPU / 8 GB RAM is plenty) managed by [Coolify](https://coolify.io). The container filesystem is **ephemeral** - every redeploy wipes it - so persistent storage matters.

1. **PostgreSQL** - create a PostgreSQL resource and point the application's `DATABASE_URL` at its internal URL. Enable scheduled backups.
2. **Application** - create an application from this repository with the **Dockerfile** build pack and set *Ports Exposes* to `5001` (Flask serves both the API and the built frontend). The first build downloads PyTorch/CUDA wheels (several GB) and takes a while; the Dockerfile already raises uv's HTTP timeout.
3. **Persistent storage** - mount volumes at `/data` and `/app/backend/uploads`. Project files, simulation data and reports live under `backend/uploads/` by default; without a volume they are deleted on every redeploy while database records survive, leaving orphaned references such as "Project not found: proj_xxx".
4. **Environment variables** (keep secrets runtime-only): `DATABASE_URL`, `SECRET_KEY`, `SITE_URL` (your public URL, used to build the Stripe webhook URL), `LLM_*`, and the FalkorDB variables below. `FLASK_DEBUG` is already `false` in the image.

> `SECRET_KEY` is **required** - use a long random value. It signs login tokens and encrypts stored API keys and payment settings. Changing it later logs everyone out and requires re-entering the stored keys.

#### FalkorDB on Coolify

The knowledge-graph engine (Graphiti + FalkorDB) needs its own persistent service:

1. Add a Docker Image resource `falkordb/falkordb:latest` in the same Coolify project. **Do not give it a public domain or published port.**
2. Mount a persistent volume at **`/var/lib/falkordb/data`** - the image's actual persistence directory (verify with `redis-cli CONFIG GET dir`). Mounting `/data` does not persist graphs.
3. Set a password: `REDIS_ARGS=--requirepass <your-password>`.
4. On the application set `FALKORDB_HOST=<the FalkorDB resource's internal hostname>`, `FALKORDB_PORT=6379` and `FALKORDB_PASSWORD=<the same password>`.

LLM/embedding calls made against FalkorDB are BYOK (each user's own model settings, read from their account), so no platform-wide LLM key is needed for the graph engine itself.

> Keep FalkorDB private: the backend only needs to reach it over Coolify's internal network.

#### Automatic deployment

In the GitHub repository add a webhook (content type `application/json`, *push* events only) pointing at your Coolify instance's `/webhooks/source/github/events/manual` URL, and set the same secret on the application in Coolify. Pushes to the configured branch then redeploy automatically.

## 📄 Acknowledgments

FuturesReport's simulation engine is powered by **[OASIS (Open Agent Social Interaction Simulations)](https://github.com/camel-ai/oasis)**. We sincerely thank the CAMEL-AI team for their open-source contributions!

## 📜 License

Licensed under the [GNU Affero General Public License v3.0](./LICENSE).
