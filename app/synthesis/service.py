"""
Idea Synthesis & Novelty Critic Service — Phase 5
===================================================
Handles querying Claude to synthesize startup ideas from paths, and evaluates
them under the strict budget limit.
Uses AsyncAnthropic client for non-blocking IO.
"""

import json
import logging
import os
import uuid
from typing import List, Dict, Any, Tuple

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.traversal.engine import PathNode

logger = logging.getLogger(__name__)


class IdeaSynthesizer:
    """
    Forves semantic collisions by prompting Claude with path summaries
    and expecting structured JSON output.
    """

    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        self.model = settings.SYNTHESIS_MODEL
        if self.api_key and not self.api_key.startswith("your_") and not self.api_key.startswith("your-"):
            self.client = AsyncAnthropic(api_key=self.api_key)
        else:
            self.client = None

    def build_prompt(self, path: List[PathNode]) -> str:
        """Constructs prompt focusing Claude on core techniques/domains in path."""
        doc_context = ""
        for idx, node in enumerate(path):
            doc_context += f"Node {idx + 1}:\n"
            doc_context += f"- Title: {node.title}\n"
            doc_context += f"- Domain: {node.domain}\n"
            doc_context += f"- Type: {node.node_type}\n"
            doc_context += f"- Summary: {node.summary}\n\n"

        prompt = f"""
You are the Aura Idea Synthesizer. You generate non-obvious, highly innovative startup concepts by forcing 'semantic collisions' across the following traversed path:

{doc_context}

Create a startup concept that capitalizes on these lateral connections (specifically merging their techniques, insights, or architectures). Your concept must be highly realistic, detailed, and directly grounded in the seed node details (Node 1).

Your response MUST be a single, strict, valid JSON object containing exactly the following keys:
- "name": A unique, creative, and capitalized tech startup name.
- "problem_statement": A detailed, multi-sentence explanation of why the current standard solutions in the seed node's domain fail. Outline specific technical bottlenecks or operational silos.
- "insight_from_path": A detailed explanation (at least 3 sentences) bridging the above domains. Explain exactly how combining the techniques or insights of Node 1 with the downstream nodes creates a novel, previously impossible capability.
- "solution": Core product description including specific features, target user flows, and how the value is delivered. Be concrete, not generic.
- "mvp_architecture": A detailed, multi-step technical architecture outline. Detail: (1) backend framework/libraries, (2) database tables schemas and search/indexing mechanisms (such as pgvector indexes), (3) key external APIs and data flow, and (4) how it runs under a minimal infrastructure resource footprint.
- "risks": Core technical or business failure points, and specific mitigation plans for each risk.

Do not include any other markdown text, chat explanations, or wrapper backticks. Respond only with the JSON entity.
"""
        return prompt

    async def synthesize(self, path: List[PathNode]) -> Dict[str, Any]:
        """Queries Claude to generate the idea, falls back to simulated idea if no API key is set."""
        if not path:
            raise ValueError("Cannot synthesize from an empty path.")

        if self.client:
            try:
                prompt = self.build_prompt(path)
                message = await self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    temperature=0.7,
                    messages=[{"role": "user", "content": prompt}]
                )
                raw_output = message.content[0].text.strip()
                return self._parse_json_response(raw_output)
            except Exception as e:
                logger.error("Claude synthesis API call failed: %s", e)
                raise e
        else:
            logger.info("Using simulated response mode for Idea Synthesis (no Anthropic key).")
            # Dynamic high-fidelity mock generator using path elements
            seed = path[0]
            other_nodes = path[1:]
            downstream_domains = [n.domain for n in other_nodes]
            
            # Clean seed title for name generation
            seed_title_clean = seed.title.replace("Platform", "").replace("Tracker", "").replace("Engine", "").replace("Hub", "").replace("Bot", "").strip()
            name_prefix = seed_title_clean.split()[0] if len(seed_title_clean.split()) > 0 else "Aura"
            
            domain_suffix = "Net"
            if "cryptography" in downstream_domains:
                domain_suffix = "Secure"
            elif "logistics" in downstream_domains:
                domain_suffix = "Flow"
            elif "materials_science" in downstream_domains:
                domain_suffix = "Forge"
            elif "biotech" in downstream_domains:
                domain_suffix = "Bio"
            elif "sustainability" in downstream_domains:
                domain_suffix = "Eco"
            concept_name = f"{name_prefix}{domain_suffix}"

            problem_statement = (
                f"Traditional workflows in the {seed.domain} domain suffer from massive inefficiencies and static datasets. "
                f"Specifically, applications built around '{seed_title_clean}' lack the capability to leverage "
                f"cross-domain methodologies from {', '.join(downstream_domains)}. This results in rigid APIs, "
                f"delayed route processing, and high computational costs when attempting real-time updates."
            )

            concept_insight = (
                f"Applies techniques from the downstream papers (specifically targeting '{path[1].title if len(path) > 1 else ''}') "
                f"to accelerate decision pipelines in the seed concept '{seed.title}'. "
                f"By modeling the seed's underlying structure using algorithms from '{path[-1].title if len(path) > 2 else path[-1].title}', "
                f"we can execute cross-domain jumps that unlock 10x gains in speed and security."
            )

            solution = (
                f"A premium, production-ready SaaS interface called {concept_name} designed to orchestrate '{seed.title}'. "
                f"It operates by capturing input profiles, computing vector proximity hashes, and mapping them "
                f"to optimized target node flows derived from {', '.join(downstream_domains)}."
            )

            mvp_architecture = (
                f"1. Service Core: FastAPI endpoints with structured JSON schemas and async route handlers.\n"
                f"2. Database: PostgreSQL with pgvector extension to store node matrices. Custom SQL schema: "
                f"nodes (id uuid, title varchar, summary text, embedding vector(1536)) and edges (source_id, target_id, rel_type, semantic_distance double precision).\n"
                f"3. Alignment Engine: Local numpy cosine-similarity routines to query proximity edges when running offline.\n"
                f"4. Server Footprint: Uvicorn server running under $15/month VPS with standard memory restrictions."
            )

            risks = (
                f"1. Database Scaling: Postgres CTE recursion length limits performance at high edge densities. Mitigation: Index on source/target and limit hop depth to 3.\n"
                f"2. Model Variance: Embedding model version alignment during data pipeline transitions. Mitigation: Hardcode index embeddings using text-embedding-3-small."
            )

            mock_idea = {
                "name": concept_name,
                "problem_statement": problem_statement,
                "insight_from_path": concept_insight,
                "solution": solution,
                "mvp_architecture": mvp_architecture,
                "risks": risks
            }
            return mock_idea

    def _parse_json_response(self, raw_output: str) -> Dict[str, Any]:
        """Cleans and parses JSON output from Claude."""
        clean_json = raw_output.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        clean_json = clean_json.strip()

        try:
            # Map MVP_architecture key to mvp_architecture if LLM outputs old casing
            data = json.loads(clean_json)
            if "MVP_architecture" in data and "mvp_architecture" not in data:
                data["mvp_architecture"] = data.pop("MVP_architecture")
            return data
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON output. Raw content was:\n%s", raw_output)
            raise ValueError("Synthesizer output was not valid JSON.") from e


