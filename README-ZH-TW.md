<div align="center">

<img src="./static/image/futures-reports-logo.svg" alt="FuturesReport Logo" width="22%"/>

# FuturesReport 未境報告

未來學 AI 多智能體模擬引擎

[![Docker](https://img.shields.io/badge/Docker-Build-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/)
[![License](https://img.shields.io/badge/License-AGPLv3-blue?style=flat-square)](./LICENSE)

[English](./README.md) | [简体中文](./README-ZH.md) | [繁體中文](./README-ZH-TW.md)

</div>

## ⚡ 專案概述

**FuturesReport** 是一款基於多智能體技術的新一代 AI 預測引擎。透過提取現實世界的種子資訊（如突發新聞、政策草案、金融信號），自動構建出高保真的平行數位世界。在此空間內，成千上萬個具備獨立人格、長期記憶與行為邏輯的智能體進行自由互動與社會演化。您可透過「上帝視角」動態注入變量，精準推演未來走向——**讓未來在數位沙盤中預演，助決策在百戰模擬後勝出**。

> 您只需：上傳種子素材（資料分析報告或有趣的小說故事），並用自然語言描述預測需求</br>
> FuturesReport 將返回：一份詳盡的預測報告，以及一個可深度互動的高保真數位世界

### 我們的願景

FuturesReport 致力於打造映射現實的群體智能鏡像，透過捕捉個體互動引發的群體湧現，突破傳統預測的局限：

- **於宏觀**：我們是決策者的預演實驗室，讓政策與公關在零風險中試錯
- **於微觀**：我們是個人用戶的創意沙盤，無論是推演小說結局還是探索腦洞，皆可有趣、好玩、觸手可及

從嚴肅預測到趣味仿真，我們讓每一個「如果」都能看見結果，讓預測萬物成為可能。

## 📸 系統截圖

<div align="center">
<table>
<tr>
<td><img src="./static/image/Screenshot/运行截图1.png" alt="截圖1" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图2.png" alt="截圖2" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/运行截图3.png" alt="截圖3" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图4.png" alt="截圖4" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/运行截图5.png" alt="截圖5" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图6.png" alt="截圖6" width="100%"/></td>
</tr>
</table>
</div>

## 🎬 示範影片

### 1. 武漢大學輿情推演預測

<div align="center">
<a href="https://www.bilibili.com/video/BV1VYBsBHEMY/" target="_blank"><img src="./static/image/武大模拟演示封面.png" alt="示範影片" width="75%"/></a>

點擊圖片查看使用微輿 BettaFish 生成的《武大輿情報告》進行預測的完整示範影片
</div>

### 2. 《紅樓夢》失傳結局推演預測

<div align="center">
<a href="https://www.bilibili.com/video/BV1cPk3BBExq" target="_blank"><img src="./static/image/红楼梦模拟推演封面.jpg" alt="示範影片" width="75%"/></a>

點擊圖片查看基於《紅樓夢》前80回數十萬字的深度預測失傳結局
</div>

> **金融方向推演預測**、**時政要聞推演預測**等範例陸續更新中...

## 🔄 工作流程

1. **圖譜構建**：現實種子提取 & 個體與群體記憶注入 & GraphRAG構建
2. **環境搭建**：實體關係抽取 & 人設生成 & 環境配置Agent注入仿真參數
3. **開始模擬**：雙平台並行模擬 & 自動解析預測需求 & 動態更新時序記憶
4. **未來學報告** *（未來學方法論驅動）*：STEEP分析 & 因果分層分析（CLA）& 多情節規劃（可能／似乎／渴望的未來）& 浮現議題識別
5. **深度互動**：對話渴望的未來 — 與任意模擬Agent互動 & 檢驗情節假設 & 與ReportAgent深化分析

## 🔭 未來學研究方法論

FuturesReport 將學術級**未來學（Futures Studies）**方法論整合進 AI 多智能體模擬引擎，將模擬輸出轉化為結構化的多種未來分析。

| 方法論框架 | 說明 |
|-----------|------|
| **未來錐（Futures Cone）** | 將預測結果分類為*可能的未來*、*似乎的未來*、*渴望的未來* |
| **STEEP 分析** | 系統性覆蓋社會、科技、環境、經濟、政治五大維度 |
| **因果分層分析法（CLA）** | 四層次深度剖析：表象層 → 系統層 → 世界觀 → 迷思／隱喻層 |
| **多情節規劃** | 雙變數情節矩陣：最佳想象、最糟想象、如常情節、驟變情節 |
| **浮現議題識別** | 從模擬數據中偵測邊緣行為，作為未來重大轉折的早期信號 |

> 術語遵循**台灣未來學學術標準**，以 Sohail Inayatullah 的因果分層分析法（CLA）框架為基礎，採用台灣未來學學術界使用的標準中文譯名。

## 🚀 快速開始

### 一、原始碼部署（推薦）

#### 前置需求

| 工具 | 版本要求 | 說明 | 安裝確認 |
|------|---------|------|---------|
| **Node.js** | 18+ | 前端執行環境，包含 npm | `node -v` |
| **Python** | ≥3.11, ≤3.12 | 後端執行環境 | `python --version` |
| **uv** | 最新版 | Python 套件管理器 | `uv --version` |

#### 1. 配置環境變數

```bash
# 複製範例配置檔案
cp .env.example .env

# 編輯 .env 檔案，填入必要的 API 金鑰
```

**必要的環境變數：**

```env
# LLM API配置（支援 OpenAI SDK 格式的任意 LLM API）
# 推薦使用阿里百鍊平台qwen-plus模型：https://bailian.console.aliyun.com/
# 注意消耗較大，可先進行小於40輪的模擬嘗試
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus

# Zep Cloud 配置
# 每月免費額度即可支撐簡單使用：https://app.getzep.com/
ZEP_API_KEY=your_zep_api_key
```

#### 2. 安裝相依套件

```bash
# 一鍵安裝所有相依套件（根目錄 + 前端 + 後端）
npm run setup:all
```

或者分步安裝：

```bash
# 安裝 Node 相依套件（根目錄 + 前端）
npm run setup

# 安裝 Python 相依套件（後端，自動建立虛擬環境）
npm run setup:backend
```

#### 3. 啟動服務

```bash
# 同時啟動前後端（在專案根目錄執行）
npm run dev
```

**服務位址：**
- 前端：`http://localhost:3000`
- 後端 API：`http://localhost:5001`

**單獨啟動：**

```bash
npm run backend   # 僅啟動後端
npm run frontend  # 僅啟動前端
```

### 二、Docker 部署

```bash
# 1. 配置環境變數（同原始碼部署）
cp .env.example .env

# 2. 拉取映像檔並啟動
docker compose up -d
```

預設會讀取根目錄下的 `.env`，並映射連接埠 `3000（前端）/5001（後端）`

> 在 `docker-compose.yml` 中已透過註解提供加速映像檔位址，可依需求替換

### 三、Zeabur 部署

Zeabur 的容器檔案系統是**暫時性的（ephemeral）**：每次重新部署都會清空容器本機磁碟。FuturesReport 預設將專案檔案、模擬資料、報告存放在 `backend/uploads/` 目錄下，若未設定持久化卷，重新部署會把該目錄整個清空，而資料庫中的紀錄（模擬歷史、報告）不受影響，於是開啟舊的推演記錄時會出現「專案不存在：proj_xxx」這類孤兒引用錯誤。

為避免此問題，請在 Zeabur 上部署前設定持久化儲存：

1. 在後端服務上新增一個 **Volume（持久化卷）**，掛載到容器內，例如掛載路徑 `/data/uploads`。
2. 在後端服務上設定環境變數 `UPLOAD_FOLDER=/data/uploads`，讓所有專案／模擬／報告檔案都寫入掛載的持久化卷，而非暫時性的容器磁碟。
3. （可選但建議）若你使用 SQLite 回退方案而非 `DATABASE_URL`，也請將 `USER_DATA_DIR` 指向同一持久化卷下的路徑（例如 `/data`），使資料庫檔案同樣能在重新部署後保留。

若未設定持久化卷與 `UPLOAD_FOLDER`，即使資料庫紀錄仍然存在，專案／模擬／報告檔案也會在每次重新部署後遺失——這是容器暫時性儲存的已知限制，並非應用程式邏輯的缺陷。

## 💳 如何設定 Stripe 金流

FuturesReport 支援 Stripe 訂閱制（目前開放 Lite 方案）。

### 1. 取得 Stripe 金鑰

前往 [Stripe Dashboard → Developers → API Keys](https://dashboard.stripe.com/apikeys)，複製以下兩組金鑰：

- **Secret Key**（`sk_test_...`）— 僅在伺服器端使用，請勿外洩
- **Publishable Key**（`pk_test_...`）— 前端可見，用於 Stripe.js 初始化

### 2. 建立訂閱方案

1. 進入 [Stripe Dashboard → Product Catalog](https://dashboard.stripe.com/products)
2. 新增產品「FuturesReport Lite」，類型選「Recurring（訂閱）」
3. 設定月付金額後，複製產生的 **Price ID**（`price_...`）

### 3. 設定 Webhook

1. 進入 [Stripe Dashboard → Developers → Webhooks](https://dashboard.stripe.com/webhooks)
2. 新增端點，URL 填入：`https://your-domain.com/api/subscription/webhook`
3. 選擇監聽以下事件：
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
4. 儲存後複製 **Webhook Signing Secret**（`whsec_...`）

### 4. 填入環境變數

在 `.env` 中填入以下變數（或在 Zeabur / Docker 環境中設定）：

```env
STRIPE_SECRET_KEY=sk_test_your_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
STRIPE_PRICE_ID_LITE=price_your_lite_price_id
```

### 5. 在後台管理系統驗證

啟動服務後，前往 `/admin` → **金流設定** 分頁，確認串接狀態顯示「✓ 已設定」。

> **注意**：Premium 和 Pro 方案目前 `is_available = false`，管理員可在後台 **訂閱分級** 分頁開放並設定 Price ID。

## 📄 致謝

FuturesReport 的仿真引擎由 **[OASIS](https://github.com/camel-ai/oasis)** 驅動，我們衷心感謝 CAMEL-AI 團隊的開源貢獻！

## 📜 授權條款

本專案基於 [GNU Affero General Public License v3.0](./LICENSE) 授權。
