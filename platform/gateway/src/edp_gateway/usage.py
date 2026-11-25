"""Usage log: one row per gateway call, with tokens and cost (plan Phase 1 exit criterion:
"Every gateway call is ... logged with tokens and cost").

SQLite in the local data folder (ADR-0008 local adapters). No prompt or response text is
stored: only a SHA-256 of the redacted prompt, so a call can be matched to its input without
keeping client content in the log (plan §4.1 Guardrails: "PII redaction on prompts and logs").
"""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    call_id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    service TEXT NOT NULL,
    run_id TEXT,
    kind TEXT NOT NULL,
    role TEXT NOT NULL,
    model TEXT,
    prompt_version TEXT,
    data_class TEXT NOT NULL,
    status TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    cost_source TEXT,
    latency_ms INTEGER,
    redactions TEXT NOT NULL,
    flags TEXT NOT NULL,
    prompt_sha256 TEXT,
    error TEXT
)
"""


class CallRecord(BaseModel):
    call_id: str
    service: str
    run_id: str | None = None
    kind: str  # "completion" or "embedding"
    role: str
    model: str | None = None
    prompt_version: str | None = None
    data_class: str
    status: str  # "ok", "refused" or "error"
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    cost_source: str | None = None
    latency_ms: int | None = None
    redactions: dict[str, int] = {}
    flags: list[str] = []
    prompt_sha256: str | None = None
    error: str | None = None


class UsageLog:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute(_SCHEMA)
        self._db.commit()

    def record(self, rec: CallRecord) -> None:
        row = rec.model_dump()
        row["ts"] = datetime.now(UTC).isoformat(timespec="seconds")
        row["redactions"] = json.dumps(rec.redactions, sort_keys=True)
        row["flags"] = json.dumps(rec.flags)
        cols = ", ".join(row)
        self._db.execute(
            f"INSERT INTO calls ({cols}) VALUES ({', '.join('?' * len(row))})", list(row.values())
        )
        self._db.commit()

    def spent_usd(self) -> float:
        (total,) = self._db.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM calls").fetchone()
        return float(total)

    def calls(self) -> list[dict[str, Any]]:
        cur = self._db.execute("SELECT * FROM calls ORDER BY ts, call_id")
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r, strict=True)) for r in cur.fetchall()]

    def summary(self) -> list[dict[str, Any]]:
        cur = self._db.execute(
            "SELECT service, kind, model, status, COUNT(*), SUM(input_tokens), SUM(output_tokens),"
            " SUM(cost_usd) FROM calls GROUP BY service, kind, model, status ORDER BY service, kind"
        )
        keys = ["service", "kind", "model", "status", "calls", "input_tokens", "output_tokens", "cost_usd"]
        return [dict(zip(keys, r, strict=True)) for r in cur.fetchall()]
