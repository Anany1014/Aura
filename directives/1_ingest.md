# SOP: Ingestion Pipeline (Layer 1)

This directive defines the process for chunking, embedding, and inserting unstructured data (papers, patents, codebases, startup concepts) into the Graph.

## Objective
Ingest raw unstructured documents, create node representation in the database, calculate Vector embeddings, and establish initial semantic proximity edges.

## Inputs
- Absolute or relative directory path containing unstructured documents (markdown, text, pdfs, json).
- Node metadata overrides (domain, type, custom tags).

## Deterministic Tool
- Script: `execution/ingest.py`

## Instructions
1. **Extraction / Chunking**:
   - Parse target files. If a file is too large (> 8000 characters), split it into semantically coherent chunks (e.g. paragraphs or sections).
2. **Feature Extraction**:
   - Extract `title`, `domain` (e.g. biotech, logistics, webdev), and `type` (e.g. paper, patent, startup, code).
   - Generate a concise 2-3 sentence `summary` representing the core tech or concept.
3. **Vector Embeddings**:
   - Send the summary (or full content if within limits) to the embedding model (`text-embedding-3-small` or equivalent).
   - Retrieve a 1536-dimensional float vector.
4. **Database Storage**:
   - Upsert the node into the `nodes` table. Avoid duplicates (match by title/content hash if needed).
5. **Edge Generation**:
   - Find existing nodes in the database.
   - For any node mapping to the same keywords or within close cosine distance (e.g., distance < 0.35), create an edge in the `edges` table.
   - Set relationship_type (e.g., `references`, `implements`, `competes_with`) and save the calculated `semantic_distance` (cosine distance).

## Edge Cases & Error Handling
- **API Failures**: If OpenAI / LLM service is down, persist intermediate chunks in `.tmp/ingest_queue.json` and retry on the next schedule.
- **Large Files**: Gracefully fail or log truncation warning if files cannot be parsed.
