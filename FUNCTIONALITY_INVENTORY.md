# Functionality Inventory — 不可破壞清單

> 建立日期：2026-07-04  
> 分支：refactor/cleanup  
> 用途：整理階段的安全網，列出所有不得破壞的功能點。

---

## 1. Python 後端進入點

| 檔案 | 用途 |
|------|------|
| `backend/run.py` | Flask 啟動入口，`python run.py` 啟動服務；讀取 FLASK_HOST / FLASK_PORT |
| `backend/app/__init__.py` | `create_app()` 工廠函式；藍圖註冊、CORS、DB 初始化、SimulationRunner 清理鉤子 |
| `backend/alembic/` | DB migration；`alembic upgrade head` 在 Docker/Zeabur 啟動時執行 |

---

## 2. Flask 藍圖 & API Endpoint

### 2.1 Auth — `/api/auth`

| Method | Path | 描述 | 認證 |
|--------|------|------|------|
| GET | `/api/auth/providers` | 列出 LLM 提供商 | 無 |
| POST | `/api/auth/register` | 註冊帳號（第一位使用者自動成為 admin） | 無 |
| POST | `/api/auth/login` | 登入，回傳 JWT token | 無 |
| GET | `/api/auth/me` | 取得當前使用者資料 | `@require_auth` |
| PUT | `/api/auth/llm-config` | 更新 LLM 提供商設定 | `@require_auth` |
| POST | `/api/auth/logout` | 登出（stateless，server 端 no-op） | 無 |

### 2.2 Admin — `/api/admin`

| Method | Path | 描述 | 認證 |
|--------|------|------|------|
| POST | `/api/admin/login` | 管理員登入 | 無 |
| GET | `/api/admin/me` | 當前管理員資料 | `@require_admin` |
| GET | `/api/admin/dashboard` | 系統統計（用戶數、CPU/記憶體） | `@require_admin` |
| GET | `/api/admin/users` | 列出所有使用者 | `@require_admin` |
| PUT | `/api/admin/users/<id>` | 更新使用者（username/password/llm） | `@require_admin` |
| PUT | `/api/admin/users/<id>/role` | 切換角色（admin ↔ user） | `@require_admin` |
| PUT | `/api/admin/users/<id>/active` | 啟用/停用帳號 | `@require_admin` |
| DELETE | `/api/admin/users/<id>` | 刪除使用者 | `@require_admin` |
| PUT | `/api/admin/users/<id>/subscription` | 管理員手動授予/撤銷訂閱 | `@require_admin` |
| GET | `/api/admin/versions` | 版本歷史 | `@require_admin` |
| GET | `/api/admin/stripe/settings` | Stripe 設定摘要（不回傳明文金鑰） | `@require_admin` |
| GET | `/api/admin/subscription/tiers` | 列出所有訂閱方案 | `@require_admin` |
| PUT | `/api/admin/subscription/tiers/<code>` | 更新方案（price_id / feature_flags / is_available） | `@require_admin` |

### 2.3 Subscription — `/api/subscription`

| Method | Path | 描述 | 認證 |
|--------|------|------|------|
| GET | `/api/subscription/status` | 取得使用者訂閱狀態 | `@require_auth` |
| POST | `/api/subscription/create-checkout-session` | 建立 Stripe Checkout Session | `@require_auth` |
| POST | `/api/subscription/create-portal-session` | 建立 Stripe Customer Portal Session | `@require_auth` |
| POST | `/api/subscription/webhook` | **Stripe Webhook**（無 auth，Stripe-Signature 驗證） | 無（簽名驗證） |

### 2.4 Graph — `/api/graph`

