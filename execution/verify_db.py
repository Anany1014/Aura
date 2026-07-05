#!/usr/bin/env python3
"""
Verification Script (Layer 3)
Verifies database schema setup, file structures, and runs a mock end-to-end simulation of the pipeline.
"""

import os
import sys
import json
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to sys.path to support importing execution package
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Color codes
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_RESET = "\033[0m"


def check_file_path(path: str, required: bool = True) -> bool:
    """Verifies if a specific path exists."""
    exists = os.path.exists(path)
    if exists:
        logger.info(f"Checking {path}: {COLOR_GREEN}EXISTS{COLOR_RESET}")
        return True
    else:
        status = f"{COLOR_RED}MISSING{COLOR_RESET}" if required else f"{COLOR_YELLOW}OPTIONAL (MISSING){COLOR_RESET}"
        logger.info(f"Checking {path}: {status}")
        return False


def verify_db_connection() -> bool:
    """Attempting verification of database schemas if PostgreSQL driver is present."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.info("DATABASE_URL environment variable is not defined. Skipping DB validation.")
        return False
        
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # Check tables
        tables = ["nodes", "edges", "cognee_metadata"]
        for table in tables:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '%s'
                );
            """ % table)
            exists = cur.fetchone()[0]
            status = f"{COLOR_GREEN}FOUND{COLOR_RESET}" if exists else f"{COLOR_RED}NOT FOUND (Run schema.sql){COLOR_RESET}"
            logger.info(f"Database Table '{table}': {status}")
            
        cur.close()
        conn.close()
        return True
    except ImportError:
        logger.warning("psycopg2 is not installed. Database connection cannot be verified.")
        return False
    except Exception as e:
        logger.error(f"Failed to connect or verify tables: {e}")
        return False


def run_e2e_simulation():
    """Runs a simulated end-to-end traversal/synthesis loop to verify logic chains."""
    logger.info("============== Running E2E Simulation ==============")
    try:
        from execution.ingest import IngestionPipeline
        from execution.traverse import TraversalEngine
        from execution.synthesize import IdeaSynthesizer
        from execution.evaluate import NoveltyCritic
        
        # 1. Ingest input
        test_payload = {
            "title": "Decentralized Biomaterial Mesh Supply Chains",
            "domain": "materials_science",
            "type": "startup",
            "summary": "Proposes mesh network topologies to allocate bio-material components safely over decentralized manufacturing plants.",
            "content": "Full description of decentralized systems for biophysiological grid mesh planning..."
        }
        logger.info("Simulating Step 1: Ingesting Node...")
        pipeline = IngestionPipeline()
        pipeline.run(test_payload)
        
        # 2. Traverse Graph
        logger.info("Simulating Step 2: Traversal Walk...")
        traverse = TraversalEngine()
        traverse.walk(max_hops=3)
        
        # 3. Idea Synthesis
        logger.info("Simulating Step 3: Synthesis Generation...")
        synth = IdeaSynthesizer()
        synth.run()
        
        # 4. Critic Evaluation
        logger.info("Simulating Step 4: Critic Scoring...")
        critic = NoveltyCritic()
        passed = critic.run()
        
        logger.info(f" E2E Pipeline run verification: {COLOR_GREEN}SUCCESSFUL (Verdict: {passed}){COLOR_RESET}")
        return True
    except Exception as e:
        logger.error(f"E2E Pipeline run verification: {COLOR_RED}FAILED ({e}){COLOR_RESET}", exc_info=True)
        return False


def main():
    logger.info("=== Starting Structure and Integrity Verification ===")
    
    # Check directory layouts
    dirs = [
        "directives",
        "execution",
        ".tmp"
    ]
    for d in dirs:
        check_file_path(d)
        
    # Check configs
    check_file_path(".gitignore")
    check_file_path(".env.example")
    check_file_path("AGENTS.md")
    
    # Check Layer 1 Directives
    directives = [
        "directives/1_ingest.md",
        "directives/2_traverse.md",
        "directives/3_synthesize.md",
        "directives/4_criticize.md"
    ]
    for directive in directives:
        check_file_path(directive)
        
    # Check Layer 3 Scripts
    scripts = [
        "execution/schema.sql",
        "execution/ingest.py",
        "execution/traverse.py",
        "execution/synthesize.py",
        "execution/evaluate.py"
    ]
    for script in scripts:
        check_file_path(script)
        
    # Check db
    verify_db_connection()
    
    # Run test loop
    run_e2e_simulation()


if __name__ == "__main__":
    main()
