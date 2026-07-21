"""
Graphiti + FalkorDB 端到端整合測試（Stage 5）

刻意不叫 test_*.py：這是要手動執行、會打真實 FalkorDB 與真實 LLM API 的腳本，
不該被 `pytest tests/` 自動蒐集執行（會因缺少環境變數而失敗，且每次執行都會
消耗真實 LLM 額度）。

全程走與生產相同的服務層路徑（GraphBuilderService / ZepEntityReader /
ZepToolsService / ZepGraphMemoryUpdater），不繞過去直接呼叫 Graphiti，藉此驗證
Stage 3 遷移後這幾個模組的真實行為，而不只是 mock 過的單元測試。

安全規則（嚴格遵守）：
- 連線資訊與金鑰一律從環境變數讀取，程式內不寫死任何值
- 任何要印出的錯誤訊息都先過 redact_secrets()
- 不把任何金鑰寫進檔案（本腳本產生的所有本地檔案都在系統 temp 目錄下，且只
  存放專案的非敏感 metadata——project.json 裡本來就不含 api_key，見
  app/models/project.py 的 Project dataclass 欄位）

執行方式（需先在終端 export 好下列環境變數）：
    export FALKORDB_HOST=...
    export FALKORDB_PORT=...
    export FALKORDB_PASSWORD=...
    export TEST_LLM_PROVIDER=...
    export TEST_LLM_API_KEY=...
    export TEST_LLM_MODEL=...
    export TEST_LLM_BASE_URL=...      # 可選，原生 Gemini 不需要
    cd backend && python tests/e2e_graphiti_falkordb.py
"""

from __future__ import annotations

import faulthandler
import os
import sys
import time
import uuid
import tempfile
import traceback
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# 环境变量校验（在 import 任何 app 模块之前先做，快速失败）
# ---------------------------------------------------------------------------

REQUIRED_ENV_VARS = [
    "FALKORDB_HOST",
    "FALKORDB_PORT",
    "FALKORDB_PASSWORD",
    "TEST_LLM_PROVIDER",
    "TEST_LLM_API_KEY",
    "TEST_LLM_MODEL",
]


def _fail_fast(message: str) -> None:
    print(f"\n[FATAL] {message}\n")
    sys.exit(1)


missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
if missing:
    _fail_fast(
        "缺少必要環境變數: " + ", ".join(missing) + "\n"
        "請先 export 這些變數再執行本腳本（見檔案頂端的使用說明）。"
    )

# 给这次测试专用的隔离环境：独立的 UPLOAD_FOLDER（project.json 等落地文件）、
# 独立的 sqlite DATABASE_URL（本脚本不需要真的用到 DB，但 app.config 载入时
# 需要一个合法值），避免碰到真实项目的 uploads/ 目录。
_E2E_TMP_DIR = tempfile.mkdtemp(prefix="futuresreport_e2e_")
os.environ.setdefault("SECRET_KEY", "e2e-test-secret-not-for-production")
os.environ.setdefault("UPLOAD_FOLDER", os.path.join(_E2E_TMP_DIR, "uploads"))
os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(_E2E_TMP_DIR, "e2e.db"))
os.environ.setdefault("FLASK_DEBUG", "False")

_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, _backend_dir)

from app.models.project import ProjectManager, ProjectStatus  # noqa: E402
from app.services.graph_builder import GraphBuilderService, delete_graph_by_id  # noqa: E402
from app.services.graphiti_factory import (  # noqa: E402
    enforce_embedding_consistency,
    redact_secrets,
    EmbeddingMismatchError,
    build_graphiti,
)
from app.services.graphiti_ontology import convert_ontology  # noqa: E402
from app.services.zep_entity_reader import ZepEntityReader  # noqa: E402
from app.services.zep_tools import ZepToolsService  # noqa: E402
from app.services.zep_graph_memory_updater import AgentActivity, ZepGraphMemoryUpdater  # noqa: E402
from app.utils.zep_paging import fetch_all_nodes, fetch_all_edges, fetch_nodes_and_edges  # noqa: E402
from redis.exceptions import ConnectionError as RedisConnectionError  # noqa: E402


