"""
FastAPI Router — Phase 6
=========================
Exposes the core HTTP surface for the Aura MVP.
Includes:
- POST /api/ingest: Ingest structured text/concepts
- POST /api/ingest/file: Ingest uploaded PDF, DOCX, or TXT file
- POST /api/traverse: Perform novelty walk (PostgreSQL CTE)
- POST /api/discover: Run end-to-end traversal + synthesis + critique pipeline
- GET /api/ideas: Fetch generated startup ideas
- GET /api/memory/status: Query budget-gated memory ledger headroom
"""

import logging
import uuid
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

from app.core.database import get_db
from app.core.models import Node, Edge, Idea
from app.ingestion.service import IngestionService
from app.traversal.engine import TraversalEngine
from app.synthesis.service import IdeaSynthesizer, NoveltyCritic
from app.memory.cognee_adapter import CogneeAdapter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Pydantic Schemas for Request / Response validation
# ---------------------------------------------------------------------------
class IngestRequest(BaseModel):
    title: str = Field(..., description="Title of the paper, document, or concept")
    domain: str = Field(..., description="Domain/industry, e.g. biotech, fintech")
    type: str = Field(..., description="Node relationship type, e.g. paper, patent, code")
    summary: Optional[str] = Field(None, description="Optional brief summary to vectorise")
    content: str = Field("", description="Raw source text")


class TraverseRequest(BaseModel):
    seed_id: Optional[uuid.UUID] = Field(None, description="Starting node UUID")
    max_hops: int = Field(3, ge=2, le=5, description="Depth of recursive walk (2-5)")
    domain_penalty: float = Field(0.3, ge=0.0, le=1.0, description="Multiplier for domain repeats")


class DiscoverRequest(BaseModel):
    seed_id: Optional[uuid.UUID] = Field(None, description="Starting node UUID")
    max_hops: int = Field(3, ge=2, le=5, description="Depth of recursive walk (2-5)")
    domain_penalty: float = Field(0.3, ge=0.0, le=1.0, description="Multiplier for domain repeats")


# ---------------------------------------------------------------------------
# Helper: Parse uploaded file bytes into plain text
# ---------------------------------------------------------------------------
def _extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    """
    Extracts plain text from uploaded files.
    Supports: PDF (.pdf), Word (.docx), Markdown (.md), and plain text (.txt, others).
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"

    if ext == "pdf":
        try:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(file_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(pages).strip()
        except Exception as e:
            raise ValueError(f"Failed to parse PDF: {e}")

    elif ext == "docx":
        try:
            import io
            import zipfile
            import xml.etree.ElementTree as ET
            # .docx is a ZIP archive; extract word/document.xml for text
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                with z.open("word/document.xml") as xf:
                    tree = ET.parse(xf)
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            texts = [node.text for node in tree.findall(".//w:t", ns) if node.text]
            return " ".join(texts).strip()
        except Exception as e:
            raise ValueError(f"Failed to parse DOCX: {e}")

    else:
        # Plain text / markdown / unknown — decode as UTF-8 with fallback
        try:
            return file_bytes.decode("utf-8").strip()
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1").strip()


# ---------------------------------------------------------------------------
# Endpoint 1: Ingestion (structured / programmatic)
# ---------------------------------------------------------------------------
@router.post("/ingest", status_code=201)
async def ingest_source(payload: IngestRequest, db: AsyncSession = Depends(get_db)):
    """
    Ingests any structured concept (text / summary).
    Generates embedding vector (OpenAI), saves node, and automatically computes
    proximity edges against existing nodes.
    """
    service = IngestionService(db)
    try:
        node = await service.ingest(
            title=payload.title,
            domain=payload.domain,
            node_type=payload.type,
            summary=payload.summary,
            content=payload.content
        )
        return {
            "status": "success",
            "message": "Node successfully ingested",
            "node": {
                "id": str(node.id),
                "title": node.title,
                "domain": node.domain,
                "node_type": node.node_type,
                "summary": node.summary
            }
        }
    except Exception as e:
        logger.exception("Failed to ingest node '%s'", payload.title)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


# ---------------------------------------------------------------------------
# Endpoint 1b: Ingest Uploaded File (PDF / DOCX / TXT / MD / plain text idea)
# ---------------------------------------------------------------------------
@router.post("/ingest/file", status_code=201)
async def ingest_uploaded_file(
    title: str = Form(..., description="Title of the idea, paper, or concept"),
    domain: str = Form(..., description="Domain e.g. biotech, fintech, gaming, sustainability"),
    node_type: str = Form("document", description="Node type e.g. paper, patent, startup, code, document"),
    file: Optional[UploadFile] = File(None, description="PDF, DOCX, TXT, or MD file to upload"),
    text_content: Optional[str] = Form(None, description="Raw text / idea description (used if no file uploaded)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Ingests a user-uploaded file or raw text idea into the semantic graph.

    Workflow:
    1. Extracts text from file (PDF, DOCX, TXT) or uses raw text_content.
    2. Ingests the extracted text as a graph node (vectorized via OpenAI).
    3. Logs the file ingestion decision to Cognee memory.
    """
    # Resolve content source
    if file and file.filename:
        raw_bytes = await file.read()
        try:
            content = _extract_text_from_file(file.filename, raw_bytes)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        source_label = file.filename
    elif text_content and text_content.strip():
        content = text_content.strip()
        source_label = "text_input"
    else:
        raise HTTPException(
            status_code=400,
            detail="Either a file upload or text_content must be provided."
        )

    if not content:
        raise HTTPException(
            status_code=422,
            detail="Extracted content is empty. Please provide a more detailed document or text."
        )

    service = IngestionService(db)
    adapter = CogneeAdapter()

    try:
        node = await service.ingest(
            title=title,
            domain=domain,
            node_type=node_type,
            content=content
        )

        # Log to Cognee memory (budget-safe — lightweight metadata only)
        await adapter.log_schema_decision(
            key=f"file_ingest_{node.title.lower().replace(' ', '_')[:40]}",
            payload={
                "node_id": str(node.id),
                "title": node.title,
                "domain": node.domain,
                "node_type": node.node_type,
                "summary": node.summary,
                "source": source_label,
                "action": "user_upload_ingested"
            }
        )

        return {
            "status": "success",
            "message": f"Successfully ingested '{title}' from {source_label} into Cognee Memory",
            "node": {
                "id": str(node.id),
                "title": node.title,
                "domain": node.domain,
                "node_type": node.node_type,
                "summary": node.summary,
                "source": source_label
            }
        }
    except Exception as e:
        logger.exception("Failed to ingest uploaded file '%s'", title)
        raise HTTPException(status_code=500, detail=f"File ingestion failed: {str(e)}")


