"""
Graphiti 組裝層：依使用者 BYOK LLM 設定動態組裝 Graphiti 實例（LLM client /
embedder / reranker），並提供正式建圖前的最小可用性預檢（precheck_llm）。

背景：本專案原本用 Zep Cloud 當圖譜引擎，改為自架 FalkorDB + Graphiti 後，圖譜建構
所需的 LLM 抽取與 embedding 一律使用使用者自己在帳號設定裡填的模型/金鑰（BYOK），
不再依賴任何全域 LLM 環境變數。FalkorDB 連線資訊（FALKORDB_HOST/PORT/PASSWORD）
才是平台層級設定，跟使用者的 LLM 選擇無關。

安全要求：本模組任何 log/例外訊息都不得輸出使用者的 api_key 明文，一律先經過
redact_secrets() 遮罩。
"""

import math
import os
import re
from typing import Dict, List, Optional, Tuple

# 必須在任何 graphiti_core import 之前設定：graphiti-core 內建匿名使用統計
# 遙測（graphiti_core/telemetry/telemetry.py），預設開啟，會在背景執行緒透過
# PostHog SDK 把事件送到第三方伺服器（us.i.posthog.com）。Stage 5 端到端測試
# 對真實 FalkorDB + Gemini 實測到：完整跑過 add_text_batches 等多次操作後，
# 主執行緒的 asyncio event loop 會卡在 _poll()/select() 動彈不得，用
# faulthandler 抓到的 stack trace 顯示背景多了一條 posthog.consumer 執行緒
# ——這條路徑本專案完全用不到，也不該讓使用者的操作資料（哪怕是匿名化的）
# 未經同意送到第三方，直接關掉。graphiti_core 自己在 pytest 環境下也會自動
# 關閉遙測（is_telemetry_enabled() 檢查 'pytest' in sys.modules），代表這本來
# 就是官方認可「會干擾程式執行」而需要關閉的機制，這裡用官方支援的環境變數
# 全域關閉，不是只在測試腳本關。用 setdefault 而不是強制覆寫，保留使用者
# 日後如果真的想要開啟的彈性（不太可能，但不剝奪這個選項）。
os.environ.setdefault("GRAPHITI_TELEMETRY_ENABLED", "false")

from pydantic import BaseModel

from falkordb.asyncio import FalkorDB
from google import genai
from google.genai import types as genai_types
from graphiti_core import Graphiti
from openai import AsyncOpenAI
from graphiti_core.cross_encoder.client import CrossEncoderClient
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.embedder.client import EmbedderClient
from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.client import LLMClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.gemini_client import GeminiClient
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.prompts.models import Message

from ..utils.locale import get_locale, t
from .graph_localization import apply_language_directive, graph_language_directive
from .structured_output_guard import apply_structured_output_guard
from ..utils.logger import get_logger

logger = get_logger('futuresreport.graphiti_factory')


# ---------------------------------------------------------------------------
# 供應商映射表（集中定義；日後新增/調整供應商只需要改這裡）
# ---------------------------------------------------------------------------

# 目前確認沒有 embedding API 的供應商：precheck_llm 直接擋下，不浪費一次 LLM 呼叫。
# 依據調查時各家公開 API 文件判斷；供應商日後推出 embedding 服務時需要更新這個集合。
NO_EMBEDDING_PROVIDERS = frozenset({"anthropic", "deepseek", "kimi"})

# 各供應商的預設 embedding 模型名。gemini 走原生 GeminiEmbedder；其餘一律走
# OpenAIEmbedder 打各自的 OpenAI 相容 /embeddings 端點（沿用使用者設定的 base_url）。
EMBEDDING_MODEL_MAP: Dict[str, str] = {
    "openai": "text-embedding-3-small",
    # "text-embedding-001" 這個舊名稱在目前的 Gemini API 版本上已經 404
    # （Stage 5 端到端測試用 client.models.list() 對真實帳號驗證過，
    # 目前 embedContent 支援的正確名稱是 gemini-embedding-001，
    # 768 維在該模型的官方建議維度清單內，跟 GRAPHITI_EMBEDDING_DIM 相容）。
    "gemini": "gemini-embedding-001",
    "qwen": "text-embedding-v3",
    "glm": "embedding-3",
    "minimax": "embo-01",
    "mistral": "mistral-embed",
    "nvidia": "nvidia/nv-embedqa-e5-v5",
}

