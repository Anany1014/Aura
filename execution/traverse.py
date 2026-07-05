#!/usr/bin/env python3
"""
Traversal Engine (Layer 3 Execution Script)
Finds non-obvious paths through the graph by walking nodes using PostgreSQL or simulations.
"""

import os
import sys
import json
import logging
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure postgres client is available
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    logger.warning("psycopg2 not installed. Database queries will run in simulation mode.")


class TraversalEngine:
    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/innovation_engine")
        self.tmp_output = ".tmp/latest_traversal.json"

    def select_random_seed(self) -> Dict[str, Any]:
        """Fetch a random starting node from database or return simulation fallback."""
        if psycopg2 and self.db_url:
            try:
                conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
                cur = conn.cursor()
                # Find a node that has at least one outgoing edge if possible, else any node
                query = """
                SELECT n.id, n.title, n.domain, n.type, n.summary 
                FROM public.nodes n
                LEFT JOIN public.edges e ON n.id = e.source_node_id
                GROUP BY n.id
                ORDER BY COUNT(e.id) DESC, RANDOM()
                LIMIT 1;
                """
                cur.execute(query)
                res = cur.fetchone()
                cur.close()
                conn.close()
                if res:
                    return dict(res)
            except Exception as e:
                logger.error(f"Failed to fetch seed node from PostgreSQL: {e}")
        
        # Simulation seed fallback if no database connection
        import uuid
        return {
            "id": str(uuid.uuid4()),
            "title": "Alpha-Fold Protein Structure Sequencing API",
            "domain": "biotech",
            "type": "paper",
            "summary": "AI network designed to construct 3D sequence predictions for protein targets."
        }

    def get_neighbors(self, node_id: str, visited_ids: List[str], current_domain: str, diversity: bool = True) -> List[Dict[str, Any]]:
        """Fetch neighboring nodes that have valid edge links and calculate traversal metrics."""
        if psycopg2 and self.db_url:
            try:
                conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
                cur = conn.cursor()
                
                # Fetch sibling nodes attached by edges: maximize semantic distance (lateral thinking)
                # Filter outgoing/incoming edges dynamically
                query = """
                SELECT n.id, n.title, n.domain, n.type, n.summary, e.semantic_distance 
                FROM public.edges e
                JOIN public.nodes n ON (n.id = e.target_node_id OR n.id = e.source_node_id)
                WHERE (e.source_node_id = %s OR e.target_node_id = %s)
                  AND n.id != %s
                  AND n.id NOT IN %s
                """
                params = [node_id, node_id, node_id, tuple(visited_ids) if visited_ids else ('',)]
                
                if diversity:
                    query += " AND n.domain != %s"
                    params.append(current_domain)
                    
                query += " ORDER BY e.semantic_distance DESC LIMIT 5;"
                
                cur.execute(query, params)
                neighbors = cur.fetchall()
                cur.close()
                conn.close()
                return [dict(n) for n in neighbors]
            except Exception as e:
                logger.error(f"Failed to fetch database neighbors: {e}")
                
        # Simulation mock neighbors if local db not set up
        import uuid
        import random
        mock_candidates = [
            {
                "id": str(uuid.uuid4()),
                "title": "Optimizing Delivery Fleets with Deep Q-Networks",
                "domain": "logistics",
                "type": "paper",
                "summary": "Deep reinforcement learning environment applied to resolve time-window delivery scheduling.",
                "semantic_distance": 0.85
            },
            {
                "id": str(uuid.uuid4()),
                "title": "DeFi Collateral Liquidation Risk Heuristics",
                "domain": "fintech",
                "type": "startup",
                "summary": "Risk management analytics for overcollateralized lending protocols on EVM-compatible chains.",
                "semantic_distance": 0.92
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Supply Chain Realtime Ledger System",
                "domain": "supply_chain",
                "type": "code",
                "summary": "Rust library executing high-frequency ledger state entries for inventory transactions.",
                "semantic_distance": 0.78
            }
        ]
        # Return candidates matching requested filter
        filtered = [c for c in mock_candidates if c["id"] not in visited_ids]
        if diversity:
            filtered = [c for c in filtered if c["domain"] != current_domain]
        return filtered

    def walk(self, seed_id: str = None, max_hops: int = 3, domain_diversity: bool = True) -> List[Dict[str, Any]]:
        """Perform recursive graph hops to maximize path distance."""
        path = []
        
        # Step 1: Establish Seed
        if seed_id:
            # Load specific seed from DB or fallback
            pass
        
        seed_node = self.select_random_seed()
        path.append(seed_node)
        
        visited_ids = [seed_node["id"]]
        current_node = seed_node
        
        # Step 2: Traverse
        for hop in range(1, max_hops + 1):
            neighbors = self.get_neighbors(
                current_node["id"], 
                visited_ids, 
                current_node["domain"], 
                domain_diversity
            )
            
            if not neighbors:
                logger.info(f"Dead end met at hop {hop} ('{current_node['title']}'). Backtracking or ending path early.")
                break
                
            # Pick neighbor with highest semantic distance
            next_node = neighbors[0] # Sorted DESC by distance
            path.append(next_node)
            visited_ids.append(next_node["id"])
            current_node = next_node
            
        # Step 3: Write Output to file (Layer 1 handoff)
        os.makedirs(os.path.dirname(self.tmp_output), exist_ok=True)
        with open(self.tmp_output, 'w') as f:
            json.dump(path, f, indent=4)
            
        logger.info(f"Completed random walk: {' -> '.join([node['domain'] for node in path])}")
        logger.info(f"Path results written to {self.tmp_output}")
        return path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Traverse Graph nodes to find weird innovation paths.")
    parser.add_argument("--seed", type=str, help="Specific starting node UUID", default=None)
    parser.add_argument("--hops", type=int, help="Traversal hop depth (3-4)", default=3)
    args = parser.parse_args()
    
    engine = TraversalEngine()
    engine.walk(seed_id=args.seed, max_hops=args.hops)