# ---------------------------------------------------------------------------
# 测试用 BYOK 配置（从环境变量组出来，绝不写死）
# ---------------------------------------------------------------------------

USER_LLM_CONFIG: Dict[str, str] = {
    "provider": os.environ["TEST_LLM_PROVIDER"].strip().lower(),
    "model": os.environ["TEST_LLM_MODEL"],
    "api_key": os.environ["TEST_LLM_API_KEY"],
    "base_url": os.environ.get("TEST_LLM_BASE_URL", ""),
}

_RUN_ID = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"
GRAPH_ID_1 = f"e2e_{_RUN_ID}_tenant1"
GRAPH_ID_2 = f"e2e_{_RUN_ID}_tenant2"


# ---------------------------------------------------------------------------
# 步骤执行框架
# ---------------------------------------------------------------------------

class StepResult:
    def __init__(self, name: str, passed: bool, duration: float, detail: str = ""):
        self.name = name
        self.passed = passed
        self.duration = duration
        self.detail = detail


RESULTS: List[StepResult] = []


def run_step(name: str, fn: Callable[[], Optional[str]], watchdog_seconds: int = 60) -> bool:
    """执行单一步骤，统一计时、捕获例外、遮罩错误訊息、印出 PASS/FAIL。

    watchdog_seconds：這個步驟預期不該超過的時間。超過就用 faulthandler 把
    當下所有執行緒的完整 stack trace 印出來（不會終止進程，只是誠實回報
    「卡在哪裡」），交給外層的 bash timeout 兜底終止。已知較慢的步驟
    （add_text_batches / 記憶更新，因為是真的在打 LLM）呼叫時會傳更寬鬆的
    watchdog_seconds。
    """
    print(f"\n--- {name} ---")
    start = time.time()
    faulthandler.dump_traceback_later(watchdog_seconds, exit=False, file=sys.stdout)
    try:
        detail = fn() or ""
        duration = time.time() - start
        RESULTS.append(StepResult(name, True, duration, detail))
        print(f"[PASS] {name} ({duration:.2f}s)" + (f" — {detail}" if detail else ""))
        return True
    except Exception as e:
        duration = time.time() - start
        safe_msg = redact_secrets(str(e))
        RESULTS.append(StepResult(name, False, duration, safe_msg))
        print(f"[FAIL] {name} ({duration:.2f}s) — {safe_msg}")
        print(redact_secrets(traceback.format_exc()))
        return False
    finally:
        faulthandler.cancel_dump_traceback_later()


# ---------------------------------------------------------------------------
# 测试 fixture：本体 + 三段繁中短文本（虚构人物/组织，避免涉及真实政治议题）
# ---------------------------------------------------------------------------

ONTOLOGY = {
    "entity_types": [
        {
            "name": "Politician",
            "description": "政治人物，例如議員、官員。",
            "attributes": [
                {"name": "party", "description": "所屬政黨或陣營"},
            ],
        },
        {
            "name": "Organization",
            "description": "組織、政黨或政府機構。",
            "attributes": [
                {"name": "org_type", "description": "組織類型，例如政黨、政府機構"},
            ],
        },
    ],
    "edge_types": [
        {
            "name": "OPPOSES",
            "description": "公開反對、杯葛某個對象的立場或提案。",
            "attributes": [],
            "source_targets": [
                {"source": "Politician", "target": "Organization"},
                {"source": "Politician", "target": "Politician"},
            ],
        },
    ],
}

TENANT_1_CHUNKS = [
    "陳大文是自由聯盟黨的資深議員，長期關注勞工權益政策。",
    "陳大文公開反對城市發展局提出的舊城重建計畫，認為該計畫將損害弱勢居民的居住權。",
    "城市發展局回應稱，重建計畫已納入補償機制，並批評陳大文的說法過於片面。",
]