# 已知能穩定支援原生 json_schema 結構化輸出的供應商；其餘一律走 json_object
# 降級模式（schema 注入 prompt，由 OpenAIGenericClient 內建處理）。這與
# app/utils/llm_client.py 現有的 _JSON_MODE_PROVIDERS 判斷邏輯呼應，是已在
# 生產環境驗證過的組合，先保守只信任 openai 走原生 json_schema。
JSON_SCHEMA_NATIVE_PROVIDERS = frozenset({"openai"})

# 所有 BYOK 使用者共用同一個 FalkorDB 執行個體與 database（單實例多租戶，
# 只靠 group_id 分區），因此每個 embedder 的輸出維度統一為 768（Gemini
# text-embedding-001/gemini-embedding 系列的官方推薦低維度之一，也是目前支援
# 清單中最小的原生維度），以降低不同專案用不同供應商建圖時撞上索引維度不符
# 的風險。已核准（2026-07-18），附帶三個條件，記錄如下：
#
# 1) 維度收斂的優先順序（見 _build_llm_and_embedder / _DimensionAwareOpenAIEmbedder）：
#    優先用供應商 API 端的維度參數，讓伺服器直接回傳目標維度的正規化向量——
#    OpenAI text-embedding-3-* 系列原生支援 `dimensions=` 參數；Gemini
#    的 GeminiEmbedder（graphiti_core 內建）本來就會把 embedding_dim 透過
#    `output_dimensionality` 傳給 API，同樣是伺服器端處理，這裡不用再包一層。
#    只有不支援維度參數的 OpenAI 相容供應商（qwen/glm/minimax/mistral/nvidia
#    等）才會落到客戶端截斷 fallback，且截斷後一律做 L2 重新正規化
#    （見 _l2_normalize）。
#
# 2) 品質風險：客戶端截斷只對「以 Matryoshka Representation Learning 方式訓練」
#    的 embedding 模型是安全的（截斷後的子向量仍保留原始向量的相對語意距離）。
#    OpenAI text-embedding-3 系列公開文件承諾 MRL 特性；但上面列的第三方
#    OpenAI 相容供應商，官方文件均未明確聲明其模型具備 MRL 特性——對這些供應商
#    做截斷是「盡力而為」，語意保真度可能下降，但至少維度一致、不會在寫入/
#    查詢時直接出錯。若某供應商被證實不具 MRL 特性，這裡的截斷等同於粗暴丟棄
#    後半段向量分量，語意品質下降幅度未知，需要靠使用者實際搜尋品質回饋來
#    發現，目前沒有自動化手段偵測。
#
# 3) 遷移代價：這是「全域統一維度」，不是「per-project 維度」。若日後要讓每個
#    project 依供應商原生維度各自建圖（避免截斷/品質問題），FalkorDB 的向量
#    索引結構需要重建（既有 group_id 底下已寫入的 768 維向量無法就地升級到
#    別的維度），代表要嘛對舊專案做一次性重新 embedding 全量重建圖譜，要嘛
#    接受新舊專案並存兩種維度 schema 的複雜度。目前判斷維護單一固定維度的
#    簡單性效益大於這個未來遷移成本，但這裡明確記錄下來供日後升級評估。
GRAPHITI_EMBEDDING_DIM = 768

# 已確認支援 OpenAI 風格 `dimensions=` 請求參數的供應商（見上方條件 1）。
# 目前只信任 openai 本家的 text-embedding-3-small/large；其餘 OpenAI 相容
# 供應商未證實支援這個參數，一律落到客戶端截斷 + L2 重新正規化 fallback。
SERVER_SIDE_DIM_PROVIDERS = frozenset({"openai"})

DEFAULT_FALKORDB_HOST = "localhost"
DEFAULT_FALKORDB_PORT = 6379
DEFAULT_LLM_CONCURRENCY_LIMIT = 6

