"""
TraversalEngine — Phase 3 Async Service
=========================================
Wraps the novelty walk CTE queries in an async service class.
Consumed by the FastAPI traversal router (Phase 5).
"""

import uuid
import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.traversal.queries import (
    NOVELTY_WALK_CTE,
    HYDRATE_PATH_NODES,
    RANDOM_SEED_QUERY,
)

logger = logging.getLogger(__name__)

# Default constants — tuned for the $50/mo budget window (FR-2.2, FR-2.3)
DEFAULT_MAX_HOPS: int = 3
DEFAULT_DOMAIN_PENALTY: float = 0.3   # mult applied when consecutive nodes share a domain


@dataclass
class PathNode:
    """Hydrated node record — one element in a traversal path."""
    id: uuid.UUID
    title: str
    domain: str
    node_type: str
    summary: str

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "title": self.title,
            "domain": self.domain,
            "node_type": self.node_type,
            "summary": self.summary,
        }


@dataclass
class TraversalResult:
    """Complete result of one novelty walk."""
    seed_id: uuid.UUID
    path: list[PathNode]       # ordered list of nodes: seed → ... → terminus
    path_domains: list[str]    # domains in traversal order
    total_distance: float      # accumulated weighted novelty score
    hop_count: int

    @property
    def domain_breadth(self) -> int:
        """Number of distinct domains crossed — used for novelty gate."""
        return len(set(self.path_domains))

    def to_dict(self) -> dict:
        return {
            "seed_id": str(self.seed_id),
            "path": [n.to_dict() for n in self.path],
            "path_domains": self.path_domains,
            "total_distance": round(self.total_distance, 4),
            "hop_count": self.hop_count,
            "domain_breadth": self.domain_breadth,
        }


