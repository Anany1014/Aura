#!/usr/bin/env python3
"""
Ingestion Pipeline (Layer 3 Execution Script)
Handles parsing documents, generating embeddings, and storing nodes and edges.
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
    logger.warning("psycopg2 not installed. PostgreSQL operations will run in simulation mode.")

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
    logger.warning("openai not installed. Embedding generation will run in simulation mode.")


class IngestionPipeline:
    def __init__(self, db_url: str = None, openai_api_key: str = None):
        self.db_url = db_url or os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/innovation_engine")
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key) if (OpenAI and self.api_key) else None

    def chunk_text(self, text: str, chunk_size: int = 8000) -> List[str]:
        """Split text into smaller chunks based on size constraints."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        words = text.split()
        current_chunk = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 > chunk_size:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_length = len(word)
            else:
                current_chunk.append(word)
                current_length += len(word) + 1
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
            
        return chunks

    def generate_embedding(self, text: str) -> List[float]:
        """Generate a 1536-dimensional embedding using OpenAI (or mock vector if simulated)."""
        if self.client:
            try:
                response = self.client.embeddings.create(
                    input=[text],
                    model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
                )
                return response.data[0].embedding
            except Exception as e:
                logger.error(f"Failed to generate embedding from OpenAI: {e}")
                raise e
        else:
            logger.info("OpenAI client not configured. Generating static/simulated 1536-dimension vector.")
            # return a dummy 1536 vector for validation/test flow stability
            import random
            random.seed(hash(text))
            vector = [random.uniform(-1, 1) for _ in range(1536)]
            # normalize vector
            magnitude = sum(x*x for x in vector) ** 0.5
            return [x/magnitude for x in vector]

    def save_node(self, title: str, domain: str, node_type: str, summary: str, embedding: List[float]) -> str:
        """Saves a node to postgres and returns its UUID."""
        if psycopg2 and self.db_url:
            try:
                conn = psycopg2.connect(self.db_url)
                cur = conn.cursor()
                # Upsert query using title/domain unique constraints or basic checks
                query = """
                INSERT INTO public.nodes (title, domain, type, summary, embedding)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """
                cur.execute(query, (title, domain, node_type, summary, embedding))
                node_id = cur.fetchone()[0]
                conn.commit()
                cur.close()
                conn.close()
                logger.info(f"Successfully saved node: {title} with ID {node_id}")
                return str(node_id)
            except Exception as e:
                logger.error(f"Failed to save node to PostgreSQL: {e}")
                if 'conn' in locals() and conn:
                    conn.rollback()
                raise e
        else:
            # Simulate DB output UUID
            import uuid
            node_id = str(uuid.uuid4())
            logger.info(f"[SIMULATION] Saved node: '{title}' in domain '{domain}' with ID: {node_id}")
            return node_id

    def create_edges_for_node(self, new_node_id: str, new_node_embedding: List[float]) -> int:
        """Finds other nodes in database and inserts proximity edges based on cosine similarity."""
        if psycopg2 and self.db_url:
            try:
                conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
                cur = conn.cursor()
                
                # Fetch sibling nodes to calculate distance. Using pgvector operator <=> (cosine distance)
                query = """
                SELECT id, title, type, (embedding <=> %s::vector) AS similarity_distance 
                FROM public.nodes 
                WHERE id != %s 
                ORDER BY embedding <=> %s::vector
                LIMIT 10;
                """
                cur.execute(query, (new_node_embedding, new_node_id, new_node_embedding))
                candidates = cur.fetchall()
                
                edge_count = 0
                for cand in candidates:
                    distance = float(cand['similarity_distance'])
                    # If distance is low (closer resemblance) or we force connections for small networks
                    if distance < 0.4: 
                        rel_type = "references" if cand['type'] == 'paper' else "competes_with"
                        edge_query = """
                        INSERT INTO public.edges (source_node_id, target_node_id, relationship_type, semantic_distance)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (source_node_id, target_node_id, relationship_type) DO NOTHING;
                        """
                        cur.execute(edge_query, (new_node_id, cand['id'], rel_type, distance))
                        edge_count += 1
                
                conn.commit()
                cur.close()
                conn.close()
                logger.info(f"Created {edge_count} relation edges for node: {new_node_id}")
                return edge_count
            except Exception as e:
                logger.error(f"Failed to create edges: {e}")
                if 'conn' in locals() and conn:
                    conn.rollback()
                raise e
        else:
            logger.info(f"[SIMULATION] Running relation logic. Mocking 3 edges for node ID: {new_node_id}")
            return 3

    def run(self, data: Dict[str, Any]) -> str:
        """Main execution entry point."""
        logger.info(f"Starting ingestion process for node: {data.get('title')}")
        chunks = self.chunk_text(data.get("content", ""))
        
        # Summarize chunks if too complex (simplified view maps first chunk summary)
        summary = data.get("summary") or chunks[0][:300] + "..."
        
        embedding = self.generate_embedding(summary)
        node_id = self.save_node(
            title=data.get("title", "Untitled Node"),
            domain=data.get("domain", "general"),
            node_type=data.get("type", "general"),
            summary=summary,
            embedding=embedding
        )
        self.create_edges_for_node(node_id, embedding)
        return node_id


if __name__ == "__main__":
    # If run standalone, allow parsing a JSON file or running a direct test case
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        try:
            with open(file_path, 'r') as f:
                payload = json.load(f)
            pipeline = IngestionPipeline()
            pipeline.run(payload)
        except Exception as err:
            logger.error(f"Run failed: {err}")
            sys.exit(1)
    else:
        logger.info("No input file provided. Running mock ingestion pipeline test case.")
        test_payload = {
            "title": "Quantum Deep Learning for Logistic Route Optimization",
            "domain": "quantum_computing",
            "type": "paper",
            "summary": "This research outlines the synthesis of quantum annealers to optimize cargo route constraints dynamically.",
            "content": "Full academic text details quantum gates being applied to solve TSP problems..."
        }
        pipeline = IngestionPipeline()
        pipeline.run(test_payload)