# FalkorDriver 自己組裝的 FalkorDB client 沒有設 socket_timeout /
# socket_connect_timeout（底層 redis-py 預設值是 None，代表不設限）。Stage 5
# 端到端測試對真實遠端 FalkorDB 實測到：在一次測試流程中陸續開了十來個
# FalkorDriver（本專案「每次操作現建一個新 driver」的既定設計，見
# build_graphiti() 的說明）之後，後續某次查詢會直接卡住、完全沒有任何例外或
# 逾時，一路等到手動砍掉進程——很可能是伺服器端連線數到了某個門檻後不主動
# 拒絕新連線，只是不回應，而客戶端沒有 socket 逾時就會無限期等下去。
# 這裡改用 FalkorDriver 官方支援的 falkor_db 參數（見它的建構子：「An existing
# FalkorDB instance to use instead of creating a new one」），自己組裝一個有
# 設定逾時的 FalkorDB client 傳進去，而不是去 patch graphiti-core 原始碼。
# connect_timeout 設短（純 TCP/RESP 握手，正常應該一兩秒內完成）；
# socket_timeout 設得比較寬鬆（涵蓋單次 Cypher 查詢，正常查詢是毫秒級，但
# 保留餘裕給大型查詢），兩者都遠短於「無限期卡住」，確保任何連線/伺服器端
# 問題都會在合理時間內變成明確的例外，而不是靜默掛住。
FALKORDB_SOCKET_CONNECT_TIMEOUT = 10
FALKORDB_SOCKET_TIMEOUT = 30

# Gemini 的「thinking」系列模型（3.x 世代，含尚未被已安裝版本 graphiti-core
# 收錄進 GEMINI_MODEL_MAX_TOKENS 查表的較新模型如 gemini-3.5-flash）會把
# max_output_tokens 預算的一部分消耗在內部思考 token（thoughts_token_count）
# 上，實際可見輸出只拿到剩下的部分。graphiti-core 對「已知」的 3.x 系列模型
# （gemini-3-pro-preview / gemini-3-flash-preview）已經把預設值提高到 65536；
# 對不在查表內的模型則退回通用的 8192（見 graphiti_core.llm_client.gemini_client
# 的 GEMINI_MODEL_MAX_TOKENS / DEFAULT_GEMINI_MAX_TOKENS）。8192 對本專案的
# chunk 大小（預設 500 字）通常夠用，但既然同一世代的其他模型都拿到 65536，
# 這裡透過 GeminiClient 官方支援的建構子參數 max_tokens 直接對齊，不去 patch
# 函式庫原始碼，也不需要為每個新模型名稱維護自己的一份查表。
# 這個常數只影響「沒有在呼叫端顯式傳入 max_tokens」的呼叫（例如 extract_nodes/
# dedupe_nodes）；edge 抽取本身在 graphiti-core 內部就有自己的顯式
# extract_edges_max_tokens=16384，不受這裡影響。
GEMINI_LLM_MAX_TOKENS = 65536

# 單次 LLM / embedding HTTP 請求的逾時（秒）。google-genai 預設「不設逾時」：
# 2026-10-29 正式環境實測，一次建圖在第 107 塊時某個 Gemini 請求再也沒有回應，
# 整個建圖任務就此無聲卡住一個多小時、CPU 閒置、沒有任何例外。設了逾時之後，
# 卡住的請求會變成例外，交給 graphiti-core 的重試（GeminiClient 最多 2 次）與
# 下面的 HTTP 層重試處理。OpenAI SDK 預設是 600 秒，這裡一併縮短成同一個值。
LLM_REQUEST_TIMEOUT_SECONDS = int(os.environ.get("GRAPHITI_LLM_TIMEOUT_SECONDS", "180"))
# HTTP 層對暫時性錯誤（429 / 5xx）的自動重試次數（含第一次）。
LLM_HTTP_RETRY_ATTEMPTS = 4


class UnsupportedProviderError(ValueError):
    """使用者選擇的供應商不支援圖譜建構所需的 embedding。"""


class EmbeddingMismatchError(ValueError):
    """目前使用者的 LLM 設定跟這個 graph_id 建圖時記錄的 embedding 供應商/模型不一致。"""


