# SOP: Idea Synthesizer (Layer 1)

This directive describes how to synthesize a startup idea by connecting semantically distant nodes from a traversed path.

## Objective
Take a traversed graph path (JSON) and prompt the LLM to generate a startup idea capitalizing on the lateral relationships across the path nodes.

## Inputs
- Traversal path JSON file (e.g. from `.tmp/latest_traversal.json`).
- Prompt heuristics or context from Cognee (optional).

## Deterministic Tool
- Script: `execution/synthesize.py`

## Instructions
1. **Load Traversal Path**:
   - Read `.tmp/latest_traversal.json` to extract nodes and summaries.
2. **Context Compilation**:
   - Format node properties (title, domain, type, summary) into a structured markdown block.
3. **Synthesis Prompt Creation**:
   - Construct a prompt instructing the LLM (Claude 3.5 Sonnet) to create a startup concept bridging these domains.
   - Force semantic collision (e.g. "Create a product where domain X solves a core bottleneck in domain Y").
   - Explicitly instruct the model to return a structured JSON output matching the schema:
     - `name`: Capitalized name.
     - `problem_statement`: Why the current solution fails.
     - `insight_from_path`: Specific structural connection found in traversal.
     - `solution`: Description of product/service wrapper.
     - `MVP_architecture`: Tech stack, API integrations, and database.
     - `risks`: Primary technical and business failure modes.
4. **LLM Query & Parsing**:
   - Call the LLM API using the compiled prompt.
   - Parse and validate JSON structure.
5. **Output**:
   - Write raw idea to `.tmp/synthesized_idea.json`.

## Edge Cases & Error Handling
- **API Call Failure**: Record details in `.tmp/logs/` and raise error.
- **Malformed JSON output**: If the LLM returns invalid JSON, retry up to 2 times with a repair prompt.