TENANT_2_CHUNKS = [
    "林小美是綠色未來黨的發言人，長期支持再生能源立法。",
]

SEARCH_QUERY = "陳大文反對城市發展局的重建計畫"


# ---------------------------------------------------------------------------
# 各步骤实现
# ---------------------------------------------------------------------------

def step_falkordb_ping() -> str:
    graphiti = build_graphiti(USER_LLM_CONFIG)
    import asyncio

    async def _ping():
        await graphiti.driver.execute_query("RETURN 1")

    try:
        asyncio.run(_ping())
    except (RedisConnectionError,) as e:
        raise RuntimeError(f"FalkorDB 連線失敗，請檢查 FALKORDB_HOST/PORT/PASSWORD: {e}") from e
    return f"host={os.environ['FALKORDB_HOST']}:{os.environ['FALKORDB_PORT']}"


def step_precheck_llm() -> str:
    builder = GraphBuilderService(user_llm_config=USER_LLM_CONFIG)
    ok, reason = builder.precheck()
    if not ok:
        raise RuntimeError(f"LLM 預檢失敗: {reason}")
    return f"provider={USER_LLM_CONFIG['provider']}, model={USER_LLM_CONFIG['model']}"


_PROJECT = None
_BUILDER: Optional[GraphBuilderService] = None


def step_create_project_and_ontology() -> str:
    global _PROJECT, _BUILDER
    _PROJECT = ProjectManager.create_project(name=f"e2e-test-{_RUN_ID}")
    _PROJECT.status = ProjectStatus.ONTOLOGY_GENERATED
    _PROJECT.graph_id = GRAPH_ID_1
    ProjectManager.save_project(_PROJECT)

    _BUILDER = GraphBuilderService(user_llm_config=USER_LLM_CONFIG)
    _BUILDER.set_ontology(GRAPH_ID_1, ONTOLOGY)

    entity_types, edge_types, edge_type_map = convert_ontology(ONTOLOGY)
    assert "Politician" in entity_types and "Organization" in entity_types
    assert "OPPOSES" in edge_types
    return f"graph_id={GRAPH_ID_1}, entity_types={list(entity_types.keys())}, edge_types={list(edge_types.keys())}"


def step_add_text_batches() -> str:
    assert _BUILDER is not None
    episode_uuids_holder = {}

    def progress_cb(msg, ratio):
        pass  # 静默，避免刷屏；PASS/FAIL 已经够清楚

    _BUILDER.add_text_batches(GRAPH_ID_1, TENANT_1_CHUNKS, batch_size=3, progress_callback=progress_cb)
    return f"{len(TENANT_1_CHUNKS)} 個文本塊已寫入"


def step_write_embedding_metadata() -> str:
    assert _PROJECT is not None and _BUILDER is not None
    meta = _BUILDER.get_embedding_metadata()
    _PROJECT.embedding_provider = meta["embedding_provider"]
    _PROJECT.embedding_model = meta["embedding_model"]
    ProjectManager.save_project(_PROJECT)

    reloaded = ProjectManager.get_project(_PROJECT.project_id)
    assert reloaded is not None
    assert reloaded.embedding_provider == meta["embedding_provider"]
    assert reloaded.embedding_model == meta["embedding_model"]
    return f"embedding_provider={meta['embedding_provider']}, embedding_model={meta['embedding_model']}"