def get_embedding_identity(provider: str) -> str:
    """回傳這個供應商實際會用的 embedding 模型名，供專案 metadata 記錄與比對使用
    （見 app/models/project.py 的 Project.embedding_provider/embedding_model）。"""
    provider = (provider or "").strip().lower()
    return EMBEDDING_MODEL_MAP.get(provider, EMBEDDING_MODEL_MAP["openai"])


def check_embedding_consistency(
    user_llm_config: Dict[str, str],
    stored_provider: Optional[str],
    stored_model: Optional[str],
) -> Tuple[bool, Optional[str]]:
    """比對目前使用者的 LLM 設定，與這個 graph_id 建圖時記錄在專案 metadata 的
    embedding 供應商/模型是否一致。不同供應商（甚至同供應商不同模型）的向量
    空間互不相容，同維度不代表同語意——用錯供應商搜尋只會得到語意不相關但
    維度正確、不會報錯的「安靜的錯誤結果」，比直接報錯更危險，所以在所有
    向量相關操作前都要先擋這一關。

    stored_provider/stored_model 為 None（例如舊專案在這個欄位補上之前就已建圖）
    時視為通過——沒有記錄就無從比對，不能因為遷移時序問題擋住舊資料。
    """
    if not stored_provider or not stored_model:
        return True, None

    provider = (user_llm_config.get("provider") or "").strip().lower()
    if provider == stored_provider and get_embedding_identity(provider) == stored_model:
        return True, None

    return False, t(
        "graphiti.embeddingMismatch",
        provider=stored_provider,
        model=stored_model,
    )


def enforce_embedding_consistency(user_llm_config: Dict[str, str], graph_id: str) -> None:
    """向量相關操作（搜尋、模擬記憶更新、增量寫入）前的一致性關卡：查出 graph_id
    對應的專案，比對其記錄的 embedding 供應商/模型，不一致就拋出
    EmbeddingMismatchError。找不到專案時放行（沒有 metadata 就無從比對）。

    延後 import ProjectManager 是為了避免 app/services 與 app/models 之間
    在模組載入時序上的潛在循環（models/project.py 目前不 import 任何 services，
    這裡延後只是額外保守，不是必要條件）。
    """
    from ..models.project import ProjectManager

    project = ProjectManager.find_project_by_graph_id(graph_id)
    if project is None:
        return

    ok, reason = check_embedding_consistency(
        user_llm_config, project.embedding_provider, project.embedding_model
    )
    if not ok:
        raise EmbeddingMismatchError(reason)


# ---------------------------------------------------------------------------
# 密鑰遮罩：任何要 log 或回傳給使用者的錯誤文字，一律先過這道
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),      # Anthropic（放前面，避免被下面的 sk- 規則搶先局部匹配）
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),          # OpenAI / DeepSeek / Mistral / Moonshot 等常見風格
    re.compile(r"AIzaSy[A-Za-z0-9_-]{10,}"),       # Google API key 風格
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{10,}"),   # Authorization header 殘留
]


def redact_secrets(text: str) -> str:
    """把文字中看起來像 API key 的片段遮罩掉，供任何要 log 或回傳給使用者的例外
    訊息使用。這是縱深防禦：目前已知的 SDK 例外訊息不會回顯完整 key，但供應商
    行為可能改變，統一在這裡過濾比逐處小心可靠。"""
    if not text:
        return text
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _l2_normalize(vector: List[float]) -> List[float]:
    """把向量重新正規化為單位長度。截斷一個未知是否為 MRL 訓練的 embedding
    向量後，其長度不再是 1，會讓 cosine similarity 搜尋出現系統性偏差；
    L2 正規化是最低限度的補救（無法恢復截斷丟失的語意資訊，但至少讓向量
    長度重新一致，避免長度偏差蓋過語意相似度的訊號）。"""
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return vector
    return [x / norm for x in vector]


