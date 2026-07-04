# FuturesReport Cleanup Report

Branch: `refactor/cleanup`  
Scope: Phases 0–3 (Phase 3 = proposals only, not executed)  
Smoke tests: 26/26 pass after every phase

---

## Phase 0 — Safety Net

| Item | Status |
|---|---|
| `refactor/cleanup` branch created | ✅ |
| `FUNCTIONALITY_INVENTORY.md` written | ✅ |
| `backend/tests/test_smoke.py` — 26 tests covering all 6 blueprints | ✅ |

Tests run against a unique temp SQLite file per session (via `tempfile.mkstemp`), deleted on teardown. No external services (Zep, Stripe, LLM) are called.

---

## Phase 1 — Zero-Risk Deletions

### Debug print() statements removed

**`backend/app/services/oasis_profile_generator.py`**

Removed 6 `print()` calls that duplicated adjacent `logger.info` output with `'='*60` decorative separators:
- Before parallel profile generation (3 prints)
- After parallel completion (3 prints)

**Preserved:** `_print_generated_profile()` method's `print(output)` — this is intentional console output for human-readable profile inspection, not debug logging.

### Debug console.log() removed

**`frontend/src/views/Process.vue`**

Removed 12 `console.log()` calls from `renderGraph()` and `pollTaskStatus()`:
- `'Fetching graph data, nodes:'`
- `'Task status: ...'`
- `'✅ 图谱构建完成'`
- `'📊 加载完整图谱:'`
- `'✅ 图谱加载完成'`
- `'Cannot render: svg/container/dimensions missing'`
- `'Rendering graph:'`
- `'No nodes to render'`
- `'Nodes: X Edges: Y'`
- A catch block changed from `console.log('Graph data fetch:', ...)` → `catch { /* graph data not ready yet */ }`

**Preserved:** All `console.error()` and `console.warn()` in catch blocks — these surface real errors.

### Unused dependencies removed

**`backend/requirements.txt`**

Removed:
- `celery[redis]>=5.3.0`
- `redis>=5.0.0`

Confirmed unused by global grep: zero matches for `import celery`, `from celery`, `import redis`, `from redis` across the entire `backend/` directory (excluding `.venv`).

> ⚠️ **Manual action required:** `pyproject.toml` still lists `celery` and `redis` because `uv` is not in PATH on this machine. Modifying `pyproject.toml` without running `uv lock` would make the Docker build fail (`uv.lock` would be inconsistent). Run `uv lock` after manually removing those two entries from `pyproject.toml` to complete the cleanup.

---

## Phase 2 — Low-Risk Consolidation

### Inline stdlib imports → module level

All stdlib modules have zero initialization side effects; moving from inline to module level is strictly better (imports happen once at startup instead of on every request).

**`backend/app/api/simulation.py`**

Added to module-level imports: `csv`, `json`, `sqlite3`, `threading`, `from datetime import datetime`  
Added: `from ..models.task import TaskManager, TaskStatus`

Removed **9 redundant inline import statements** scattered across:
- `_check_simulation_prepared()` — `import json`
- `prepare_simulation()` — `import threading`, `import os`, `from ..config import Config`, `from ..models.task import TaskManager, TaskStatus`
- `get_prepare_status()` — `from ..models.task import TaskManager`
- Three report/history handlers — `import json`, `from datetime import datetime`
- Two SQLite handlers — `import csv`, `from datetime import datetime`, `import sqlite3` (×2)

**`backend/app/api/report.py`**

Added to module-level imports: `import uuid`, `import tempfile`

Removed **2 redundant inline import statements**:
- `generate_report()` — `import uuid`
- `download_report()` — `import tempfile`

**Preserved inline:** `from ..services.zep_tools import ZepToolsService` at two locations in `report.py` (lines ~980 and ~1024).  
**Reason:** `zep_tools.py` imports from `zep_cloud.client`; moving to module level would fail at Flask startup when `ZEP_API_KEY` is absent (dev environments without Zep). The lazy pattern is intentional.

---

## Phase 3 — Structure Convergence Proposals

> **These are proposals only. Nothing below has been executed.**  
> Review and approve before action.

### Overly long route functions in `simulation.py` (2,736 lines)

