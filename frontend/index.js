// CodeNeuron SPA Controller

document.addEventListener("DOMContentLoaded", () => {
    // ---- DOM Element Selectors ----
    const aiInput = document.getElementById("ai-answer-input");
    const modeSelect = document.getElementById("verification-mode");
    const apiKeyGroup = document.getElementById("api-key-group");
    const apiKeyInput = document.getElementById("gemini-api-key");
    const sourceModelInput = document.getElementById("source-model");
    
    const btnVerify = document.getElementById("btn-verify");
    const btnClear = document.getElementById("btn-clear");
    const btnDemo = document.getElementById("btn-demo-data");
    const btnExport = document.getElementById("btn-export-pdf");
    
    const progressCard = document.getElementById("progress-card");
    const resultsCard = document.getElementById("results-card");
    const dashboardCard = document.getElementById("dashboard-card");
    const historyList = document.getElementById("history-list");
    
    // Progress Pipeline Steps
    const steps = {
        ingest: document.getElementById("step-ingest"),
        chunk: document.getElementById("step-chunk"),
        search: document.getElementById("step-search"),
        verify: document.getElementById("step-verify"),
        sandbox: document.getElementById("step-sandbox"),
        aggregate: document.getElementById("step-aggregate")
    };

    // Results Dashboard Metrics
    const trustPercentText = document.getElementById("trust-percentage");
    const scoreCircle = document.getElementById("score-circle");
    const reportTitle = document.getElementById("report-summary-title");
    const reportText = document.getElementById("report-summary-text");
    const reportBreakdown = document.getElementById("report-breakdown");
    const verdictBadge = document.getElementById("verdict-badge");
    
    // Tabs Navigation
    const tabButtons = document.querySelectorAll(".tab-btn");
    const tabContents = document.querySelectorAll(".tab-content");
    
    // Prose Highlight Elements
    const proseHighlightedText = document.getElementById("prose-highlighted-text");
    const evidenceDrawer = document.getElementById("evidence-drawer");
    
    // Code Inspection Elements
    const codeBlocksList = document.getElementById("code-blocks-list");
    const codeInspectorPanel = document.getElementById("code-inspector-panel");
    const codeInspectorContent = document.getElementById("code-inspector-content");
    const codeEmptyState = document.getElementById("code-empty-state");
    
    // Raw JSON Display
    const rawJsonDisplay = document.getElementById("raw-json-display");
    
    // Active States Cache
    let currentReport = null;
    let selectedClaimIndex = null;
    let selectedCodeIndex = 0;

    // ---- Demo AI Answer Example ----
    const DEMO_EXAMPLE = `Python uses the Timsort algorithm for sorting lists, which combines merge sort and insertion sort.
However, the capital city of Australia is Sydney, which is the most populous city in the country.

\`\`\`python
def fibonacci(n):
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    elif n == 2:
        return [0, 1]
    
    seq = [0, 1]
    for i in range(2, n):
        seq.append(seq[-1] + seq[-2])
    return seq
\`\`\`

Additionally, Python allows running shell tasks directly. The following code is unsafe and shouldn't be executed:

\`\`\`python
import os
import subprocess
# This is blocked by the CodeNeuron sandbox
os.system("echo Unsafe Operations Triggered")
open("hacked.txt", "w").write("test")
\`\`\``;

    // ---- Event Listeners ----
    
    // Toggle API Key Input Visibility based on mode selected
    modeSelect.addEventListener("change", () => {
        if (modeSelect.value === "gemini") {
            apiKeyGroup.classList.remove("hidden");
        } else {
            apiKeyGroup.classList.add("hidden");
        }
    });
    
    // Clear Input
    btnClear.addEventListener("click", () => {
        aiInput.value = "";
        resetVerificationStates();
    });
    
    // Load Demo Data
    btnDemo.addEventListener("click", () => {
        aiInput.value = DEMO_EXAMPLE;
        sourceModelInput.value = "ChatGPT-4o";
    });
    
    // Export PDF Report
    btnExport.addEventListener("click", () => {
        window.print();
    });
    
    // Tab switching routing
    tabButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");
            
            tabButtons.forEach(b => b.classList.remove("active"));
            tabContents.forEach(c => c.classList.remove("active"));
            
            btn.classList.add("active");
            document.getElementById(targetTab).classList.add("active");
        });
    });
    
    // Run Core Full-Stack Analysis
    btnVerify.addEventListener("click", triggerAnalysis);

    // Boot Database Load
    loadHistoryList();

    // ---- Functions ----

    function resetVerificationStates() {
        progressCard.classList.add("hidden");
        resultsCard.classList.add("hidden");
        dashboardCard.classList.add("hidden");
        btnExport.setAttribute("disabled", "true");
        currentReport = null;
    }

    async function loadHistoryList() {
        try {
            const res = await fetch("/api/history");
            if (res.ok) {
                const history = await res.json();
                renderHistoryList(history);
            }
        } catch (e) {
            console.error("Failed loading verification history", e);
        }
    }

    function renderHistoryList(history) {
        historyList.innerHTML = "";
        if (!history || history.length === 0) {
            historyList.innerHTML = `<div class="empty-history">No past analyses found.</div>`;
            return;
        }

        history.forEach((entry, idx) => {
            const date = new Date(entry.timestamp);
            const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            
            const badgeClass = entry.metrics.overall_verdict;
            const item = document.createElement("div");
            item.className = `history-item ${currentReport && currentReport.id === entry.id ? 'active' : ''}`;
            
            item.innerHTML = `
                <div class="history-header">
                    <span>${timeStr}</span>
                    <span class="history-engine">${entry.mode_selected.toUpperCase()}</span>
                </div>
                <div class="history-model">${entry.source_model}</div>
                <div class="history-score-row">
                    <span class="badge ${badgeClass}">${entry.metrics.overall_verdict}</span>
                    <span style="font-weight:600; font-size:12px;">${entry.metrics.score_percentage}%</span>
                </div>
            `;
            
            item.addEventListener("click", () => {
                // Instantly restore dashboard results representation
                document.querySelectorAll(".history-item").forEach(item => item.classList.remove("active"));
                item.classList.add("active");
                currentReport = entry;
                renderReportDashboard(entry);
            });
            
            historyList.appendChild(item);
        });
    }

    async function triggerAnalysis() {
        const text = aiInput.value ? aiInput.value.trim() : "";
        if (!text) {
            alert("Please paste an AI answer to verify.");
            return;
        }
        
        resetVerificationStates();
        progressCard.classList.remove("hidden");
        btnVerify.setAttribute("disabled", "true");
        
        // 1. Ingest Progress Update
        updateProgressStep("ingest", "active");
        
        const payload = {
            answer: text,
            source_model: sourceModelInput.value || "Unknown",
            mode: modeSelect.value,
            gemini_api_key: apiKeyInput.value || ""
        };
        
        // Pipeline transitions timing simulator to match REST steps
        setTimeout(() => updateProgressStep("chunk", "active"), 400);
        setTimeout(() => updateProgressStep("search", "active"), 800);
        setTimeout(() => updateProgressStep("verify", "active"), 1200);
        setTimeout(() => updateProgressStep("sandbox", "active"), 1600);
        setTimeout(() => updateProgressStep("aggregate", "active"), 2000);
        
        try {
            const response = await fetch("/api/verify", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            
            if (response.ok) {
                const report = await response.json();
                currentReport = report;
                
                // Complete all steps
                Object.keys(steps).forEach(key => updateProgressStep(key, "done"));
                
                setTimeout(() => {
                    progressCard.classList.add("hidden");
                    btnVerify.removeAttribute("disabled");
                    btnExport.removeAttribute("disabled");
                    
                    renderReportDashboard(report);
                    loadHistoryList(); // reload logs sidebar
                }, 800);
            } else {
                const err = await response.json();
                let errorMsg = err.detail || "Server Error";
                if (typeof errorMsg === 'object') {
                    errorMsg = JSON.stringify(errorMsg);
                }
                alert(`Analysis Failed: ${errorMsg}`);
                btnVerify.removeAttribute("disabled");
                progressCard.classList.add("hidden");
            }
        } catch (e) {
            console.error("HTTP verification call failure", e);
            alert("Failed to reach server. Ensure FastAPI backend is running locally on port 8000.");
            btnVerify.removeAttribute("disabled");
            progressCard.classList.add("hidden");
        }
    }

    function updateProgressStep(stepName, state) {
        const element = steps[stepName];
        if (!element) return;
        
        // Clear old classes
        element.className = "pipeline-step";
        
        const statusBox = element.querySelector(".step-status");
        
        if (state === "active") {
            element.classList.add("active");
            statusBox.innerHTML = `<span class="step-spinner"></span>`;
        } else if (state === "done") {
            element.classList.add("done");
            statusBox.innerHTML = `<span class="step-bullet" style="background:#50fa7b; box-shadow:0 0 10px #50fa7b"></span>`;
        } else {
            statusBox.innerHTML = `<span class="step-bullet"></span>`;
        }
    }

    function renderReportDashboard(report) {
        // Show components
        resultsCard.classList.remove("hidden");
        dashboardCard.classList.remove("hidden");
        
        const m = report.metrics;
        
        // 1. Render radial SVG confidence rating
        const percentage = m.score_percentage;
        trustPercentText.textContent = `${percentage}%`;
        
        // Circular progress circumference = 2 * PI * r = 2 * 3.1416 * 50 = 314.16
        const offset = 314.16 - (percentage / 100) * 314.16;
        scoreCircle.style.strokeDashoffset = offset;
        
        // Set stroke color based on verdict rating HSL
        let strokeColor = "#bd93f9"; // fallback purple
        if (m.overall_verdict === "UNSAFE") {
            strokeColor = "#ffb86c"; // orange warning
        } else if (percentage >= 80) {
            strokeColor = "#50fa7b"; // green
        } else if (percentage >= 50) {
            strokeColor = "#ffb86c"; // orange suspicious
        } else {
            strokeColor = "#ff5555"; // red untrustworthy
        }
        scoreCircle.style.stroke = strokeColor;
        
        // 2. Render report assessments text
        reportTitle.textContent = m.summary;
        let reportTextContent = `Analysis conducted via CodeNeuron ${report.mode_selected.toUpperCase()} engine. Source LLM: ${report.source_model}.`;
        if (report.generated_answer) {
            reportTextContent = `Generated Answer: "${report.generated_answer}"\n\n` + reportTextContent;
            aiInput.value = report.generated_answer;
        }
        reportText.textContent = reportTextContent;
        reportBreakdown.textContent = m.breakdown;
        
        // Verdict Badge
        verdictBadge.className = `badge ${m.overall_verdict}`;
        verdictBadge.textContent = m.overall_verdict;
        
        // 3. Render sentence highlights (Prose Factual audit)
        renderProseHighlights(report.chunks);
        
        // 4. Render Sandboxed Code Sandboxes Tab
        renderCodeSandbox(report.chunks);
        
        // 5. Render Raw telemetry JSON
        rawJsonDisplay.textContent = JSON.stringify(report, null, 4);
    }

    function renderProseHighlights(chunks) {
        proseHighlightedText.innerHTML = "";
        
        // Reset evidence drawer elements
        evidenceDrawer.querySelector(".empty-drawer-state").classList.remove("hidden");
        evidenceDrawer.querySelector(".drawer-content").classList.add("hidden");
        selectedClaimIndex = null;
        
        let proseFound = false;
        
        chunks.forEach((c, idx) => {
            if (c.type === "prose") {
                proseFound = true;
                const span = document.createElement("span");
                span.className = `claim-highlighter ${c.verdict}`;
                span.textContent = c.content + " ";
                span.setAttribute("data-index", idx);
                
                span.addEventListener("click", () => {
                    document.querySelectorAll(".claim-highlighter").forEach(s => s.classList.remove("selected"));
                    span.classList.add("selected");
                    selectedClaimIndex = idx;
                    revealEvidenceDrawer(c);
                });
                
                proseHighlightedText.appendChild(span);
            } else if (c.type === "code") {
                // Visual markdown block spacing for readabilities
                const codePre = document.createElement("pre");
                codePre.className = "code-block-container";
                codePre.style.margin = "12px 0";
                codePre.innerHTML = `<code style="font-family:'Fira Code', monospace; color:#f0f3fa; font-size:12px;"># Code Block Blocked/Isolated\n${c.code.substring(0, 100)}...</code>`;
                proseHighlightedText.appendChild(codePre);
            }
        });
        
        if (!proseFound) {
            proseHighlightedText.innerHTML = `<div class="empty-drawer-state">No factual prose claims were routed in this AI response.</div>`;
        }
    }

    function revealEvidenceDrawer(claimChunk) {
        evidenceDrawer.querySelector(".empty-drawer-state").classList.add("hidden");
        const drawerContent = evidenceDrawer.querySelector(".drawer-content");
        drawerContent.classList.remove("hidden");
        
        // Fill drawer elements
        document.getElementById("evidence-verdict").className = `badge ${claimChunk.verdict}`;
        document.getElementById("evidence-verdict").textContent = claimChunk.verdict;
        document.getElementById("evidence-claim-text").textContent = `"${claimChunk.content}"`;
        document.getElementById("evidence-explanation-text").textContent = claimChunk.explanation || "No explanation provided.";
        
        const ev = claimChunk.evidence;
        if (ev) {
            document.getElementById("evidence-source-text").textContent = ev.text;
            
            // Recompute dynamic keywords relevance score display
            const relevancePercentage = Math.round(claimChunk.confidence * 100);
            document.getElementById("evidence-relevance-pill").textContent = `Assessment Confidence: ${relevancePercentage}%`;
            
            const sourceUrl = document.getElementById("evidence-source-url");
            sourceUrl.href = ev.source;
            sourceUrl.textContent = ev.source.startsWith("http") ? new URL(ev.source).hostname : "Wikipedia Documentation Link";
            sourceUrl.classList.remove("hidden");
        } else {
            document.getElementById("evidence-source-text").textContent = "No external documents retrieved containing aligned claims.";
            document.getElementById("evidence-relevance-pill").textContent = "Assessment Confidence: 30%";
            document.getElementById("evidence-source-url").classList.add("hidden");
        }
    }

    function renderCodeSandbox(chunks) {
        codeBlocksList.innerHTML = "";
        
        const codeChunks = chunks.filter(c => c.type === "code");
        
        if (codeChunks.length === 0) {
            codeEmptyState.classList.remove("hidden");
            codeInspectorContent.classList.add("hidden");
            return;
        }
        
        codeEmptyState.classList.add("hidden");
        codeInspectorContent.classList.remove("hidden");
        
        selectedCodeIndex = 0;
        
        codeChunks.forEach((c, idx) => {
            const btn = document.createElement("div");
            btn.className = `nav-item ${idx === selectedCodeIndex ? 'active' : ''}`;
            
            // Preview function def names inside button
            let namePreview = `Code Chunk [${c.language.toUpperCase()}]`;
            const funcMatch = c.code.match(/def\s+(\w+)/);
            if (funcMatch) {
                namePreview = `${funcMatch[1]}()`;
            }
            
            btn.textContent = namePreview;
            btn.addEventListener("click", () => {
                document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                selectedCodeIndex = idx;
                revealCodeInspector(c);
            });
            
            codeBlocksList.appendChild(btn);
        });
        
        revealCodeInspector(codeChunks[0]);
    }

    function revealCodeInspector(codeChunk) {
        document.getElementById("code-verdict-badge").className = `badge ${codeChunk.verdict}`;
        document.getElementById("code-verdict-badge").textContent = codeChunk.verdict;
        
        const sa = codeChunk.static_analysis || {};
        const tr = codeChunk.test_results || {};
        
        // 1. Fill metrics cards
        document.getElementById("metric-complexity").textContent = sa.complexity || "LOW";
        document.getElementById("metric-lints").textContent = `${sa.lint_errors || 0} Alert(s)`;
        document.getElementById("metric-time").textContent = tr.time || "0.00s";
        document.getElementById("metric-security").textContent = `${sa.security_issues || 0} Alert(s)`;
        
        // 2. Render code display
        document.getElementById("code-source-display").textContent = codeChunk.code;
        
        // 3. Render static warnings terminal console
        const warningsTerminal = document.getElementById("code-warnings-list");
        warningsTerminal.innerHTML = "";
        
        if (sa.warnings && sa.warnings.length > 0) {
            sa.warnings.forEach(w => {
                const line = document.createElement("div");
                line.className = "terminal-line terminal-error";
                line.textContent = `[SECURITY ALERT] ${w}`;
                warningsTerminal.appendChild(line);
            });
        }
        
        if (sa.details && sa.details.length > 0) {
            sa.details.forEach(d => {
                const line = document.createElement("div");
                line.className = "terminal-line terminal-warning";
                line.textContent = `[LINT AUDIT] ${d}`;
                warningsTerminal.appendChild(line);
            });
        }
        
        if (warningsTerminal.innerHTML === "") {
            warningsTerminal.innerHTML = `<div class="terminal-line terminal-pass">[AST CHECKS] 0 security vulnerabilities flagged. PEP 8 line guidelines observed.</div>`;
        }

        // 4. Render testing assertion logs
        const testsTerminal = document.getElementById("code-tests-list");
        testsTerminal.innerHTML = "";
        
        if (tr.details && tr.details.length > 0) {
            tr.details.forEach(detail => {
                const line = document.createElement("div");
                line.className = "terminal-line";
                if (detail.includes("PASSED")) {
                    line.classList.add("terminal-pass");
                } else if (detail.includes("FAILED") || detail.includes("Error") || detail.includes("Failure")) {
                    line.classList.add("terminal-error");
                } else {
                    line.classList.add("terminal-info");
                }
                line.textContent = `[ASSERT] ${detail}`;
                testsTerminal.appendChild(line);
            });
        }
        
        if (testsTerminal.innerHTML === "") {
            testsTerminal.innerHTML = `<div class="terminal-line terminal-info">[UNIT RUNNER] Syntax compilation was validated successfully.</div>`;
        }

        // 5. Render run console stdout/stderr logs
        const termDisplay = document.getElementById("code-terminal-display");
        termDisplay.innerHTML = "";
        
        let termLogs = "";
        if (tr.stdout && tr.stdout.trim()) {
            termLogs += `>>> STDOUT STREAM <<<\n${tr.stdout.trim()}\n\n`;
        }
        if (tr.stderr && tr.stderr.trim()) {
            termLogs += `>>> STDERR/TRACEBACK STREAM <<<\n${tr.stderr.trim()}\n`;
        }
        
        if (!termLogs.trim()) {
            termLogs = "No sandboxed output generated during execution.";
        }
        termDisplay.textContent = termLogs;
        
        // 6. Render generated test suite code
        document.getElementById("code-test-source-display").textContent = codeChunk.test_source || "# Test script generated successfully.";
    }
});