class _DimensionAwareOpenAIEmbedder(OpenAIEmbedder):
    """在 OpenAIEmbedder 之上加一層維度收斂策略（見 GRAPHITI_EMBEDDING_DIM
    旁的條件 1 註解）：

    - use_server_side_dim=True（目前僅 openai 本家）：呼叫 embeddings.create()
      時帶入 `dimensions=`，由伺服器直接回傳目標維度的正規化向量，不做任何
      客戶端後處理。
    - use_server_side_dim=False（其餘 OpenAI 相容供應商）：沿用父類別的客戶端
      截斷（`[:embedding_dim]`），但截斷後再做 L2 重新正規化。
    """

    def __init__(self, config: OpenAIEmbedderConfig, use_server_side_dim: bool, client: Optional[AsyncOpenAI] = None):
        super().__init__(config=config, client=client)
        self._use_server_side_dim = use_server_side_dim

    async def create(self, input_data) -> List[float]:
        if not self._use_server_side_dim:
            return _l2_normalize(await super().create(input_data))

        result = await self.client.embeddings.create(
            input=input_data,
            model=self.config.embedding_model,
            dimensions=self.config.embedding_dim,
        )
        return result.data[0].embedding

    async def create_batch(self, input_data_list: List[str]) -> List[List[float]]:
        if not self._use_server_side_dim:
            vectors = await super().create_batch(input_data_list)
            return [_l2_normalize(v) for v in vectors]

        result = await self.client.embeddings.create(
            input=input_data_list,
            model=self.config.embedding_model,
            dimensions=self.config.embedding_dim,
        )
        return [embedding.embedding for embedding in result.data]


class NoOpRerankerClient(CrossEncoderClient):
    """不做任何重排序，原樣按輸入順序回傳（配一個遞減的假分數以滿足介面約定）。

    決策依據：Graphiti 預設的 OpenAIRerankerClient 需要額外一把 OpenAI key（違反
    BYOK 單一金鑰原則），BGERerankerClient 需要本地 sentence-transformers + 下載
    reranker 模型（跟專案既有的低資源 K3s 保護原則衝突）。改用不依賴 cross-encoder
    的 RRF 系搜尋 recipe + 這個 no-op 實作；之後若要換更好的 reranker，只需要改
    build_graphiti() 裡組裝 cross_encoder 的這一行。
    """

    async def rank(self, query: str, passages: list) -> list:
        total = max(len(passages), 1)
        return [(passage, 1.0 - i / total) for i, passage in enumerate(passages)]


# Qwen 3.5 起的混合推理模型（qwen3.5 / 3.6 / 3.7 / 3.8 的 flash、plus、max）
# 預設開啟「思考」（阿里雲官方文件；舊的 qwen-plus / qwen-flash 預設關閉）。
# 2026-10-30 正式環境：qwen3.8-flash 建圖時每個請求都先產生長篇思考、單次呼叫
# 超過 2 分鐘，第一批 20 塊卡在 15% 動不了；思考 token 也按輸出計費。
# Graphiti 的抽取/去重是短小的結構化輸出，不需要思考，所以對建圖用的 client
# 關閉它。「純思考」模型（官方列出的 qwen3.8-2.4t-a95b、名稱含 thinking 的）
# 不能關閉，送了反而會被拒，所以排除。
_QWEN_THINKING_ONLY_MARKERS = ("thinking", "2.4t")


def _qwen_thinking_can_be_disabled(provider: str, model: str) -> bool:
    name = (model or "").lower()
    return provider == "qwen" and not any(marker in name for marker in _QWEN_THINKING_ONLY_MARKERS)


def _disable_thinking(openai_client: AsyncOpenAI) -> None:
    """Make every chat request from this client send enable_thinking=false
    (DashScope's switch for hybrid-thinking models). Embedding calls are untouched."""
    completions = openai_client.chat.completions
    original_create = completions.create

    async def create(*args, **kwargs):
        extra_body = dict(kwargs.pop("extra_body", None) or {})
        extra_body.setdefault("enable_thinking", False)
        return await original_create(*args, extra_body=extra_body, **kwargs)

    completions.create = create