class TraversalEngine:
    """
    Executes the novelty graph walk using an async SQLAlchemy session.

    Separation of concerns:
    - SQL lives in queries.py  (pure strings, easy to unit-test & replace)
    - Orchestration/retry logic lives here
    - No business logic (synthesis, scoring) — that belongs in Phase 4/5
    """

    def __init__(
        self,
        db: AsyncSession,
        max_hops: int = DEFAULT_MAX_HOPS,
        domain_penalty: float = DEFAULT_DOMAIN_PENALTY,
    ):
        if not (2 <= max_hops <= 5):
            raise ValueError(f"max_hops must be between 2 and 5, got {max_hops}")
        if not (0.0 <= domain_penalty <= 1.0):
            raise ValueError(f"domain_penalty must be in [0.0, 1.0], got {domain_penalty}")

        self.db = db
        self.max_hops = max_hops
        self.domain_penalty = domain_penalty

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        seed_id: Optional[uuid.UUID] = None,
    ) -> TraversalResult:
        """
        Execute one novelty walk.

        Args:
            seed_id: Starting node UUID. If None, a random seed is selected.

        Returns:
            TraversalResult with the path that maximises novelty score.

        Raises:
            ValueError:  No seed found (empty graph).
            RuntimeError: CTE returned no complete path (graph too sparse for
                          requested hop depth — caller should retry with smaller hops).
        """
        from app.core.config import settings

        if settings.SIMULATION_MODE:
            logger.info("[SIMULATION] Bypassing CTE database traversal query")
            seed_uuid = seed_id or uuid.uuid4()
            
            # Default values for simulation path
            seed_title = "Decentralized Biomaterial Mesh Supply Chains"
            seed_domain = "materials_science"
            seed_type = "startup"
            seed_summary = "Proposes mesh network topologies to allocate bio-material components safely over decentralized manufacturing plants."
            
            # If seed_id matches a previously ingested node, resolve its metadata
            if seed_id:
                import os
                import json
                meta_dir = settings.COGNEE_METADATA_DIR
                if os.path.exists(meta_dir):
                    for filename in os.listdir(meta_dir):
                        if (filename.startswith("readme_ingest_") or filename.startswith("file_ingest_")) and filename.endswith(".json"):
                            try:
                                with open(os.path.join(meta_dir, filename), "r", encoding="utf-8") as f:
                                    meta_data = json.load(f)
                                    payload = meta_data.get("payload", {})
                                    if payload.get("node_id") == str(seed_id):
                                        seed_title = payload.get("title", seed_title)
                                        seed_domain = payload.get("domain", seed_domain)
                                        seed_type = payload.get("node_type", seed_type)
                                        seed_summary = payload.get("summary", seed_summary)
                                        
                                        # Map README titles to high-fidelity matching summaries for the demo
                                        summaries_repo = {
                                            "CityVaani Civic Engagement Platform": "A modern, bilingual civic engagement web application built to bridge the gap between citizens and municipal authorities by allowing issue reporting, OSM Leaflet visualizations, and status tracking.",
                                            "ONOE Voter Hub - One Nation One Election": "An interactive, neutral educational simulator built with Streamlit mapping voters statistics, Cost-efficiency bar charts, policy FAQs, and quiz evaluations.",
                                            "TOTEM Chess Bot and Engine": "An offline, grandmaster-capable chess engine and GUI built with Pygame utilizing minimax alpha-beta pruning, move hint assistance, and custom FEN starts.",
                                            "UrbnConnect Urban Sustainability Tracker": "A civic-tech environmental monitoring dashboard mapping deforestation indices, community greenery deficits, adopted trees, and plantation guides."
                                        }
                                        seed_summary = summaries_repo.get(seed_title, seed_summary)
                                        break
                            except Exception:
                                pass

            mock_path = [
                PathNode(
                    id=seed_uuid,
                    title=seed_title,
                    domain=seed_domain,
                    node_type=seed_type,
                    summary=seed_summary
                ),
                PathNode(
                    id=uuid.uuid4(),
                    title="Quantum Cryptographic Distributed Scaling",
                    domain="cryptography",
                    node_type="paper",
                    summary="Proposes combining quantum entanglement protocols with sharding mechanisms in distributed ledgers to secure multi-hop operations."
                ),
                PathNode(
                    id=uuid.uuid4(),
                    title="Realtime Cargo Logistics Routing",
                    domain="logistics",
                    node_type="code",
                    summary="Rust library executing ledger state updates for high-frequency cargo route adjustments and transit calculations."
                )
            ]
            return TraversalResult(
                seed_id=seed_uuid,
                path=mock_path,
                path_domains=[n.domain for n in mock_path],
                total_distance=2.54,
                hop_count=len(mock_path) - 1
            )

        # Step 1: resolve seed
        resolved_seed = await self._resolve_seed(seed_id)
        logger.info("Traversal started from seed %s", resolved_seed)

        # Step 2: execute the greedy CTE
        cte_row = await self._execute_cte(resolved_seed)
        if cte_row is None:
            # Try falling back to fewer hops before giving up
            if self.max_hops > 2:
                logger.warning(
                    "CTE found no path at %d hops from seed %s — retrying with %d hops",
                    self.max_hops, resolved_seed, self.max_hops - 1,
                )
                fallback = TraversalEngine(
                    self.db,
                    max_hops=self.max_hops - 1,
                    domain_penalty=self.domain_penalty,
                )
                return await fallback.run(seed_id=resolved_seed)
            raise RuntimeError(
                f"No traversal path found from seed {resolved_seed}. "
                "Graph may be too sparse — ingest more nodes and edges first."
            )

        path_ids: list[uuid.UUID] = list(cte_row.path_ids)
        path_domains: list[str] = list(cte_row.path_domains)
        total_distance: float = float(cte_row.total_distance)
        hop_count: int = int(cte_row.hop_count)

        logger.info(
            "CTE walk: %d hops, domains=%s, score=%.4f",
            hop_count, path_domains, total_distance,
        )

        # Step 3: hydrate full node objects in path order
        nodes = await self._hydrate_nodes(path_ids)

        return TraversalResult(
            seed_id=resolved_seed,
            path=nodes,
            path_domains=path_domains,
            total_distance=total_distance,
            hop_count=hop_count,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _resolve_seed(self, seed_id: Optional[uuid.UUID]) -> uuid.UUID:
        """Return provided seed, or pick a random one from the database."""
        if seed_id is not None:
            return seed_id

        result = await self.db.execute(text(RANDOM_SEED_QUERY))
        row = result.fetchone()
        if row is None:
            raise ValueError(
                "No nodes with edges found in the database. "
                "Run the ingestion pipeline first."
            )
        return row[0]

    async def _execute_cte(self, seed_id: uuid.UUID):
        """
        Execute the novelty walk CTE and return the raw result row, or None
        if the graph cannot produce a complete path.
        """
        result = await self.db.execute(
            text(NOVELTY_WALK_CTE),
            {
                "seed_id": seed_id,
                "max_hops": self.max_hops,
                "domain_penalty": self.domain_penalty,
            },
        )
        return result.fetchone()

    async def _hydrate_nodes(self, path_ids: list[uuid.UUID]) -> list[PathNode]:
        """
        Fetch full node rows for each ID in path order.
        Uses array_position to preserve traversal ordering in SQL.
        """
        result = await self.db.execute(
            text(HYDRATE_PATH_NODES),
            {"path_ids": path_ids},
        )
        rows = result.fetchall()
        return [
            PathNode(
                id=row.id,
                title=row.title,
                domain=row.domain,
                node_type=row.node_type,
                summary=row.summary,
            )
            for row in rows
        ]
