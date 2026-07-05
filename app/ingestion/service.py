"""
Ingestion Service — Phase 5
=============================
Async library service for parsing research, summaries, and creating nodes + edges.
Uses the async SQLAlchemy engine and OpenAI embeddings.
"""

import logging
import random
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.models import Node, Edge

logger = logging.getLogger(__name__)


class IngestionService:
    """
    Handles chunking, vectorizing (OpenAI), and storing a new node,
    followed by proximity edge creation using pgvector's cosine distance.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        # Set up OpenAI client asynchronously if API key is provided
        api_key = settings.OPENAI_API_KEY
        if api_key and not api_key.startswith("your_") and not api_key.startswith("your-"):
            self.client = AsyncOpenAI(api_key=api_key)
        else:
            self.client = None

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate a 1536-dim embedding using OpenAI text-embedding-3-small, or mock vector."""
        if self.client:
            try:
                response = await self.client.embeddings.create(
                    input=[text],
                    model=settings.EMBEDDING_MODEL
                )
                return response.data[0].embedding
            except Exception as e:
                logger.error("OpenAI embedding generation failed: %s", e)
                raise e
        else:
            logger.info("OpenAI API key not set. Generating mock normalized 1536-dim vector.")
            # Set seed based on hash of text for stable mock results
            random.seed(hash(text))
            vector = [random.uniform(-1.0, 1.0) for _ in range(1536)]
            # Normalize vector to unit length so cosine distance calculations work correctly
            norm = sum(x * x for x in vector) ** 0.5
            return [x / norm for x in vector]

    async def ingest(
        self,
        title: str,
        domain: str,
        node_type: str,
        summary: Optional[str] = None,
        content: str = "",
    ) -> Node:
        """
        Runs ingestion:
        1. Summarizes content if summary is omitted (or chunks it).
        2. Generates semantic embedding.
        3. Creates the Node.
        4. Calculates distance to other nodes and inserts edges.
        """
        # Determine summary (fallback to content chunk if empty)
        node_summary = summary or (content[:297] + "..." if len(content) > 300 else content)

        # Generate embedding
        embedding = await self.generate_embedding(node_summary)

        # If in Simulation Mode, skip DB transactions and return a mock Node
        if settings.SIMULATION_MODE:
            logger.info("[SIMULATION] Bypassing PostgreSQL write for node '%s'", title)
            import uuid as uuid_lib
            node = Node(
                title=title,
                domain=domain,
                node_type=node_type,
                summary=node_summary,
                embedding=embedding
            )
            node.id = uuid_lib.uuid4()
            return node

        # Create and persist the Node
        node = Node(
            title=title,
            domain=domain,
            node_type=node_type,
            summary=node_summary,
            embedding=embedding
        )
        self.db.add(node)
        await self.db.flush()  # Populates node.id UUID
        logger.info("Created node '%s' in domain '%s' with id=%s", title, domain, node.id)

        # Create relationships to other nearest-neighbour nodes (limit to top 10 closest)
        edge_count = await self._create_proximity_edges(node)
        logger.info("Created %d relation edges for node id=%s", edge_count, node.id)

        await self.db.commit()
        return node

    async def _create_proximity_edges(self, new_node: Node) -> int:
        """
        Calculates distance of new_node against existing nodes.
        Inserts undirected relation edges for those with cosine distance < 0.4.
        """
        # Query nearest neighbors using pgvector's cosine_distance operator.
        # select(Node, Node.embedding.cosine_distance(new_node.embedding))
        query = (
            select(Node, Node.embedding.cosine_distance(new_node.embedding).label("distance"))
            .where(Node.id != new_node.id)
            .order_by("distance")
            .limit(10)
        )
        result = await self.db.execute(query)
        candidates = result.all()

        edge_count = 0
        for other_node, distance in candidates:
            # Connect nodes if they are within similarity threshold (distance < 0.4)
            # Or if database is extremely small, connect to at least 2 nodes to make graph walkable
            if distance < 0.4 or edge_count < 2:
                # Custom relationship mapping based on node type
                if other_node.node_type == "paper":
                    rel_type = "references"
                elif other_node.node_type == "patent":
                    rel_type = "implements"
                else:
                    rel_type = "competes_with"

                # Insert Edge source -> target
                edge = Edge(
                    source_node_id=new_node.id,
                    target_node_id=other_node.id,
                    relationship_type=rel_type,
                    semantic_distance=float(distance)
                )
                self.db.add(edge)
                edge_count += 1

        return edge_count
