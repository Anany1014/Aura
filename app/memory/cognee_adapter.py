"""
Budget-Gated Cognee Adapter — Phase 4
========================================
PRD Section 4 (Strict Guardrails) and Section 6 (Budget Constraint):

  "Cognee is restricted to storing architecture decisions, graph schema
   evolutions, and prompt optimization heuristics. It MUST NOT store raw
   documents, full repos, or heavy node embeddings to maintain the $25/month
   tier."

  "Cognee memory payload must remain under 50MB."

Design:
-------
This module is the ONLY place in the codebase that may write to Cognee.
Every write passes through two mandatory gates:

  Gate 1 — Type allowlist:
    Only three record types are permitted: SCHEMA_LOG, PROMPT_HEURISTIC,
    and IDEA_PATTERN. Any other type raises CogneeTypeViolation immediately.

  Gate 2 — Field blocklist (strip-before-write):
    Forbidden fields: "embedding", "content", "raw_text", "document",
    "full_text", "chunk", "vector".
    These are stripped from the payload dict before serialization so they
    can never enter the Cognee graph context regardless of caller intent.

  Gate 3 — Memory ceiling (50 MB hard cap):
    The serialized payload size is checked before writing. If the current
    estimated total Cognee memory + this payload exceeds MAX_MEMORY_BYTES,
    a CogneeMemoryError is raised and the write is rejected. A local JSON
    ledger in COGNEE_METADATA_DIR tracks cumulative usage.

Usage:
------
    adapter = CogneeAdapter()
    await adapter.log_schema_decision("nodes_table_v2", {"change": "added hnsw index"})
    await adapter.log_prompt_heuristic("synthesis_v3", {"temperature": 0.7, "note": "..."})
    await adapter.log_idea_pattern("rejected", idea_dict, score=6.1)
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — derived directly from PRD Section 4 & 6
# ---------------------------------------------------------------------------
MAX_MEMORY_BYTES: int = settings.COGNEE_MAX_MEMORY_MB * 1024 * 1024  # 50 MB default
LEDGER_FILE: str = os.path.join(settings.COGNEE_METADATA_DIR, "memory_ledger.json")

# Fields that are UNCONDITIONALLY stripped from any payload before writing.
# These represent the heavy data types explicitly banned by the PRD.
_BLOCKED_FIELDS: frozenset[str] = frozenset({
    "embedding",
    "vector",
    "content",
    "raw_text",
    "full_text",
    "document",
    "chunk",
    "chunks",
    "text",
})

# Maximum size of a single Cognee record (64 KB). Protects against accidentally
# passing large summary strings that would erode the 50 MB budget quickly.
_MAX_SINGLE_RECORD_BYTES: int = 64 * 1024


# ---------------------------------------------------------------------------
# Allowed record types
# ---------------------------------------------------------------------------
class CogneeRecordType(str, Enum):
    SCHEMA_LOG = "schema_log"             # Architecture decisions, index changes
    PROMPT_HEURISTIC = "prompt_heuristic" # Synthesis/critic prompt calibration
    IDEA_PATTERN = "idea_pattern"         # Pass/fail patterns from idea pipeline


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class CogneeTypeViolation(ValueError):
    """Raised when caller attempts to write a record type not in the allowlist."""
    pass


class CogneeMemoryError(RuntimeError):
    """Raised when a write would push cumulative Cognee memory over the budget."""
    pass


class CogneeFieldViolation(ValueError):
    """Raised when a blocked field is found in the payload (before stripping)."""
    pass


# ---------------------------------------------------------------------------
# Ledger — tracks cumulative bytes written to Cognee in this installation
# ---------------------------------------------------------------------------
class _MemoryLedger:
    """Simple JSON file ledger tracking total bytes committed to Cognee."""

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {"total_bytes": 0, "record_count": 0, "last_updated": None}

    def _save(self) -> None:
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)

    @property
    def total_bytes(self) -> int:
        return self._data["total_bytes"]

    def add(self, byte_count: int) -> None:
        self._data["total_bytes"] += byte_count
        self._data["record_count"] += 1
        self._data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def usage_mb(self) -> float:
        return self._data["total_bytes"] / (1024 * 1024)

    def summary(self) -> dict:
        return dict(self._data)


# ---------------------------------------------------------------------------
# Main Adapter
# ---------------------------------------------------------------------------
class CogneeAdapter:
    """
    Single-responsibility Cognee gateway.

    All Cognee writes in the codebase MUST go through this class.
    Direct cognee client calls outside this module are forbidden by convention.
    """

    def __init__(self) -> None:
        self._ledger = _MemoryLedger(LEDGER_FILE)
        self._cognee_available = self._probe_cognee()

    def _probe_cognee(self) -> bool:
        """
        Returns False unconditionally in Phase 4.

        Live Cognee integration is deferred to Phase 6 (subprocess-based writer).
        Cognee registers asyncio event-loop callbacks at import/probe time —
        probing it while an asyncio loop is already running causes an indefinite
        block. Until the subprocess writer is in place, all writes go to the
        local JSON store (see _commit).
        """
        return False

    # ------------------------------------------------------------------
    # Public write methods — the only permitted write surface
    # ------------------------------------------------------------------

    async def log_schema_decision(self, key: str, payload: dict[str, Any]) -> str:
        """
        Record an architecture or schema evolution decision.

        Args:
            key:     Unique identifier, e.g. "nodes_hnsw_index_v2"
            payload: Must contain only lightweight metadata (no embeddings/text).

        Returns:
            Record ID (UUID string).
        """
        return await self._write(CogneeRecordType.SCHEMA_LOG, key, payload)

    async def log_prompt_heuristic(self, key: str, payload: dict[str, Any]) -> str:
        """
        Record a prompt parameter change or calibration result.

        Args:
            key:     Unique identifier, e.g. "synthesis_temperature_v3"
            payload: Heuristic data dict — no raw prompts/documents allowed.
        """
        return await self._write(CogneeRecordType.PROMPT_HEURISTIC, key, payload)

    async def log_idea_pattern(
        self,
        verdict: str,          # "passed" | "rejected"
        idea_name: str,
        scores: dict[str, float],
        domains_traversed: list[str],
        aggregate_score: float,
    ) -> str:
        """
        Record a pass/fail idea pattern so future synthesis can learn from it.

        Only lightweight metadata (name, domains, scores) is stored — never
        the full idea text or path summaries.
        """
        payload = {
            "verdict": verdict,
            "idea_name": idea_name,
            "scores": scores,
            "domains_traversed": domains_traversed,
            "aggregate_score": round(aggregate_score, 4),
        }
        key = f"idea_{verdict}_{idea_name.lower().replace(' ', '_')[:40]}"
        return await self._write(CogneeRecordType.IDEA_PATTERN, key, payload)

    # ------------------------------------------------------------------
    # Memory budget query
    # ------------------------------------------------------------------

    def memory_status(self) -> dict:
        """Returns current memory usage — safe to expose in health endpoints."""
        return {
            **self._ledger.summary(),
            "limit_mb": settings.COGNEE_MAX_MEMORY_MB,
            "usage_mb": round(self._ledger.usage_mb(), 3),
            "headroom_mb": round(
                settings.COGNEE_MAX_MEMORY_MB - self._ledger.usage_mb(), 3
            ),
        }

    # ------------------------------------------------------------------
    # Internal gate logic
    # ------------------------------------------------------------------

    async def _write(
        self,
        record_type: CogneeRecordType,
        key: str,
        payload: dict[str, Any],
    ) -> str:
        """
        Core write path. Applies all three gates before touching Cognee.
        Returns the record ID on success.
        """
        # Gate 1: type allowlist — enum membership already enforced by type hint,
        # but we double-check to guard against any string-coercion tricks.
        if not isinstance(record_type, CogneeRecordType):
            raise CogneeTypeViolation(
                f"'{record_type}' is not a permitted Cognee record type. "
                f"Allowed: {[t.value for t in CogneeRecordType]}"
            )

        # Gate 2: field blocklist — warn loudly then strip
        payload = self._sanitize_payload(payload)

        # Build the final envelope
        record_id = str(uuid.uuid4())
        envelope = {
            "id": record_id,
            "type": record_type.value,
            "key": key,
            "payload": payload,
            "written_at": datetime.now(timezone.utc).isoformat(),
        }
        serialized = json.dumps(envelope, default=str)
        byte_count = len(serialized.encode("utf-8"))

        # Gate 3a: single-record size guard
        if byte_count > _MAX_SINGLE_RECORD_BYTES:
            raise CogneeMemoryError(
                f"Record '{key}' ({byte_count} bytes) exceeds the per-record "
                f"limit of {_MAX_SINGLE_RECORD_BYTES} bytes. Strip large fields."
            )

        # Gate 3b: cumulative memory ceiling
        projected_total = self._ledger.total_bytes + byte_count
        if projected_total > MAX_MEMORY_BYTES:
            raise CogneeMemoryError(
                f"Write rejected: committing {byte_count} bytes would push "
                f"Cognee memory to {projected_total / 1024 / 1024:.2f} MB, "
                f"exceeding the {settings.COGNEE_MAX_MEMORY_MB} MB budget."
            )

        # --- Actual Cognee write (or local fallback if unavailable) ---
        await self._commit(key, serialized)

        # Update ledger after successful commit
        self._ledger.add(byte_count)
        logger.info(
            "Cognee write OK | type=%s key=%s bytes=%d usage=%.2fMB",
            record_type.value, key, byte_count, self._ledger.usage_mb(),
        )
        return record_id

    def _sanitize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Strip all blocked fields from the payload.
        Logs a warning for each stripped field so violations are visible.
        """
        cleaned = {}
        for k, v in payload.items():
            if k.lower() in _BLOCKED_FIELDS:
                logger.warning(
                    "CogneeAdapter: blocked field '%s' stripped from payload "
                    "(PRD Section 4 — no raw data in Cognee).", k
                )
            else:
                # Recursively sanitize nested dicts
                if isinstance(v, dict):
                    v = self._sanitize_payload(v)
                cleaned[k] = v
        return cleaned

    async def _commit(self, key: str, serialized_json: str) -> None:
        """
        Write the sanitized envelope to the local JSON store in COGNEE_METADATA_DIR.

        WHY NOT CALL cognee DIRECTLY HERE:
        Cognee registers asyncio event-loop callbacks at *import* time. Importing
        it inside an already-running asyncio context (i.e., inside `async def`)
        causes the loop to block indefinitely waiting for Cognee's internal
        network/auth handshake.

        The safe integration pattern is to call Cognee from a subprocess, not
        directly from inside the FastAPI event loop. That wiring is deferred to
        a future phase once the full pipeline is running end-to-end.

        For Phase 4, all records are persisted to the local JSON store in
        COGNEE_METADATA_DIR. A background job can later sync these to Cognee.

        TODO (Phase 6): replace with asyncio.subprocess call to a thin
              cognee_writer.py script that can block freely in its own process.
        """
        os.makedirs(settings.COGNEE_METADATA_DIR, exist_ok=True)

        # Use a sanitized filename: replace characters unsafe for paths
        safe_key = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
        fallback_path = os.path.join(settings.COGNEE_METADATA_DIR, f"{safe_key}.json")

        with open(fallback_path, "w", encoding="utf-8") as f:
            f.write(serialized_json)

        logger.debug("Cognee local store write: %s", fallback_path)