def get_llm_concurrency_limit() -> int:
    """讀取 LLM 並發限制環境變數（沿用既有 LLM_CONCURRENCY_LIMIT 慣例），用來覆蓋
    Graphiti 的 SEMAPHORE_LIMIT（見 Graphiti(max_coroutines=...)），不需要自建
    asyncio.Semaphore。"""
    raw = os.environ.get("LLM_CONCURRENCY_LIMIT", str(DEFAULT_LLM_CONCURRENCY_LIMIT))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_LLM_CONCURRENCY_LIMIT
    return value if value >= 1 else DEFAULT_LLM_CONCURRENCY_LIMIT


def _build_llm_and_embedder(
    provider: str,
    api_key: str,
    model: str,
    base_url: str,
) -> Tuple[LLMClient, EmbedderClient]:
    """供應商判斷邏輯集中在這裡：gemini 走原生 client，其餘一律走 OpenAI 相容
    generic client。"""
    if provider == "gemini":
        # LLM 與 embedder 共用一個帶逾時與重試設定的 genai.Client（兩者的
        # 建構子都官方支援傳入 client；不傳的話各自 new 一個沒有逾時的 client）。
        gemini_client = genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(
                timeout=LLM_REQUEST_TIMEOUT_SECONDS * 1000,  # 毫秒
                retry_options=genai_types.HttpRetryOptions(
                    attempts=LLM_HTTP_RETRY_ATTEMPTS,
                    http_status_codes=[408, 429, 500, 502, 503, 504],
                ),
            ),
        )
        llm_client = GeminiClient(
            # small_model=model（而非留空、吃 graphiti-core 內建的 DEFAULT_SMALL_MODEL）：
            # graphiti-core 對 model_size=ModelSize.small 的呼叫（屬性抽取、邊/節點
            # 去重比對、時間戳抽取等）預設會用它自己寫死的「小模型」名稱，這個名稱
            # 不是使用者的 BYOK 選擇，而且已證實會過期／被供應商下架（Stage 5 端到端
            # 測試實測 gemini-2.5-flash-lite 回傳 404 "no longer available to new
            # users"）。統一釘死成使用者自己配置的主模型，確保所有呼叫都在使用者
            # 帳號真正有權限的模型上執行，不依賴函式庫內建、可能過時的預設值。
            config=LLMConfig(api_key=api_key, model=model, small_model=model),
            max_tokens=GEMINI_LLM_MAX_TOKENS,
            client=gemini_client,
        )
        # GeminiEmbedder（graphiti_core 內建）本來就把 embedding_dim 透過
        # `output_dimensionality` 傳給 embed_content API，是伺服器端處理，
        # 不需要在這裡包一層截斷/正規化 wrapper（見條件 1 註解）。
        embedder = GeminiEmbedder(
            config=GeminiEmbedderConfig(
                api_key=api_key,
                embedding_model=EMBEDDING_MODEL_MAP["gemini"],
                embedding_dim=GRAPHITI_EMBEDDING_DIM,
            ),
            client=gemini_client,
        )
        return llm_client, embedder

    structured_output_mode = (
        "json_schema" if provider in JSON_SCHEMA_NATIVE_PROVIDERS else "json_object"
    )
    # 同 gemini 分支：自己組裝帶逾時/重試的 AsyncOpenAI client 傳進去（LLM 與
    # embedder 共用），不吃 SDK 預設的 600 秒逾時。
    openai_client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url or None,
        timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        max_retries=LLM_HTTP_RETRY_ATTEMPTS - 1,
    )
    if _qwen_thinking_can_be_disabled(provider, model):
        _disable_thinking(openai_client)
    llm_client = OpenAIGenericClient(
        # small_model=model：同 gemini 分支的理由——graphiti-core 對
        # model_size=ModelSize.small 呼叫預設會用它自己寫死的 DEFAULT_SMALL_MODEL
        # （目前是 'gpt-4.1-nano'），這是 OpenAI 專屬模型名，對 qwen/glm/minimax/
        # mistral/nvidia 等第三方「OpenAI 相容」端點幾乎必然不存在、會直接 404。
        # 統一釘死成使用者自己配置的主模型，不依賴函式庫內建、假設用戶用真正
        # OpenAI 帳號的預設值。
        config=LLMConfig(api_key=api_key, model=model, small_model=model, base_url=base_url),
        structured_output_mode=structured_output_mode,
        client=openai_client,
    )
    embedding_model = EMBEDDING_MODEL_MAP.get(provider, EMBEDDING_MODEL_MAP["openai"])
    embedder = _DimensionAwareOpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=api_key,
            base_url=base_url,
            embedding_model=embedding_model,
            embedding_dim=GRAPHITI_EMBEDDING_DIM,
        ),
        use_server_side_dim=provider in SERVER_SIDE_DIM_PROVIDERS,
        client=openai_client,
    )
    return llm_client, embedder


