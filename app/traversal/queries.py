"""
Novelty Traversal SQL Queries — Phase 3 Core
=============================================

Design rationale:
-----------------
A naive recursive CTE for graph traversal generates ALL possible paths, which
causes exponential blowup on a dense graph (O(branching^hops) rows).

We use a GREEDY CTE instead: at each hop, a single best neighbour is selected
using DISTINCT ON + ORDER BY. This constrains the recursive step to one row per
path prefix, giving O(max_hops) recursive iterations — stable and predictable.

Novelty Scoring Math (FR-2.3):
- Base score per hop   = edge.semantic_distance  (cosine distance ∈ [0, 2])
- Same-domain penalty  = multiply hop score by DOMAIN_PENALTY (< 1.0)
- Path score           = SUM of weighted hop scores
- Winner               = path with MAX total_distance among all completed walks

The domain penalty enforces FR-2.3 ("domains/node types change across hops")
without hard-filtering — it biases traversal toward cross-domain jumps while
still allowing same-domain if no better neighbours exist.
"""

NOVELTY_WALK_CTE = """
WITH RECURSIVE novelty_walk (
    path_ids,        -- UUID[]  — ordered list of node IDs forming the path
    path_domains,    -- TEXT[]  — ordered list of domains for penalty calc
    current_id,      -- UUID    — current frontier node
    total_distance,  -- FLOAT   — accumulated weighted semantic distance
    hop_count        -- INT     — depth of current path
) AS (

    --------------------------------------------------------------------------
    -- ANCHOR: seed the walk from a single starting node
    --------------------------------------------------------------------------
    SELECT
        ARRAY[n.id]::uuid[]      AS path_ids,
        ARRAY[n.domain]::text[]  AS path_domains,
        n.id                     AS current_id,
        0.0::double precision    AS total_distance,
        0                        AS hop_count
    FROM nodes n
    WHERE n.id = :seed_id

    UNION ALL

    --------------------------------------------------------------------------
    -- RECURSIVE STEP: one greedy hop from the current frontier
    --
    -- DISTINCT ON (w.current_id) combined with ORDER BY score DESC means only
    -- the single highest-scoring unvisited neighbour is selected per iteration.
    -- This is the key that prevents path explosion.
    --------------------------------------------------------------------------
    SELECT DISTINCT ON (w.current_id)
        w.path_ids    || n.id       AS path_ids,
        w.path_domains || n.domain  AS path_domains,
        n.id                        AS current_id,

        -- Novelty score for this hop:
        -- Full score if domain changes (cross-domain jump).
        -- Penalised score (×0.3) if domain repeats from previous node.
        w.total_distance + (
            e.semantic_distance *
            CASE
                WHEN n.domain = w.path_domains[array_length(w.path_domains, 1)]
                THEN :domain_penalty   -- same domain as immediate predecessor
                ELSE 1.0               -- different domain: full credit
            END
        )                           AS total_distance,

        w.hop_count + 1             AS hop_count

    FROM novelty_walk w

    -- Traverse edges in both directions (undirected walk)
    JOIN edges e ON (
        e.source_node_id = w.current_id
        OR e.target_node_id = w.current_id
    )

    -- Resolve the neighbour on the other end of the edge
    JOIN nodes n ON n.id = CASE
        WHEN e.source_node_id = w.current_id THEN e.target_node_id
        ELSE e.source_node_id
    END

    WHERE
        -- Never revisit a node already in this path
        n.id != ALL(w.path_ids)
        -- Enforce max hop depth
        AND w.hop_count < :max_hops

    -- Greedy selection: pick the highest weighted distance neighbour
    ORDER BY
        w.current_id,
        (e.semantic_distance *
            CASE
                WHEN n.domain = w.path_domains[array_length(w.path_domains, 1)]
                THEN :domain_penalty
                ELSE 1.0
            END
        ) DESC
)

--------------------------------------------------------------------------
-- FINAL SELECTION: return only complete paths (reached max_hops) and
-- pick the single highest-scoring one.
--------------------------------------------------------------------------
SELECT
    path_ids,
    path_domains,
    total_distance,
    hop_count
FROM novelty_walk
WHERE hop_count = :max_hops
ORDER BY total_distance DESC
LIMIT 1;
"""


# After NOVELTY_WALK_CTE returns path_ids, we hydrate the full node objects.
HYDRATE_PATH_NODES = """
SELECT
    id,
    title,
    domain,
    node_type,
    summary,
    created_at
FROM nodes
WHERE id = ANY(:path_ids)
ORDER BY array_position(:path_ids, id);
"""


# Picks a random seed node — prefers nodes with at least one outgoing edge.
RANDOM_SEED_QUERY = """
SELECT n.id
FROM nodes n
WHERE EXISTS (
    SELECT 1 FROM edges e
    WHERE e.source_node_id = n.id
       OR e.target_node_id = n.id
)
ORDER BY RANDOM()
LIMIT 1;
"""
