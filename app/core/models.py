import uuid
from sqlalchemy import Column, String, Text, ForeignKey, Float, DateTime, text, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.core.database import Base


class Node(Base):
    __tablename__ = "nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    domain = Column(String(100), nullable=False)    # e.g. "biotech", "fintech"
    node_type = Column(String(50), nullable=False)  # renamed: "type" shadows Python builtin
    summary = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True) # OpenAI text-embedding-3-small = 1536 dims
    created_at = Column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        Index("idx_nodes_domain", "domain"),
        Index("idx_nodes_type", "node_type"),
        # HNSW index for fast approximate cosine nearest-neighbour search.
        # - postgresql_using: index method
        # - postgresql_with: HNSW build params (m = max links/node, ef_construction = search width during build)
        # - postgresql_ops: per-column operator class (cosine distance for pgvector)
        Index(
            "idx_nodes_embedding_cosine",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class Edge(Base):
    __tablename__ = "edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type = Column(String(50), nullable=False)  # "references", "implements", "competes_with"
    semantic_distance = Column(Float, nullable=False)        # cosine distance ∈ [0, 2]
    created_at = Column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        Index("idx_edges_source", "source_node_id"),
        Index("idx_edges_target", "target_node_id"),
        # Traversal queries ORDER BY semantic_distance DESC — explicit index helps
        Index("idx_edges_semantic_distance", "semantic_distance"),
        # Use UniqueConstraint (not Index with unique=True) for multi-column uniqueness —
        # this is the correct SQLAlchemy pattern and generates a proper DB UNIQUE constraint.
        UniqueConstraint(
            "source_node_id",
            "target_node_id",
            "relationship_type",
            name="uq_source_target_rel",
        ),
    )


class Idea(Base):
    __tablename__ = "ideas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    problem_statement = Column(Text, nullable=False)
    insight_from_path = Column(Text, nullable=False)
    solution = Column(Text, nullable=False)
    mvp_architecture = Column(Text, nullable=False)  # lowercase snake_case per SQLAlchemy convention
    risks = Column(Text, nullable=False)
    critique_score = Column(Float, nullable=True)    # Aggregate novelty critic score (0–10)
    created_at = Column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        # Daily cron queries filter by score >= 8.0 and order by recency
        Index("idx_ideas_critique_score", "critique_score"),
        Index("idx_ideas_created_at", "created_at"),
    )
