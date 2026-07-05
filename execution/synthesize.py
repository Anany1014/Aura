#!/usr/bin/env python3
"""
Idea Synthesizer (Layer 3 Execution Script)
Ingests traversal hops and queries LLM (Claude) to render cohesive startup ideas.
"""

import os
import sys
import json
import logging
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure Anthropic SDK is available
try:
    import anthropic
except ImportError:
    anthropic = None
    logger.warning("anthropic SDK not installed. Synthesis will run in simulation mode.")


class IdeaSynthesizer:
    def __init__(self, anthropic_key: str = None):
        self.api_key = anthropic_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = os.getenv("SYNTHESIS_MODEL", "claude-3-5-sonnet-20241022")
        self.input_file = ".tmp/latest_traversal.json"
        self.output_file = ".tmp/synthesized_idea.json"
        
        if anthropic and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        else:
            self.client = None

    def load_path(self) -> List[Dict[str, Any]]:
        """Loads latest traversed nodes."""
        if not os.path.exists(self.input_file):
            raise FileNotFoundError(f"Traversal path file not found at {self.input_file}. Run traverse.py first.")
            
        with open(self.input_file, 'r') as f:
            return json.load(f)

    def build_prompt(self, path: List[Dict[str, Any]]) -> str:
        """Constructs system & user details forcing cross-domain synthesis."""
        doc_context = ""
        for idx, node in enumerate(path):
            doc_context += f"Node {idx + 1}:\n"
            doc_context += f"- Title: {node.get('title')}\n"
            doc_context += f"- Domain: {node.get('domain')}\n"
            doc_context += f"- Type: {node.get('type') or node.get('node_type')}\n"
            doc_context += f"- Summary: {node.get('summary')}\n\n"
            
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

    def query_claude(self, prompt: str) -> str:
        """Call Claude to generate the idea, fallback to simulation if SDK unavailable."""
        if self.client:
            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    temperature=0.7,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                content = message.content[0].text
                return content
            except Exception as e:
                logger.error(f"Claude API request failed: {e}")
                raise e
        else:
            logger.info("Using simulation response mode for Idea Synthesis.")
            # Dynamic high-fidelity mock generator using path elements
            if not self.input_file or not os.path.exists(self.input_file):
                # Fallback path if latest_traversal.json is missing during testing
                path = [
                    {"title": "Decentralized Biomaterial Mesh Supply Chains", "domain": "materials_science", "summary": "Proposes mesh network topologies."},
                    {"title": "Quantum Cryptographic Distributed Scaling", "domain": "cryptography", "summary": "Quantum scaling."},
                    {"title": "Realtime Cargo Logistics Routing", "domain": "logistics", "summary": "Cargo routing."}
                ]
            else:
                try:
                    with open(self.input_file, 'r') as f:
                        path = json.load(f)
                except Exception:
                    path = [
                        {"title": "Decentralized Biomaterial Mesh Supply Chains", "domain": "materials_science", "summary": "Proposes mesh network topologies."},
                        {"title": "Quantum Cryptographic Distributed Scaling", "domain": "cryptography", "summary": "Quantum scaling."},
                        {"title": "Realtime Cargo Logistics Routing", "domain": "logistics", "summary": "Cargo routing."}
                    ]

            seed = path[0]
            other_nodes = path[1:]
            downstream_domains = [n.get("domain") for n in other_nodes]
            
            # Clean seed title for name generation
            seed_title_clean = seed.get("title", "Aura").replace("Platform", "").replace("Tracker", "").replace("Engine", "").replace("Hub", "").replace("Bot", "").strip()
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
                f"Traditional workflows in the {seed.get('domain')} domain suffer from massive inefficiencies and static datasets. "
                f"Specifically, applications built around '{seed_title_clean}' lack the capability to leverage "
                f"cross-domain methodologies from {', '.join(downstream_domains)}. This results in rigid APIs, "
                f"delayed route processing, and high computational costs when attempting real-time updates."
            )

            concept_insight = (
                f"Applies techniques from the downstream papers (specifically targeting '{other_nodes[0].get('title') if len(other_nodes) > 0 else ''}') "
                f"to accelerate decision pipelines in the seed concept '{seed.get('title')}'. "
                f"By modeling the seed's underlying structure using algorithms from '{other_nodes[-1].get('title') if len(other_nodes) > 1 else seed.get('title')}', "
                f"we can execute cross-domain jumps that unlock 10x gains in speed and security."
            )

            solution = (
                f"A premium, production-ready SaaS interface called {concept_name} designed to orchestrate '{seed.get('title')}'. "
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
            return json.dumps(mock_idea, indent=4)

    def run(self) -> Dict[str, Any]:
        """Runs the synthesizer script."""
        logger.info("Starting idea synthesis process...")
        path = self.load_path()
        prompt = self.build_prompt(path)
        raw_output = self.query_claude(prompt)
        
        # Clean potential markdown wrappers if returned
        clean_json = raw_output.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        clean_json = clean_json.strip()
        
        try:
            parsed_idea = json.loads(clean_json)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON output: {e}\nRaw output was:\n{raw_output}")
            raise e
            
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        with open(self.output_file, 'w') as f:
            json.dump(parsed_idea, f, indent=4)
            
        logger.info(f"Synthesized idea generated: '{parsed_idea.get('name')}'")
        logger.info(f"Output recorded in {self.output_file}")
        return parsed_idea


if __name__ == "__main__":
    synthesizer = IdeaSynthesizer()
    try:
        synthesizer.run()
    except Exception as err:
        logger.error(f"Synthesis failed: {err}")
        sys.exit(1)
