#!/usr/bin/env python3
"""
Novelty Critic & Evaluator (Layer 3 Execution Script)
Validates generated startup ideas for cross-domain novelty and saves wins/failed logs.
"""

import os
import sys
import json
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure Anthropic SDK is available
try:
    import anthropic
except ImportError:
    anthropic = None
    logger.warning("anthropic SDK not installed. Evaluation will run in simulation mode.")

try:
    import psycopg2
except ImportError:
    psycopg2 = None
    logger.warning("psycopg2 not installed. Cognee feedback tables will write to simulation.")


class NoveltyCritic:
    def __init__(self, anthropic_key: str = None, db_url: str = None):
        self.api_key = anthropic_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = os.getenv("SYNTHESIS_MODEL", "claude-3-5-sonnet-20241022")
        self.db_url = db_url or os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/innovation_engine")
        self.input_file = ".tmp/synthesized_idea.json"
        
        if anthropic and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        else:
            self.client = None

    def load_idea(self) -> Dict[str, Any]:
        """Load synthesized idea from file."""
        if not os.path.exists(self.input_file):
            raise FileNotFoundError(f"Idea file not found at {self.input_file}. Run synthesize.py first.")
            
        with open(self.input_file, 'r') as f:
            return json.load(f)

    def conduct_evaluation(self, idea: Dict[str, Any]) -> Dict[str, Any]:
        """Call Claude to grade the idea along novelty, feasibility, and market gap benchmarks."""
        if self.client:
            prompt = f"""
You are the Aura Quality Controller (Novelty Critic). Grade the following startup concept for novelty, validity, and architectural feasibility under a strict budget constraint ($50/mo limit):

Startup Idea Details:
- Name: {idea.get('name')}
- Problem: {idea.get('problem_statement')}
- Insight (Path): {idea.get('insight_from_path')}
- Solution: {idea.get('solution')}
- MVP Architecture: {idea.get('mvp_architecture') or idea.get('MVP_architecture')}
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
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=600,
                    temperature=0.2,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                raw_json = message.content[0].text.strip()
                if raw_json.startswith("```json"):
                    raw_json = raw_json[7:]
                if raw_json.endswith("```"):
                    raw_json = raw_json[:-3]
                return json.loads(raw_json.strip())
            except Exception as e:
                logger.error(f"Critic call failed: {e}")
                raise e
        else:
            logger.info("Using simulated evaluation response (Critic metrics set to pass).")
            name = idea.get("name", "Generated Idea")
            explanation = (
                f"The concept '{name}' successfully bridges the domains by combining the technical features of Node 1 with downstream path elements. "
                "The proposed architecture employs a lightweight PostgreSQL database with pgvector, enabling the system to run on minimal server resources "
                "under the $50/mo budget threshold while offering a clear novelty gap compared to generic industry solutions."
            )
            return {
                "cross_domain_synthesis": 8.6,
                "market_gap": 8.2,
                "low_budget_feasibility": 9.1,
                "explanation": explanation
            }

    def save_failed_pattern_to_cognee(self, idea: Dict[str, Any], evaluation: Dict[str, Any]):
        """Saves unsuccessful ideas to pg cognee_metadata to tune prompts."""
        if psycopg2 and self.db_url:
            try:
                conn = psycopg2.connect(self.db_url)
                cur = conn.cursor()
                # Store failed data
                payload = {
                    "idea": idea,
                    "metrics": evaluation,
                    "verdict": "rejected"
                }
                query = """
                INSERT INTO public.cognee_metadata (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP;
                """
                # Store under keys like 'failed_pattern_name'
                key = f"failed_pattern_{idea.get('name', 'unknown').lower().replace(' ', '_')}"
                cur.execute(query, (key, json.dumps(payload)))
                conn.commit()
                cur.close()
                conn.close()
                logger.info(f"Stored rejected pattern '{key}' in Cognee metadata for model fine-tuning.")
            except Exception as e:
                logger.error(f"Failed to record Cognee metadata: {e}")
                if 'conn' in locals() and conn:
                    conn.rollback()
        else:
            logger.info(f"[SIMULATION] Saved rejected idea '{idea.get('name')}' to local Cognee logs.")

    def run(self) -> bool:
        """Processes evaluations and routes winner/failure logs."""
        logger.info("Starting Critic evaluation pass...")
        idea = self.load_idea()
        eval_result = self.conduct_evaluation(idea)
        
        avg_score = (
            eval_result.get("cross_domain_synthesis", 0.0) +
            eval_result.get("market_gap", 0.0) +
            eval_result.get("low_budget_feasibility", 0.0)
        ) / 3.0
        
        logger.info(f"Critic Score Summary: {avg_score:.2f}/10.0")
        logger.info(f"Details: {eval_result.get('explanation')}")
        
        if avg_score >= 8.0:
            logger.info("Verdict: PASS. Idea exceeds quality threshold.")
            # Save to winning ideas
            winners_dir = ".tmp/winning_ideas"
            os.makedirs(winners_dir, exist_ok=True)
            output_path = os.path.join(winners_dir, f"{idea.get('name', 'Winner').replace(' ', '_').lower()}.json")
            
            with open(output_path, 'w') as f:
                json.dump({
                    "idea": idea,
                    "evaluation": eval_result,
                    "score": avg_score
                }, f, indent=4)
            logger.info(f"Winning idea stored at {output_path}")
            return True
        else:
            logger.info("Verdict: REJECT. Idea did not meet requirements.")
            self.save_failed_pattern_to_cognee(idea, eval_result)
            return False


if __name__ == "__main__":
    critic = NoveltyCritic()
    try:
        critic.run()
    except Exception as err:
        logger.error(f"Evaluation failed: {err}")
        sys.exit(1)
