"""
Daily image-generation quota tracker — pure logic, no Streamlit coupling.

Persists state in `{OUTPUT_BASE}/.quota.json` as `{"date": "YYYY-MM-DD", "count": N}`.

Used by both:
  - `orchestrator.generate_book` to consume one slot before each gpt-image-1 call
  - `app.py` for the legacy single-image flows

Decoupled from Streamlit so that orchestrator can enforce the cap without
crashing the script (no `st.stop()`); callers handle the False return.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


def _quota_file() -> Path:
    """Resolve quota file path at call time so monkeypatched OUTPUT_BASE
    (in tests) and runtime env changes are respected."""
    return Path(os.environ.get("OUTPUT_BASE", "output")) / ".quota.json"


def _daily_cap() -> int:
    return int(os.environ.get("DAILY_IMAGE_CAP", "50"))


# Backward-compat module-level constants (read once at import for legacy code
# that does `from quota import QUOTA_FILE`). New code should use `_quota_file()`.
QUOTA_FILE        = _quota_file()
DEFAULT_DAILY_CAP = _daily_cap()


def _today_iso() -> str:
    return datetime.now().date().isoformat()


def load() -> dict:
    qf = _quota_file()
    if not qf.exists():
        return {"date": None, "count": 0}
    try:
        return json.loads(qf.read_text(encoding="utf-8"))
    except Exception:
        return {"date": None, "count": 0}


def save(data: dict) -> None:
    qf = _quota_file()
    qf.parent.mkdir(parents=True, exist_ok=True)
    qf.write_text(json.dumps(data), encoding="utf-8")


def used_today() -> int:
    q = load()
    return q.get("count", 0) if q.get("date") == _today_iso() else 0


def remaining(cap: int | None = None) -> int:
    if cap is None:
        cap = _daily_cap()
    return max(0, cap - used_today())


def consume_one(cap: int | None = None) -> bool:
    """Try to consume one image quota slot. True on success, False if cap reached."""
    if cap is None:
        cap = _daily_cap()
    today = _today_iso()
    used = used_today()
    if used >= cap:
        return False
    save({"date": today, "count": used + 1})
    return True


def refund_one() -> None:
    """Refund one slot (e.g., after a failed generation that was pre-charged)."""
    today = _today_iso()
    used = used_today()
    save({"date": today, "count": max(0, used - 1)})