class NoveltyCritic:
    """
    Secondary evaluation pass. Grades the idea for cross-domain novelty,
    market gap, and low-budget feasibility.
    """

    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        self.model = settings.SYNTHESIS_MODEL
        if self.api_key and not self.api_key.startswith("your_") and not self.api_key.startswith("your-"):
            self.client = AsyncAnthropic(api_key=self.api_key)
        else:
            self.client = None

    async def evaluate(self, idea: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
        """Grades the idea, returns the detailed evaluation dict and the average score."""
        if self.client:
            prompt = f"""
You are the Aura Quality Controller (Novelty Critic). Grade the following startup concept for novelty, validity, and architectural feasibility under a strict budget constraint ($50/mo limit):

Startup Idea Details:
- Name: {idea.get('name')}
- Problem: {idea.get('problem_statement')}
- Insight (Path): {idea.get('insight_from_path')}
- Solution: {idea.get('solution')}
- MVP Architecture: {idea.get('mvp_architecture')}
- Risks: {idea.get('risks')}

Evaluate the idea along these 3 vectors on a scale of 1.0 to 10.0:
1. cross_domain_synthesis: Does it combine fields in a genuinely non-obvious way? Low score if it is a derivative application (e.g. Uber for X).
2. market_gap: Is it likely that this idea is already heavily occupied or simple?
3. low_budget_feasibility: Can it run under a low infrastructure budget?

Respond ONLY with a valid JSON block containing:
- "cross_domain_synthesis": float,
- "market_gap": float,
- "low_budget_feasibility": float,
- "explanation": brief summary of evaluations.
"""
            try:
                message = await self.client.messages.create(
                    model=self.model,
                    max_tokens=600,
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}]
                )
                raw_json = message.content[0].text.strip()
                if raw_json.startswith("```json"):
                    raw_json = raw_json[7:]
                if raw_json.endswith("```"):
                    raw_json = raw_json[:-3]
                
                eval_result = json.loads(raw_json.strip())
                avg_score = (
                    eval_result.get("cross_domain_synthesis", 0.0) +
                    eval_result.get("market_gap", 0.0) +
                    eval_result.get("low_budget_feasibility", 0.0)
                ) / 3.0
                return eval_result, avg_score
            except Exception as e:
                logger.error("Claude critic API call failed: %s", e)
                raise e
        else:
            logger.info("Using simulated evaluation response (Critic metrics set to pass).")
            name = idea.get("name", "Generated Idea")
            explanation = (
                f"The concept '{name}' successfully bridges the domains by combining the technical features of Node 1 with downstream path elements. "
                "The proposed architecture employs a lightweight PostgreSQL database with pgvector, enabling the system to run on minimal server resources "
                "under the $50/mo budget threshold while offering a clear novelty gap compared to generic industry solutions."
            )
            eval_result = {
                "cross_domain_synthesis": 8.6,
                "market_gap": 8.2,
                "low_budget_feasibility": 9.1,
                "explanation": explanation
            }
            return eval_result, 8.63