def build_graphiti(user_llm_config: Dict[str, str], graph_id: Optional[str] = None) -> Graphiti:
    """依使用者 BYOK LLM 設定 + FalkorDB 平台設定組裝一個 Graphiti 實例。

    FalkorDB 的多租戶隔離不是「單一共用圖、靠 WHERE group_id 篩選」——
    graphiti-core 的 add_episode() 內部會在 group_id 跟 driver 當下的
    `_database` 不同時，把 driver clone 成 `database=group_id`（見
    graphiti_core.graphiti.Graphiti.add_episode 裡的
    `self.driver = self.driver.clone(database=group_id)`），也就是說每個
    group_id 實際上對應 FalkorDB 裡一個「獨立命名的圖」，不是同一張圖裡的
    一個篩選條件。這件事在 Stage 2/3 設計時沒有對著真實 FalkorDB 驗證過，
    Stage 5 端到端測試對真實遠端 FalkorDB 實測才發現：write 端經
    add_episode() 的內部 clone 邏輯寫進了名為 graph_id 的圖，但如果 read 端
    （fetch_all_nodes / search_ 等）用一個沒有指定 database 的全新 driver
    （落到預設的 'default_db'），就會查到完全不同、空的圖，造成「寫入回報
    成功、但讀回是空的」。

    修法：這裡直接在建構 FalkorDriver 時就把 database 設成 graph_id，讓
    write 和 read 用的 driver 從一開始就指向同一張圖（graph_id 不是 None
    時）。這樣 add_episode() 內部「group_id != self.driver._database」的
    判斷會是 False，clone 變成無操作，行為完全一致。

    Args:
        user_llm_config: {"provider", "model", "base_url", "api_key"}
            （見 UserManager.get_llm_config()）。
        graph_id: 這個 Graphiti 實例要操作的圖譜 ID，同時決定 FalkorDB 的
            database 名稱。省略時退回 FalkorDriver 的預設 database
            （'default_db'）——只適合純粹的連線自檢（不涉及任何具體圖的
            讀寫）等場景，正式的建圖/讀取/搜尋一律要傳入實際的 graph_id。

    Raises:
        UnsupportedProviderError: 使用者選擇的供應商不支援圖譜建構所需的 embedding。
            呼叫端應該先呼叫 precheck_llm() 擋掉這個情況，這裡的檢查是防禦性的。
    """
    provider = (user_llm_config.get("provider") or "").strip().lower()
    if provider in NO_EMBEDDING_PROVIDERS:
        raise UnsupportedProviderError(t("graphiti.noEmbeddingSupport", provider=provider))

    api_key = user_llm_config.get("api_key") or ""
    model = user_llm_config.get("model") or ""
    base_url = user_llm_config.get("base_url") or ""

    llm_client, embedder = _build_llm_and_embedder(provider, api_key, model, base_url)
    # 圖譜內容（實體名稱、摘要、關係事實）跟著介面語言走：建圖 / 模擬記憶更新的
    # 背景執行緒都已經 set_locale()，這裡取到的就是發起請求的使用者語言。
    apply_language_directive(llm_client, graph_language_directive(get_locale()))
    # 結構化輸出驗證：模型回傳 JSON Schema 本身或格式錯誤時，附上更正說明重問（見 structured_output_guard）。
    apply_structured_output_guard(llm_client)

    falkor_client = FalkorDB(
        host=os.environ.get("FALKORDB_HOST", DEFAULT_FALKORDB_HOST),
        port=int(os.environ.get("FALKORDB_PORT", str(DEFAULT_FALKORDB_PORT))),
        password=os.environ.get("FALKORDB_PASSWORD") or None,
        socket_connect_timeout=FALKORDB_SOCKET_CONNECT_TIMEOUT,
        socket_timeout=FALKORDB_SOCKET_TIMEOUT,
    )
    driver = FalkorDriver(
        falkor_db=falkor_client,
        database=graph_id or "default_db",
    )

    logger.info(f"組裝 Graphiti 實例: graph_id={graph_id or '(unscoped)'}, provider={provider}, model={model}")

    return Graphiti(
        graph_driver=driver,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=NoOpRerankerClient(),
        max_coroutines=get_llm_concurrency_limit(),
    )