# ---------------------------------------------------------------------------
# Endpoint 2: Traversal Walk
# ---------------------------------------------------------------------------
@router.post("/traverse")
async def run_traversal(payload: TraverseRequest, db: AsyncSession = Depends(get_db)):
    """
    Executes the greedy Postgres CTE novelty traversal query starting from
    the specified seed (or a random seed with edges if omitted).
    """
    engine = TraversalEngine(db, max_hops=payload.max_hops, domain_penalty=payload.domain_penalty)
    try:
        result = await engine.run(seed_id=payload.seed_id)
        return result.to_dict()
    except ValueError as e:
        # e.g. empty graph
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        # e.g. sparse graph traversal failed
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Error executing recursive CTE walk")
        raise HTTPException(status_code=500, detail=f"Traversal failed: {str(e)}")


# ---------------------------------------------------------------------------
# Endpoint 3: End-to-End Idea Discovery (Traverse + Synthesise + Criticise)
# ---------------------------------------------------------------------------
@router.post("/discover")
async def discover_idea(payload: DiscoverRequest, db: AsyncSession = Depends(get_db)):
    """
    Executes the full Aura loop:
    1. Traverses the graph to maximize semantic distance and cross-domain jumps.
    2. Passes path summaries to Claude to synthesize a structured JSON startup idea.
    3. Runs an evaluation pass grading the idea (cross-domain synthesis, market gap, feasibility).
    4. GATES THE OUTCOME:
       - If score >= 8.0: Saves idea to the postgres `ideas` table.
       - If score < 8.0: Logs failed pattern to Cognee for optimization heuristics.
    """
    # Step 1: Traversal
    engine = TraversalEngine(db, max_hops=payload.max_hops, domain_penalty=payload.domain_penalty)
    try:
        walk = await engine.run(seed_id=payload.seed_id)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Discovery failed at traversal stage: {str(e)}")

    # Step 2: Synthesis
    synthesizer = IdeaSynthesizer()
    try:
        idea_data = await synthesizer.synthesize(walk.path)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Discovery failed at synthesis stage: {str(e)}")

    # Step 3: Novelty Critic
    critic = NoveltyCritic()
    try:
        eval_metrics, avg_score = await critic.evaluate(idea_data)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Discovery failed at evaluation stage: {str(e)}")

    # Step 4: Gate and Store
    verdict = "REJECT"
    idea_id = None
    cognee_record = None

    from app.core.config import settings

    if avg_score >= 8.0:
        verdict = "PASS"
        if settings.SIMULATION_MODE:
            logger.info("[SIMULATION] Bypassing PostgreSQL write for winning idea")
            idea_id = str(uuid.uuid4())
        else:
            # Save to database ideas table
            idea_model = Idea(
                name=idea_data.get("name", "Untitled Synthesis"),
                problem_statement=idea_data.get("problem_statement", ""),
                insight_from_path=idea_data.get("insight_from_path", ""),
                solution=idea_data.get("solution", ""),
                mvp_architecture=idea_data.get("mvp_architecture", ""),
                risks=idea_data.get("risks", ""),
                critique_score=round(avg_score, 4)
            )
            db.add(idea_model)
            await db.commit()
            idea_id = str(idea_model.id)
            logger.info("Discover VERDICT: PASS (%.2f/10.0) | Saved Idea id=%s name='%s'", avg_score, idea_id, idea_model.name)
    else:
        # Save failed pattern to CogneeAdapter
        adapter = CogneeAdapter()
        try:
            cognee_record = await adapter.log_idea_pattern(
                verdict="rejected",
                idea_name=idea_data.get("name", "Unknown"),
                scores={
                    "cross_domain_synthesis": eval_metrics.get("cross_domain_synthesis", 0.0),
                    "market_gap": eval_metrics.get("market_gap", 0.0),
                    "low_budget_feasibility": eval_metrics.get("low_budget_feasibility", 0.0)
                },
                domains_traversed=walk.path_domains,
                aggregate_score=avg_score
            )
            # Log changes to the local ledger (non-blocking)
            logger.info("Discover VERDICT: REJECT (%.2f/10.0) | Logged to Cognee id=%s", avg_score, cognee_record)
        except Exception as ce:
            logger.error("Failed to write rejected pattern to Cognee: %s", ce)

    return {
        "verdict": verdict,
        "score": round(avg_score, 2),
        "evaluation": eval_metrics,
        "idea": idea_data,
        "database_idea_id": idea_id,
        "cognee_record_id": cognee_record,
        "traversed_path": walk.to_dict()
    }