| Method | Path | 描述 | 認證 |
|--------|------|------|------|
| GET | `/api/graph/project/<id>` | 取得專案詳情 | 無 |
| GET | `/api/graph/project/list` | 列出專案 | 無 |
| DELETE | `/api/graph/project/<id>` | 刪除專案 | 無 |
| POST | `/api/graph/project/<id>/reset` | 重置專案狀態 | 無 |
| POST | `/api/graph/ontology/generate` | 上傳檔案 → 生成本體定義（LLM） | `@require_llm_config` |
| POST | `/api/graph/build` | 建構 Zep 知識圖譜（非同步任務） | 無 |
| GET | `/api/graph/task/<id>` | 查詢任務狀態 | 無 |
| GET | `/api/graph/tasks` | 列出所有任務 | 無 |
| GET | `/api/graph/data/<graph_id>` | 取得圖譜節點/邊資料 | 無 |
| DELETE | `/api/graph/delete/<graph_id>` | 刪除 Zep 圖譜 | 無 |

### 2.5 Simulation — `/api/simulation`

| Method | Path | 描述 | 認證 |
|--------|------|------|------|
| GET | `/api/simulation/entities/<graph_id>` | 取得圖譜實體 | 無 |
| GET | `/api/simulation/entities/<graph_id>/<uuid>` | 取得單一實體詳情 | 無 |
| GET | `/api/simulation/entities/<graph_id>/by-type/<type>` | 依類型取得實體 | 無 |
| POST | `/api/simulation/create` | 建立模擬 | 無 |
| POST | `/api/simulation/prepare` | 準備模擬環境（LLM 生成 Profile + Config，非同步） | `@require_auth` `@require_llm_config` |
| POST | `/api/simulation/prepare/status` | 查詢準備進度 | 無 |
| GET | `/api/simulation/<id>` | 取得模擬狀態 | 無 |
| GET | `/api/simulation/list` | 列出模擬 | 無 |
| GET | `/api/simulation/history` | 歷史模擬列表（含專案詳情） | 無 |
| GET | `/api/simulation/<id>/profiles` | 取得 Agent Profile | 無 |
| GET | `/api/simulation/<id>/profiles/realtime` | 即時取得 Profile（生成中） | 無 |
| GET | `/api/simulation/<id>/config/realtime` | 即時取得 Config（生成中） | 無 |
| GET | `/api/simulation/<id>/config` | 取得模擬配置 | 無 |
| GET | `/api/simulation/<id>/config/download` | 下載配置 JSON | 無 |
| GET | `/api/simulation/script/<name>/download` | 下載執行腳本 | 無 |
| POST | `/api/simulation/generate-profiles` | 從圖譜直接生成 Profile | 無 |
| POST | `/api/simulation/start` | 啟動模擬 | `@require_auth` `@require_llm_config` |
| POST | `/api/simulation/stop` | 停止模擬 | 無 |
| GET | `/api/simulation/<id>/run-status` | 模擬執行即時狀態 | 無 |
| GET | `/api/simulation/<id>/run-status/detail` | 執行詳細狀態（含動作） | 無 |
| GET | `/api/simulation/<id>/actions` | 動作歷史 | 無 |
| GET | `/api/simulation/<id>/timeline` | 時間線（按輪次） | 無 |
| GET | `/api/simulation/<id>/agent-stats` | Agent 統計 | 無 |
| GET | `/api/simulation/<id>/posts` | 模擬帖子（SQLite） | 無 |
| GET | `/api/simulation/<id>/comments` | 模擬留言（SQLite，僅 Reddit） | 無 |

### 2.6 Report — `/api/report`

| Method | Path | 描述 | 認證 |
|--------|------|------|------|
| POST | `/api/report/generate` | 生成報告（非同步） | `@require_auth` `@require_llm_config` |
| POST | `/api/report/generate/status` | 查詢生成進度 | 無 |
| GET | `/api/report/<id>` | 取得報告 | 無 |
| GET | `/api/report/by-simulation/<sim_id>` | 依模擬 ID 取得報告 | 無 |
| GET | `/api/report/list` | 列出報告 | 無 |
| GET | `/api/report/<id>/download` | 下載 Markdown 報告 | 無 |
| DELETE | `/api/report/<id>` | 刪除報告 | 無 |
| POST | `/api/report/chat` | Report Agent 對話 | `@require_auth` `@require_llm_config` |
| GET | `/api/report/<id>/progress` | 報告生成進度 | 無 |
| GET | `/api/report/<id>/sections` | 已生成章節列表 | 無 |
| GET | `/api/report/<id>/section/<n>` | 取得單一章節 | 無 |
| GET | `/api/report/check/<sim_id>` | 檢查是否有報告（解鎖 Interview） | 無 |
| GET | `/api/report/<id>/agent-log` | Agent 執行日誌（增量） | 無 |
| GET | `/api/report/<id>/agent-log/stream` | Agent 執行日誌（全量） | 無 |
| GET | `/api/report/<id>/console-log` | 控制台日誌（增量） | 無 |
| GET | `/api/report/<id>/console-log/stream` | 控制台日誌（全量） | 無 |
| POST | `/api/report/tools/search` | 圖譜搜尋工具（調試用） | 無 |
| POST | `/api/report/tools/statistics` | 圖譜統計（調試用） | 無 |