# ---------------------------------------------------------------------------
# 預檢：抽取（結構化輸出）+ embedding 各發一次最小測試呼叫
# ---------------------------------------------------------------------------

class _PrecheckSchema(BaseModel):
    ok: bool


def _classify_error(exc: Exception) -> str:
    """把底層例外轉成不含金鑰的中文摘要，區分配額/認證/其他。"""
    status_code = getattr(exc, "status_code", None)
    text = redact_secrets(str(exc))
    lower_text = text.lower()

    if status_code == 429 or "resource_exhausted" in lower_text or "rate limit" in lower_text:
        return t("graphiti.precheckQuotaError", detail=text[:150])
    if (
        status_code == 401
        or "authentication" in lower_text
        or "invalid api key" in lower_text
        or "permission" in lower_text
        or "unauthorized" in lower_text
    ):
        return t("graphiti.precheckAuthError", detail=text[:150])
    return t("graphiti.precheckGenericError", detail=text[:150])


async def precheck_llm(user_llm_config: Dict[str, str]) -> Tuple[bool, Optional[str]]:
    """建圖前的最小可用性預檢：確認使用者的 LLM 設定同時能做結構化輸出抽取與
    embedding。任何失敗都回傳 (False, 明確原因)；成功回傳 (True, None)。

    絕不在任何 log/例外訊息中輸出 api_key 明文（見 redact_secrets）。
    """
    provider = (user_llm_config.get("provider") or "").strip().lower()

    if provider in NO_EMBEDDING_PROVIDERS:
        return False, t("graphiti.noEmbeddingSupport", provider=provider)

    api_key = user_llm_config.get("api_key") or ""
    model = user_llm_config.get("model") or ""
    base_url = user_llm_config.get("base_url") or ""

    try:
        llm_client, embedder = _build_llm_and_embedder(provider, api_key, model, base_url)
    except Exception as e:
        logger.warning(
            f"LLM 預檢初始化失敗: provider={provider}, model={model}, error={redact_secrets(str(e))}"
        )
        return False, _classify_error(e)

    try:
        await llm_client.generate_response(
            messages=[
                Message(
                    role="system",
                    content="You only respond with JSON matching the requested schema.",
                ),
                Message(
                    role="user",
                    content="Return a JSON object with a single boolean field 'ok' set to true.",
                ),
            ],
            response_model=_PrecheckSchema,
            # 1000（不是 50）：Gemini 的 thinking 系列模型會把部分 max_output_tokens
            # 預算耗在內部推理 token（thoughts_token_count）上，太小的預算會讓
            # 可見輸出被截斷為空、precheck 誤判為失敗（Stage 5 端到端測試實際
            # 診斷出的根因：gemini-3.5-flash 用 50 tokens 時 46 個被推理耗盡，
            # finish_reason=MAX_TOKENS，response.text 為 None）。1000 對這個
            # 極簡的單欄位 schema 有充足餘裕（實測 2000 時僅用掉約 153 tokens）。
            max_tokens=1000,
        )
    except Exception as e:
        logger.warning(
            f"LLM 預檢（結構化輸出）失敗: provider={provider}, model={model}, "
            f"error={redact_secrets(str(e))}"
        )
        return False, _classify_error(e)

    try:
        await embedder.create(input_data="ping")
    except Exception as e:
        logger.warning(
            f"LLM 預檢（embedding）失敗: provider={provider}, model={model}, "
            f"error={redact_secrets(str(e))}"
        )
        return False, _classify_error(e)

    logger.info(f"LLM 預檢通過: provider={provider}, model={model}")
    return True, None