def step_read_entities_and_edges() -> str:
    assert _BUILDER is not None
    graph_data = _BUILDER.get_graph_data(GRAPH_ID_1)

    nodes = graph_data["nodes"]
    edges = graph_data["edges"]
    assert len(nodes) > 0, "節點列表為空"
    assert len(edges) > 0, "邊列表為空（可能是 LLM 未抽出任何關係，檢查文本/模型）"

    for node in nodes:
        for field in ("uuid", "name", "labels", "summary"):
            assert field in node, f"節點缺少欄位 {field}"
    for edge in edges:
        for field in ("uuid", "name", "fact", "source_node_uuid", "target_node_uuid"):
            assert field in edge, f"邊缺少欄位 {field}"

    all_labels = {label for node in nodes for label in node["labels"]}
    custom_labels_found = all_labels & {"Politician", "Organization"}
    assert custom_labels_found, f"自訂實體型別未出現在節點標籤中，實際標籤: {all_labels}"

    return f"{len(nodes)} 個節點, {len(edges)} 條邊, 自訂型別命中: {custom_labels_found}"


def step_search_graph() -> str:
    tools = ZepToolsService(USER_LLM_CONFIG)
    result = tools.search_graph(GRAPH_ID_1, query=SEARCH_QUERY, limit=10, scope="edges")
    assert result.total_count > 0, f"搜尋 '{SEARCH_QUERY}' 沒有找到任何結果"
    return f"query='{SEARCH_QUERY}' -> {result.total_count} 條結果"


def step_consistency_guard() -> str:
    real_provider = USER_LLM_CONFIG["provider"]
    fake_provider = "openai" if real_provider != "openai" else "gemini"
    fake_config = {
        "provider": fake_provider,
        "model": "not-the-real-model",
        "api_key": "fake-key-not-used-for-any-real-call",
        "base_url": "",
    }

    try:
        enforce_embedding_consistency(fake_config, GRAPH_ID_1)
        raise AssertionError("預期應該拋出 EmbeddingMismatchError，但沒有")
    except EmbeddingMismatchError:
        pass

    # 反向确认：用真实配置查同一张图不应该被挡
    enforce_embedding_consistency(USER_LLM_CONFIG, GRAPH_ID_1)
    return f"假配置 (provider={fake_provider}) 正確被擋下；真實配置正常放行"


