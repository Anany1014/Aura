# SOP: Traversal Engine (Layer 1)

This directive describes how to traverse the PostgreSQL graph using adjacency links to locate semantically distant but structurally linked topics.

## Objective
Execute a constrained random walk of 3 to 4 hops in the graph database (`nodes` and `edges` tables) starting from a specific seed node, maximizing the cumulative semantic distance across the path while ensuring domain variation.

## Inputs
- `seed_node_id` (UUID, optional). If not provided, a random seed is selected.
- `max_hops` (Integer, default: 3 or 4).
- `domain_diversity` (Boolean, default: True). Forces the walk to cross domains at each hop.

## Deterministic Tool
- Script: `execution/traverse.py`

## Instructions
1. **Locate Seed**:
   - Select the starting node. If `seed_node_id` is missing, run a query to select a random high-degree node.
2. **Execute Hops**:
   - For `current_node`, query all adjacent edges.
   - Filter candidates to exclude previously visited nodes in the current path.
   - If `domain_diversity` is enabled, filter for candidate nodes that have a different `domain` from `current_node`.
   - Calculate candidate score: Choose candidates which have a high `semantic_distance` (meaning they are semantically unrelated or lateral concepts) but still have a valid structural edge in the `edges` table.
   - Choose the next node based on a weighted probability emphasizing higher distance.
3. **Track Path**:
   - Accumulate node attributes: `(id, title, domain, type, summary)`.
   - Build path representation: `Node A -> Edge 1 -> Node B -> Edge 2 -> Node C ...`
4. **Output Generation**:
   - Save path information into `.tmp/latest_traversal.json` for subsequent synthesis.

## Edge Cases & Error Handling
- **Dead Ends**: If a node has no outgoing edges, backtrack to the previous node and select a different branch.
- **Disconnected Graphs**: If the graph is small or disconnected, fallback to selecting a secondary seed node via semantic search using cosine distance on node embeddings.