### 2.7 健康檢查

| Method | Path | 描述 |
|--------|------|------|
| GET | `/health` | K8s/Zeabur 探針；回傳 CPU/記憶體資訊 |

---

## 3. Stripe Webhook

- **路由**：`POST /api/subscription/webhook`
- **無 Bearer token 認證**，改用 `Stripe-Signature` header 驗證
- **處理的 event types**（`_HANDLERS` dict in `subscription.py`）：
  - `checkout.session.completed` → 啟用訂閱
  - `customer.subscription.updated` → 同步狀態/期限
  - `customer.subscription.deleted` → 標記 canceled
  - `invoice.payment_failed` → 標記 past_due
- **Webhook secret**：`STRIPE_WEBHOOK_SECRET` 環境變數（不可移除）
- **始終回傳 200**，避免 Stripe 無限重試

---

## 4. RBAC 權限邏輯（不可重寫）

| 規則 | 位置 | 說明 |
|------|------|------|
| 第一位使用者為 admin | `UserManager.create_user()` L347 | `count == 0` 時 role 設為 "admin" |
| 不能降級最後一個 admin | `UserManager.update_user()` L443-449 | admin_count ≤ 1 時拋 ValueError |
| 不能刪除最後一個 admin | `UserManager.delete_user()` L567-572 | admin_count ≤ 1 時拋 ValueError |
| Admin 路由保護 | `utils/auth.py` `require_admin()` | 需要有效 admin token 或 user.role=="admin" |
| 前端 /admin 路由守衛 | `router/index.js` L73-80 | 非 admin 導向 `/` |
| 訂閱路由守衛 | `router/index.js` L83-97 | 無訂閱時導向 `/subscription` |

---

## 5. Auth 持久化（不可修改 key 名稱）

| localStorage Key | 用途 |
|-----------------|------|
| `futures_auth_token` | JWT token（30 天有效） |
| `futures_auth_user` | 使用者資料快取（JSON） |
| `futures_admin_token` | Admin token（8 小時有效） |

---

## 6. 訂閱層級（不可修改代碼邏輯）

- 資料庫表 `subscription_tiers`（seed 於 `db/database.py`）
- tier_code：`lite` / `premium` / `pro`
- 前端路由守衛判斷：`['lite', 'premium', 'pro'].includes(sub?.tier_code)` 且 status === 'active'
- 訂閱功能由 `feature_flags` JSON 欄位控制（admin 可動態修改，無需改程式碼）

---

## 7. Region 時區設定（下拉選單）

- **設定檔**：`backend/app/services/simulation_config_generator.py`
- **常數名稱**：`REGION_TIMEZONE_CONFIGS`（`api/simulation.py` 中 import 此常數）
- **預設值**：`region_code = data.get('region_code', 'china')`（prepare 端點 L475）
- **支援 region**：china, taiwan, usa_et, usa_pt, japan, europe_ce（以及更多）
- 前端 region 選單 → `Step2EnvSetup.vue`（選項不可刪減）

---

## 8. Zep 整合點