def step_memory_update() -> str:
    updater = ZepGraphMemoryUpdater(GRAPH_ID_1, USER_LLM_CONFIG)
    activity = AgentActivity(
        platform="twitter",
        agent_id=1,
        agent_name="測試агент_陳大文",
        action_type="CREATE_POST",
        action_args={"content": "我會持續監督城市發展局的舊城重建計畫。"},
        round_num=1,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    updater.start()
    updater.add_activity(activity)
    updater.stop()  # stop() 内部会 flush 剩余缓冲区，强制立即发送

    stats = updater.get_stats()
    assert stats["items_sent"] >= 1, f"記憶更新未成功寫入，stats={stats}"
    return f"items_sent={stats['items_sent']}, failed_count={stats['failed_count']}"


def step_pagination() -> str:
    # 每一对 nodes+edges 各自用一个新建的 Graphiti 实例（透过 fetch_nodes_and_edges
    # 在同一个 event loop 内完成），不要对同一个 driver 跨多组 fetch 调用重复用
    # asyncio.run()——否则第二组调用会在已关闭的 event loop 上炸掉（Stage 5
    # 用真实 FalkorDB 实测到的问题，见 zep_paging.fetch_nodes_and_edges 的说明）。
    nodes_full, edges_full = fetch_nodes_and_edges(
        build_graphiti(USER_LLM_CONFIG, GRAPH_ID_1).driver, GRAPH_ID_1,
        node_page_size=100, edge_page_size=100,
    )
    nodes_paged, edges_paged = fetch_nodes_and_edges(
        build_graphiti(USER_LLM_CONFIG, GRAPH_ID_1).driver, GRAPH_ID_1,
        node_page_size=1, edge_page_size=1,
    )

    assert len(nodes_paged) == len(nodes_full), (
        f"分页 page_size=1 得到的节点数 {len(nodes_paged)} 与一次性取回的 {len(nodes_full)} 不一致"
    )
    assert len(edges_paged) == len(edges_full), (
        f"分页 page_size=1 得到的边数 {len(edges_paged)} 与一次性取回的 {len(edges_full)} 不一致"
    )
    return f"nodes={len(nodes_full)} (page_size=1 一致), edges={len(edges_full)} (page_size=1 一致)"


def step_multi_tenant_isolation() -> str:
    assert _BUILDER is not None
    project2 = ProjectManager.create_project(name=f"e2e-test-tenant2-{_RUN_ID}")
    project2.status = ProjectStatus.ONTOLOGY_GENERATED
    project2.graph_id = GRAPH_ID_2
    ProjectManager.save_project(project2)

    builder2 = GraphBuilderService(user_llm_config=USER_LLM_CONFIG)
    builder2.set_ontology(GRAPH_ID_2, ONTOLOGY)
    builder2.add_text_batches(GRAPH_ID_2, TENANT_2_CHUNKS, batch_size=3)

    meta2 = builder2.get_embedding_metadata()
    project2.embedding_provider = meta2["embedding_provider"]
    project2.embedding_model = meta2["embedding_model"]
    ProjectManager.save_project(project2)

    reader = ZepEntityReader(USER_LLM_CONFIG)
    tenant1_names = {n["name"] for n in reader.get_all_nodes(GRAPH_ID_1)}
    tenant2_names = {n["name"] for n in reader.get_all_nodes(GRAPH_ID_2)}

    assert "林小美" not in tenant1_names, "tenant2 的實體洩漏到 tenant1"
    assert "陳大文" not in tenant2_names, "tenant1 的實體洩漏到 tenant2"
    assert tenant1_names.isdisjoint(tenant2_names), (
        f"兩個 graph_id 的實體集合有重疊: {tenant1_names & tenant2_names}"
    )

    global _GRAPH_2_CREATED
    _GRAPH_2_CREATED = True
    return f"tenant1={len(tenant1_names)} 個實體, tenant2={len(tenant2_names)} 個實體, 互不可見已確認"


_GRAPH_2_CREATED = False


def cleanup() -> None:
    """无论前面哪一步失败，都尝试清理两个测试图谱。"""
    print("\n--- 清理階段 ---")
    for graph_id in (GRAPH_ID_1, GRAPH_ID_2):
        try:
            delete_graph_by_id(graph_id)
            print(f"[CLEANUP] 已刪除 {graph_id}")
        except Exception as e:
            print(f"[CLEANUP-WARN] 刪除 {graph_id} 時發生例外（可能該圖本來就不存在）: {redact_secrets(str(e))}")

    # 验证删除后确实查不到数据了（每次 fetch 各自现建一个新的 Graphiti 实例，
    # 不要沿用同一个 driver 跨两次调用——理由同 step_pagination 的说明）
    try:
        remaining_1 = fetch_all_nodes(build_graphiti(USER_LLM_CONFIG).driver, GRAPH_ID_1, page_size=100)
        remaining_2 = fetch_all_nodes(build_graphiti(USER_LLM_CONFIG).driver, GRAPH_ID_2, page_size=100)
        if remaining_1 or remaining_2:
            print(f"[CLEANUP-WARN] 刪除後仍查到殘留節點: tenant1={len(remaining_1)}, tenant2={len(remaining_2)}")
        else:
            print("[CLEANUP] 已確認刪除後兩個圖都查不到任何節點")
    except Exception as e:
        print(f"[CLEANUP-WARN] 刪除後驗證失敗: {redact_secrets(str(e))}")


def main() -> int:
    print("=" * 70)
    print("Graphiti + FalkorDB 端到端整合測試")
    print("=" * 70)
    print(f"FalkorDB: {os.environ['FALKORDB_HOST']}:{os.environ['FALKORDB_PORT']}")
    print(f"LLM: provider={USER_LLM_CONFIG['provider']}, model={USER_LLM_CONFIG['model']}")
    print(f"測試 graph_id: {GRAPH_ID_1} (tenant1), {GRAPH_ID_2} (tenant2)")
    print()
    print("預估 LLM/embedding API 呼叫量級（實際數字取決於 LLM 從文本抽出多少實體/關係）：")
    print("  - precheck_llm: 2 次（1 次結構化輸出 + 1 次 embedding）")
    print("  - add_text_batches (tenant1, 3 個文本塊): 每塊內部約 3-6 次 LLM 呼叫")
    print("    （實體抽取、邊抽取、去重比對）+ 每個抽出的實體/邊各 1 次 embedding，")
    print("    粗估 3 塊合計 20-35 次")
    print("  - search_graph: 1 次 embedding（查詢向量化）")
    print("  - 記憶更新 (1 條 episode): 約 3-6 次 LLM + 若干 embedding，粗估 5-10 次")
    print("  - tenant2 (1 個文本塊): 粗估 5-12 次")
    print("  合計粗估：約 35-65 次 API 呼叫（一個中等長度的簡短測試量級，非精確值）")
    print()

    start_all = time.time()

    try:
        if not run_step("0. FalkorDB 連線自檢 (ping)", step_falkordb_ping):
            _fail_fast("FalkorDB 連線失敗，中止測試（見上方錯誤訊息）。")

        if not run_step("0. LLM 預檢 (precheck_llm)", step_precheck_llm):
            _fail_fast("LLM 預檢失敗，中止測試（見上方錯誤訊息）。")

        steps = [
            ("1. 建立測試專案 + 設定含自訂型別的本體", step_create_project_and_ontology, 30, False),
            ("2. add_text_batches 寫入 3 個文本塊", step_add_text_batches, 350, False),
            ("3. 寫入 embedding metadata 到專案", step_write_embedding_metadata, 30, False),
            ("4. 讀取 entities/edges 驗證格式與自訂型別", step_read_entities_and_edges, 60, False),
            ("5. search_graph 語義搜尋", step_search_graph, 60, False),
            ("6. Embedding 一致性守門（假配置應被擋下）", step_consistency_guard, 30, False),
            ("7. 模擬記憶更新路徑寫入", step_memory_update, 200, False),
            # continue_on_known_failure=True：這一步的失敗是已經確認、根因完全
            # 查清楚的 FalkorDB 引擎缺陷（WHERE uuid < $param 在有 RANGE 索引的
            # 屬性上，跨頁邊界沒有正確排除/去重，只在極端小 page_size 下才會
            # 觸發；生產實際預設的 page_size=100 已經用超過一頁的真實資料量
            # 額外驗證過不受影響），不是這次遷移的迴歸，也不會被誤判成「這步
            # 通過了」——RESULTS 裡仍然誠實記錄 FAIL。放行只是為了不要因為這個
            # 已知、跟遷移正確性無關的問題擋住後面步驟（尤其是 9. 多租戶隔離）
            # 的驗證機會。
            ("8. 分頁游標邏輯 (page_size=1)", step_pagination, 90, True),
            ("9. 多租戶隔離 (第二個 graph_id)", step_multi_tenant_isolation, 350, False),
        ]

        all_ok = True
        for name, fn, watchdog, continue_on_known_failure in steps:
            ok = run_step(name, fn, watchdog_seconds=watchdog)
            all_ok = all_ok and ok
            if not ok:
                if continue_on_known_failure:
                    print(f"\n[CONTINUE] 已知問題（見步驟說明），繼續執行後續步驟。")
                    continue
                print(f"\n[STOP] 步驟失敗，停止後續步驟（仍會執行清理）。")
                break

    finally:
        cleanup()

    total_time = time.time() - start_all

    print("\n" + "=" * 70)
    print("測試總結")
    print("=" * 70)
    passed = sum(1 for r in RESULTS if r.passed)
    failed = sum(1 for r in RESULTS if not r.passed)
    for r in RESULTS:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.name} ({r.duration:.2f}s)")
    print(f"\n總計: {passed} passed, {failed} failed, 總耗時 {total_time:.1f}s")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
