document.addEventListener("DOMContentLoaded", () => {

    // ── DOM References ──────────────────────────────────────────────────────
    const systemBadge = document.getElementById("system-badge");
    const modeText = document.getElementById("mode-text");

    // Upload panel
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const selectedFileLabel = document.getElementById("selected-file-name");
    const textIdea = document.getElementById("text-idea");
    const inputTitle = document.getElementById("input-title");
    const selectDomain = document.getElementById("select-domain");
    const selectType = document.getElementById("select-type");
    const btnUpload = document.getElementById("btn-upload");
    const uploadAlert = document.getElementById("upload-alert");
    const nodeCount = document.getElementById("node-count");
    const nodeList = document.getElementById("node-list");
    const selectSeed = document.getElementById("select-seed");

    // Discovery
    const rangeHops = document.getElementById("range-hops");
    const labelHops = document.getElementById("label-hops");
    const rangePenalty = document.getElementById("range-penalty");
    const labelPenalty = document.getElementById("label-penalty");
    const btnDiscover = document.getElementById("btn-discover");

    // Cognee
    const cogneeUsed = document.getElementById("cognee-used");
    const cogneeHeadroom = document.getElementById("cognee-headroom");
    const cogneeLimit = document.getElementById("cognee-limit");
    const cogneeRecords = document.getElementById("cognee-records");
    const cogneeProgress = document.getElementById("cognee-progress");

    // Output panels
    const discoveryStatusPanel = document.getElementById("discovery-status-panel");
    const ideaPanel = document.getElementById("idea-panel");
    const emptySynthesisState = document.getElementById("empty-synthesis-state");

    // Idea display
    const ideaVerdict = document.getElementById("idea-verdict");
    const ideaTitle = document.getElementById("idea-title");
    const ideaScore = document.getElementById("idea-score");
    const ideaDbId = document.getElementById("idea-db-id");
    const ideaProblem = document.getElementById("idea-problem");
    const ideaSolution = document.getElementById("idea-solution");
    const ideaInsight = document.getElementById("idea-insight");
    const ideaArchitecture = document.getElementById("idea-architecture");
    const ideaRisks = document.getElementById("idea-risks");
    const criticCrossDomain = document.getElementById("critic-cross-domain");
    const criticMarketGap = document.getElementById("critic-market-gap");
    const criticFeasibility = document.getElementById("critic-feasibility");
    const criticExplanation = document.getElementById("critic-explanation");
    const traversalPath = document.getElementById("traversal-path");

    // ── State ───────────────────────────────────────────────────────────────
    let ingestedNodes = [];
    let selectedFile = null;

    // ── Slider sync ─────────────────────────────────────────────────────────
    rangeHops.addEventListener("input", e => { labelHops.textContent = e.target.value; });
    rangePenalty.addEventListener("input", e => { labelPenalty.textContent = e.target.value; });

    // ── Alert helper ────────────────────────────────────────────────────────
    function showAlert(element, message, type = "info") {
        element.style.display = "block";
        element.className = `alert-message alert-${type}`;
        const icons = { success: "✓", warning: "⚠", error: "✕", info: "ℹ" };
        element.innerHTML = `<span>${icons[type] || "ℹ"}</span> ${message}`;
        setTimeout(() => { element.style.display = "none"; }, 6000);
    }

    // ── Badge helper ────────────────────────────────────────────────────────
    function getBadgeClass(domain) {
        if (!domain) return "badge-general";
        const d = domain.toLowerCase();
        if (d.includes("civic")) return "badge-civic";
        if (d.includes("gaming") || d.includes("game")) return "badge-gaming";
        if (d.includes("sustain")) return "badge-sustainable";
        if (d.includes("biotech") || d.includes("health")) return "badge-biotech";
        if (d.includes("fintech") || d.includes("finance")) return "badge-fintech";
        if (d.includes("ai") || d.includes("ml") || d.includes("deep")) return "badge-ai";
        return "badge-general";
    }

    // ── File input helpers ───────────────────────────────────────────────────
    fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) {
            selectedFile = fileInput.files[0];
            selectedFileLabel.textContent = `📎 ${selectedFile.name}`;
        }
    });

    // Drag-and-drop
    dropZone.addEventListener("dragover", e => {
        e.preventDefault();
        dropZone.classList.add("drag-over");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("drag-over");
    });

    dropZone.addEventListener("drop", e => {
        e.preventDefault();
        dropZone.classList.remove("drag-over");
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            selectedFile = files[0];
            selectedFileLabel.textContent = `📎 ${selectedFile.name}`;
        }
    });

    // Auto-fill title from filename if title is empty
    function autoFillTitle() {
        if (selectedFile && inputTitle.value.trim() === "") {
            const guessed = selectedFile.name
                .replace(/\.[^.]+$/, "")          // strip extension
                .replace(/[-_]+/g, " ")            // dashes/underscores → spaces
                .replace(/\b\w/g, c => c.toUpperCase()); // title-case
            inputTitle.value = guessed;
        }
    }
    fileInput.addEventListener("change", autoFillTitle);
    dropZone.addEventListener("drop", () => setTimeout(autoFillTitle, 50));

    // ── Render nodes list ───────────────────────────────────────────────────
    function renderNodes(nodes) {
        ingestedNodes = nodes;
        nodeCount.textContent = nodes.length;

        if (nodes.length === 0) {
            nodeList.innerHTML = `<div class="empty-state" style="padding: 1.5rem 0.5rem; font-size: 0.85rem;">No nodes indexed yet.</div>`;
            selectSeed.innerHTML = `<option value="">-- Random Walk (Auto Seed) --</option>`;
            return;
        }

        // Update seed dropdown
        selectSeed.innerHTML = `<option value="">-- Random Walk (Auto Seed) --</option>` +
            nodes.map(n => `<option value="${n.id}">${n.title} (${n.domain})</option>`).join("");

        // Render node cards
        nodeList.innerHTML = nodes.map(n => `
            <div class="node-item" data-id="${n.id}">
                <div class="node-title-box">
                    <span class="node-name">${n.title}</span>
                    <span class="node-source">⬆ ${n.source || "text input"}</span>
                </div>
                <span class="badge ${getBadgeClass(n.domain)}">${n.domain}</span>
            </div>
        `).join("");

        // Click to set seed
        document.querySelectorAll(".node-item").forEach(item => {
            item.addEventListener("click", () => {
                document.querySelectorAll(".node-item").forEach(i => i.classList.remove("selected"));
                item.classList.add("selected");
                selectSeed.value = item.getAttribute("data-id");
            });
        });
    }

    function addNode(node) {
        const existing = ingestedNodes.find(n => n.id === node.id);
        if (!existing) ingestedNodes.push(node);
        renderNodes(ingestedNodes);
        // Auto-select the newest node as seed
        document.querySelectorAll(".node-item").forEach(item => {
            if (item.getAttribute("data-id") === node.id) {
                item.click();
            }
        });
    }

    // ── Cognee status ───────────────────────────────────────────────────────
    async function fetchCogneeStatus() {
        try {
            const res = await fetch("/api/memory/status");
            if (!res.ok) throw new Error("Status endpoint failed");
            const data = await res.json();

            if (cogneeUsed) cogneeUsed.textContent = `${data.usage_mb.toFixed(3)} MB`;
            if (cogneeHeadroom) cogneeHeadroom.textContent = `${data.headroom_mb.toFixed(3)} MB`;
            if (cogneeLimit) cogneeLimit.textContent = data.limit_mb;
            if (cogneeRecords) cogneeRecords.textContent = data.record_count;

            if (cogneeProgress) {
                const pct = Math.min((data.usage_mb / data.limit_mb) * 100, 100);
                cogneeProgress.style.width = `${pct}%`;
            }

            if (data.record_count > 0) {
                systemBadge.className = "system-mode-badge";
                modeText.textContent = "Idea Generator";
            } else {
                systemBadge.className = "system-mode-badge simulation";
                modeText.textContent = "Simulation Mode (Local Store)";
            }
        } catch (e) {
            console.error("Failed to load Cognee status", e);
            systemBadge.className = "system-mode-badge simulation";
            modeText.textContent = "Local Fallback Mode";
        }
    }

    // ── Upload & Index Button ───────────────────────────────────────────────
    btnUpload.addEventListener("click", async () => {
        const title = inputTitle.value.trim();
        const domain = selectDomain.value;
        const type = selectType.value;
        const text = textIdea.value.trim();

        if (!title) {
            showAlert(uploadAlert, "Please enter a title for the concept.", "warning");
            return;
        }
        if (!selectedFile && !text) {
            showAlert(uploadAlert, "Please upload a file or describe your idea in the text box.", "warning");
            return;
        }

        btnUpload.disabled = true;
        btnUpload.innerHTML = `<span class="spinning">🔮</span> Indexing into Memory...`;

        try {
            const formData = new FormData();
            formData.append("title", title);
            formData.append("domain", domain);
            formData.append("node_type", type);

            if (selectedFile) {
                formData.append("file", selectedFile);
            } else {
                formData.append("text_content", text);
            }

            const res = await fetch("/api/ingest/file", {
                method: "POST",
                body: formData
                // Do NOT set Content-Type — browser sets multipart boundary automatically
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || "Ingestion request failed");
            }

            const data = await res.json();
            showAlert(uploadAlert, data.message, "success");

            // Add new node to the list + auto-select as seed
            addNode(data.node);

            // Reset inputs
            inputTitle.value = "";
            textIdea.value = "";
            selectedFile = null;
            fileInput.value = "";
            selectedFileLabel.textContent = "";

            await fetchCogneeStatus();

        } catch (e) {
            showAlert(uploadAlert, `Ingestion error: ${e.message}`, "warning");
        } finally {
            btnUpload.disabled = false;
            btnUpload.innerHTML = `<span>🧠</span> Index into Aura Memory`;
        }
    });

    // ── Discovery Run ───────────────────────────────────────────────────────
    btnDiscover.addEventListener("click", async () => {
        emptySynthesisState.style.display = "none";
        ideaPanel.style.display = "none";
        discoveryStatusPanel.style.display = "block";
        btnDiscover.disabled = true;
        btnDiscover.innerHTML = `<span class="spinning">🔮</span> Discovering...`;

        const seedId = selectSeed.value || null;
        const maxHops = parseInt(rangeHops.value);
        const domainPenalty = parseFloat(rangePenalty.value);

        try {
            const res = await fetch("/api/discover", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ seed_id: seedId, max_hops: maxHops, domain_penalty: domainPenalty })
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || "Discovery walk failed");
            }

            const data = await res.json();

            // Populate idea panel
            ideaVerdict.className = `idea-verdict-tag verdict-${data.verdict.toLowerCase()}`;
            ideaVerdict.textContent = data.verdict;
            ideaTitle.textContent = data.idea.name || "Untitled Lateral Concept";
            ideaScore.textContent = data.score.toFixed(2);
            if (ideaDbId) ideaDbId.textContent = data.database_idea_id || "Simulation (Not Saved)";

            ideaProblem.textContent = data.idea.problem_statement || "—";
            ideaSolution.textContent = data.idea.solution || "—";
            ideaInsight.textContent = data.idea.insight_from_path || "—";
            ideaArchitecture.textContent = data.idea.MVP_architecture || data.idea.mvp_architecture || "—";
            ideaRisks.textContent = data.idea.risks || "—";

            criticCrossDomain.textContent = data.evaluation.cross_domain_synthesis || "—";
            criticMarketGap.textContent = data.evaluation.market_gap || "—";
            criticFeasibility.textContent = data.evaluation.low_budget_feasibility || "—";
            criticExplanation.textContent = data.evaluation.explanation || "No explanation provided by critic.";

            renderPathTimeline(data.traversed_path);

            await fetchCogneeStatus();

            discoveryStatusPanel.style.display = "none";
            ideaPanel.style.display = "block";

        } catch (e) {
            discoveryStatusPanel.style.display = "none";
            emptySynthesisState.style.display = "block";
            showAlert(uploadAlert, `Discovery Walk failed: ${e.message}`, "warning");
        } finally {
            btnDiscover.disabled = false;
            btnDiscover.innerHTML = `<span>⚡</span> Run Discovery Walk`;
        }
    });

    // ── Traversal Timeline ───────────────────────────────────────────────────
    function renderPathTimeline(walk) {
        if (!walk || !walk.path || walk.path.length === 0) {
            traversalPath.innerHTML = `<div class="empty-state" style="padding: 1rem 0;">No traversal path generated.</div>`;
            return;
        }

        const hopColors = ["hop-purple", "hop-cyan", "hop-pink", "hop-green"];

        traversalPath.innerHTML = walk.path.map((node, idx) => {
            const colorClass = hopColors[idx % hopColors.length];
            const edgeInfo = (idx > 0 && walk.edges && walk.edges[idx - 1]) ? walk.edges[idx - 1] : null;

            const edgeHtml = edgeInfo ? `
                <div style="font-size: 0.72rem; color: var(--accent-cyan); margin: 0.5rem 0; padding: 0.25rem 0.5rem; background: rgba(6,182,212,0.05); border-inline-start: 2px solid var(--accent-cyan); display: inline-block; border-radius: 2px;">
                    🔗 Edge: <strong>${edgeInfo.relationship_type}</strong> (dist: <strong>${edgeInfo.semantic_distance.toFixed(3)}</strong>)
                </div>` : "";

            return `
                <div class="path-step ${colorClass}">
                    <div class="path-node-icon">${idx + 1}</div>
                    <div class="path-content-box">
                        <div class="path-node-title">${node.title}</div>
                        <div class="path-node-info">
                            <span>Type: <strong style="color: white; text-transform: uppercase;">${node.node_type}</strong></span>
                            <span>Domain: <strong>${node.domain}</strong></span>
                        </div>
                        ${edgeHtml}
                        <div class="path-node-summary">${node.summary}</div>
                    </div>
                </div>`;
        }).join("");
    }

    // ── Init ─────────────────────────────────────────────────────────────────
    fetchCogneeStatus();
});