| 服務 | 檔案 | 用途 |
|------|------|------|
| GraphBuilderService | `services/graph_builder.py` | 建立 Zep Graph、上傳文本 Episode、設定本體 |
| ZepEntityReader | `services/zep_entity_reader.py` | 從 Zep Graph 讀取並過濾實體 |
| ZepToolsService | `services/zep_tools.py` | Report Agent 調用：搜尋圖譜、取得統計 |
| ZepGraphMemoryUpdater | `services/zep_graph_memory_updater.py` | 模擬執行中將 Agent 動作寫回 Zep |
| zep_paging | `utils/zep_paging.py` | Zep API 分頁輔助函式 |
| **環境變數**：`ZEP_API_KEY` | Config | 必填（缺失僅警告，不阻止啟動） |

---

## 9. GraphRAG / DashScope 整合點

| 服務 | 說明 |
|------|------|
| ReportAgent | `services/report_agent.py`：以 ZepToolsService 做 tool-call，實現 GraphRAG 報告生成 |
| LLMClient | `utils/llm_client.py`：統一 OpenAI-compatible 格式，支援所有 provider |
| DashScope | provider key = `qwen`，base_url = `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| OntologyGenerator | `services/ontology_generator.py`：呼叫 LLM 生成本體定義 |
| OasisProfileGenerator | `services/oasis_profile_generator.py`：呼叫 LLM 生成 Agent Profile |
| SimulationConfigGenerator | `services/simulation_config_generator.py`：呼叫 LLM 生成模擬參數 |

---

## 10. 前端路由（Vue Router）

| Path | Component | 保護 |
|------|-----------|------|
| `/` | Home.vue | 無 |
| `/subscription` | SubscriptionView.vue | 無 |
| `/launch` | SimulateLaunchView.vue | `requiresSubscription: true` |
| `/process/:projectId` | MainView.vue | 無 |
| `/simulation/:simulationId` | SimulationView.vue | 無 |
| `/simulation/:simulationId/start` | SimulationRunView.vue | 無 |
| `/report/:reportId` | ReportView.vue | 無 |
| `/interaction/:reportId` | InteractionView.vue | 無 |
| `/admin` | AdminView.vue | is_admin 或 futures_admin_token |

---

## 11. 前端 Store

| 檔案 | 說明 |
|------|------|
| `store/auth.js` | `authState` reactive 物件：token/user/providers/loading/error；localStorage 持久化 |
| `store/pendingUpload.js` | 暫存上傳待處理狀態 |

---

## 12. 環境變數（不可重命名）

| 變數 | 用途 |
|------|------|
| `SECRET_KEY` | JWT / token 簽名 |
| `ZEP_API_KEY` | Zep Cloud |
| `STRIPE_SECRET_KEY` | Stripe API |
| `STRIPE_WEBHOOK_SECRET` | Webhook 簽名驗證 |
| `STRIPE_PUBLISHABLE_KEY` | Admin UI 顯示（非必填） |
| `DATABASE_URL` | 空 = SQLite；設定 = PostgreSQL |
| `FLASK_HOST` / `FLASK_PORT` / `FLASK_DEBUG` | Flask 啟動參數 |
| `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL_NAME` | 預設 LLM（次要，用戶自設為主） |
| `SITE_URL` | Zeabur 反向代理後的公開 domain（webhook URL 組裝） |
| `USER_DATA_DIR` | 上傳/模擬資料目錄 |
| `SIM_MAX_AGENTS` / `SIM_MAX_ROUNDS` / `LLM_CONCURRENCY_LIMIT` 等 | 模擬資源限制 |

---

## 13. 部署設定（不可修改）

| 檔案 | 用途 |
|------|------|
| `zbpack.json` | Zeabur 部署設定 |
| `Dockerfile` | 容器映像建構 |
| `docker-compose.yml` | 本地開發容器組合 |
| `.dockerignore` | Docker 忽略清單 |

---

## 14. 測試狀態

- **現有測試**：無（專案目錄中無 test_*.py 或 *.test.js）
- **Smoke tests**：將建立於 `backend/tests/test_smoke.py`，涵蓋核心 API 端點的狀態碼驗證
- **測試工具**：pytest（已在 pyproject.toml dev dependencies 中）