# ---------------------------------------------------------------------------
# Endpoint 4: Fetch ideas
# ---------------------------------------------------------------------------
@router.get("/ideas", response_model=List[Dict[str, Any]])
async def list_ideas(
    min_score: float = Query(0.0, ge=0.0, le=10.0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists previously synthesized startup ideas.
    Default ordering: newest first.
    Filters by minimum critique score if specified.
    """
    from app.core.config import settings

    if settings.SIMULATION_MODE:
        logger.info("[SIMULATION] Returning mock ideas list")
        return [
            {
                "id": str(uuid.uuid4()),
                "name": "ProteicRoute AI",
                "problem_statement": "Logistics companies use static route optimization plans...",
                "insight_from_path": "Combining 3D protein structure sequencing with Deep Q-networks...",
                "solution": "A middleware routing engine that models schedules as polypeptides...",
                "mvp_architecture": "FastAPI service deploying PyTorch model weights...",
                "risks": "High computational overhead for translation layer...",
                "critique_score": 8.5,
                "created_at": "2026-07-03T16:00:00"
            }
        ]

    stmt = (
        select(Idea)
        .where(Idea.critique_score >= min_score)
        .order_by(desc(Idea.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    ideas = result.scalars().all()
    return [
        {
            "id": str(i.id),
            "name": i.name,
            "problem_statement": i.problem_statement,
            "insight_from_path": i.insight_from_path,
            "solution": i.solution,
            "mvp_architecture": i.mvp_architecture,
            "risks": i.risks,
            "critique_score": i.critique_score,
            "created_at": i.created_at.isoformat() if i.created_at else None
        }
        for i in ideas
    ]


# ---------------------------------------------------------------------------
# Endpoint 5: Cognee memory status monitor
# ---------------------------------------------------------------------------
@router.get("/memory/status")
async def get_memory_status():
    """
    Returns current Cognee budget allocation, bytes used, and headroom.
    Ensures operational budget constraints ($25/mo) are transparent.
    """
    adapter = CogneeAdapter()
    return adapter.memory_status()