| Function | Approx. lines | Concern |
|---|---|---|
| `prepare_simulation()` | ~297 | Handles task creation, thread spawning, already-prepared check, full entity/profile pipeline setup, error branches |
| `start_simulation()` | ~206 | Builds full OASIS config, spawns SimulationRunner thread, validates all prerequisites |
| `interview_agents_batch()` | ~138 | LLM loop over multiple agents with retry/fallback |
| `interview_agent()` | ~129 | Single-agent LLM interview with full prompt construction |
| `_check_simulation_prepared()` | ~118 | State file parsing and file existence checks — good candidate for further decomposition |
| `interview_all_agents()` | ~103 | Wrapper over batch interview with full-roster expansion |
| `get_run_status_detail()` | ~101 | Aggregates multiple data sources into one status payload |

**Proposed split — `simulation.py` → 2 files:**
- `simulation_routes.py` — HTTP entry points only (thin controllers, ≤50 lines each)
- `simulation_helpers.py` (or `simulation_logic.py`) — `_check_simulation_prepared`, `_get_report_id_for_simulation`, interview prompt builders, config assembly logic

**Risk:** Medium. Requires verifying all cross-function references and that Flask blueprint registration is adjusted. The interview trio (`interview_agent`, `interview_agents_batch`, `interview_all_agents`) share `INTERVIEW_PROMPT_PREFIX` and `optimize_interview_prompt()` — these must move together or be imported.

### `generate_report()` in `report.py` (~184 lines)

Handles validation, LLM config resolution, report record creation, thread spawning, and error branching in one function. Could extract a `_build_report_task()` helper.

**Risk:** Low. The function is self-contained; extracting the task-setup block would not change any API behavior.

### `frontend/src/views/Process.vue` (2,021 lines)

Contains graph rendering (D3.js), task polling, simulation control, interview panel, and post-feed display in one SFC. Candidates for extraction:
- `<GraphPanel>` component — D3 rendering logic (`renderGraph`, `updateGraph`, zoom/pan)
- `<InterviewPanel>` component — interview form + history display
- `<PostFeed>` component — Reddit/Twitter post list

**Risk:** Medium-high. Vue component extraction requires careful prop/emit design and ensuring reactive state (`reactive()` store) is accessible across components. The `pollTaskStatus` interval must remain in the parent or be lifted to a composable.

---

## Items Preserved With Reasons

| Item | Location | Reason preserved |
|---|---|---|
| `_print_generated_profile()` `print(output)` | `oasis_profile_generator.py` | Intentional human-readable console output |
| All `console.error()` / `console.warn()` | `Process.vue` | Legitimate error surfacing |
| `from ..services.zep_tools import ZepToolsService` (inline ×2) | `report.py` | Lazy import guard: prevents startup failure when `ZEP_API_KEY` is absent |
| `celery`, `redis` in `pyproject.toml` | `pyproject.toml` | Cannot update without `uv lock`; would break Docker build |
| `INTERVIEW_PROMPT_PREFIX` (both definitions) | `simulation.py` | Confirmed not duplicates: different content and purpose |
| `optimize_interview_prompt()` | `simulation.py` | Confirmed used at 3 call sites |
| All Stripe webhook logic | `subscription.py` | Protected — always returns 200, Stripe-Signature verified |
| RBAC first-user-is-admin | `models/user.py` | Protected |
| Auth localStorage key names | `frontend/` | Protected |
| Region dropdown default Taiwan | `frontend/` | Protected |
| All deployment config files | `zbpack.json`, `Dockerfile`, `docker-compose.yml`, `.dockerignore` | Protected — not touched |

---

## Recommended Manual Review List

1. **`pyproject.toml`** — Remove `celery[redis]>=5.3.0` and `redis>=5.0.0`, then run `uv lock`. Low risk.

2. **`simulation.py` split** — Approve the Phase 3 split proposal above before executing. Schedule for a separate PR.

3. **`Process.vue` component extraction** — Approve the component split proposal before executing. Highest complexity; requires frontend state design session.

4. **`ZepToolsService` import** — If `ZEP_API_KEY` will always be set in all environments, the inline guard can be moved to module level. Confirm with ops team.

5. **`ruff` / `eslint --fix`** — Neither tool was in PATH during this cleanup. Run `ruff check --fix backend/` and `eslint --fix frontend/src/` for automated import ordering and style normalization once tools are available.

---

## Summary

| Phase | Action | Files changed | Lines removed |
|---|---|---|---|
| 0 | Safety net | 2 created | +366 (tests+inventory) |
| 1 | Delete dead code + unused deps | 3 modified | −6 prints, −12 console.logs, −2 dep lines |
| 2 | Consolidate inline imports | 2 modified | −30 lines net |
| 3 | Proposals written | 0 executed | — |

All 26 smoke tests pass on `refactor/cleanup` branch.
