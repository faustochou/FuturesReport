"""
One-shot backfill: populate simulation_records.full_requirement for rows
written before that column existed, using the untruncated
simulation_requirement recorded in each simulation's simulation_config.json.

Rows whose config file can no longer be found (e.g. an orphaned record whose
uploads/simulations/<simulation_id>/ directory was lost to an ephemeral
container redeploy) are left untouched and skipped — they keep showing the
old truncated title until/unless the underlying data resurfaces.

Usage (run from backend/ directory):
    uv run python scripts/backfill_full_requirement.py
"""

import json
import os
import sys

# Make the app package importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

_root = os.path.join(os.path.dirname(__file__), "../../")
load_dotenv(os.path.join(_root, ".env"), override=True)

from app.config import Config  # noqa: E402
from app.db.database import get_db  # noqa: E402
from app.db.models import SimulationRecord  # noqa: E402
from sqlalchemy import select  # noqa: E402


def _read_full_requirement(simulation_id: str) -> str:
    """Read simulation_requirement from simulation_config.json, or "" if unavailable."""
    config_path = os.path.join(
        Config.OASIS_SIMULATION_DATA_DIR, simulation_id, "simulation_config.json"
    )
    if not os.path.exists(config_path):
        return ""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return ""
    return (data.get("simulation_requirement") or "").strip()


def main() -> None:
    updated = 0
    skipped = 0

    with get_db() as db:
        rows = db.execute(
            select(SimulationRecord).where(SimulationRecord.full_requirement.is_(None))
        ).scalars().all()

        print(f"→ {len(rows)} record(s) missing full_requirement")

        for row in rows:
            full_text = _read_full_requirement(row.simulation_id)
            if not full_text:
                # simulation_config.json missing/unreadable/empty — leave the
                # row untouched (e.g. an orphaned record from a lost redeploy)
                skipped += 1
                continue
            row.full_requirement = full_text
            updated += 1

    print(f"✓ Backfilled {updated} record(s)")
    print(f"– Skipped {skipped} record(s) (no readable simulation_config.json)")


if __name__ == "__main__":
    main()
