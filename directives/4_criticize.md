# SOP: The Novelty Critic (Layer 1)

This directive describes the quality control process for validating synthesized startup ideas.

## Objective
Evaluate a generated startup idea JSON for genuine cross-domain synthesis, market gap, and non-obviousness, filtering out ideas that score below an 8/10 on the internal novelty rubric.

## Inputs
- Synthesized idea JSON (from `.tmp/synthesized_idea.json`).

## Deterministic Tool
- Script: `execution/evaluate.py`

## Instructions
1. **Load Idea details**:
   - Parse `.tmp/synthesized_idea.json`.
2. **Compile Critique Prompt**:
   - Formulate a prompt for a secondary LLM call.
   - Evaluate along 3 metrics (each scored 1-10):
     - **Cross-Domain Synthesis**: Does it genuinely combine domains or is it derivative?
     - **Market Gap**: Is this problem already solved by existing platforms?
     - **Feasibility & Architecture**: Can it run under a low infrastructure budget?
3. **Execute Evaluation Call**:
   - Send the idea details and scoring rubric to the LLM.
   - Request JSON response returning scores and a short qualitative explanation for each score.
4. **Filtering Action**:
   - Compute aggregate score (average of the three metrics).
   - If average score >= 8.0:
     - Save as a winning idea in `.tmp/winning_ideas/` with timestamp.
     - Log success.
   - If average score < 8.0:
     - Log failure.
     - Save the pattern/idea details as a "failed pattern" in PostgreSQL `cognee_metadata` to refine subsequent prompt heuristics.

## Edge Cases & Error Handling
- **Invalid Critique JSON**: Log warning and fallback to default pass (8.0 score) if evaluation API is unresponsive, but flag for manual review.
- **Low Yield**: If 3 consecutive ideas are rejected, trigger a notification/log message suggesting prompt heuristic tuning.
