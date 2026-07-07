const API_BASE = 'http://127.0.0.1:8000/api';

// DOM Elements
const promptInput = document.getElementById('prompt-input');
const btnSubmit = document.getElementById('btn-submit');
const chatContainer = document.getElementById('chat-container');
const welcomeScreen = document.getElementById('welcome-screen');
const mainScroll = document.getElementById('main-scroll');
const apiKeyInput = document.getElementById('gemini-api-key');
const modeSelect = document.getElementById('verification-mode');

// Templates
const tplUserMsg = document.getElementById('tpl-user-msg');
const tplAiMsg = document.getElementById('tpl-ai-msg');
const tplLoading = document.getElementById('tpl-loading');

// --- Auto-expand Textarea ---
promptInput.addEventListener('input', () => {
    promptInput.style.height = 'auto';
    promptInput.style.height = Math.min(promptInput.scrollHeight, 200) + 'px';
});

// --- Event Listeners ---
promptInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
    }
});
btnSubmit.addEventListener('click', handleSubmit);

const btnNewChat = document.getElementById('btn-new-chat');
if (btnNewChat) {
    btnNewChat.addEventListener('click', () => {
        // Clear all messages except welcome screen
        const messages = chatContainer.querySelectorAll('.message');
        messages.forEach(msg => msg.remove());
        if (welcomeScreen) welcomeScreen.style.display = 'block';
    });
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        mainScroll.scrollTop = mainScroll.scrollHeight;
    });
}

// --- Main Chat Logic ---
async function handleSubmit() {
    const text = promptInput.value.trim();
    if (!text) return;

    if (welcomeScreen) welcomeScreen.style.display = 'none';

    promptInput.value = '';
    promptInput.style.height = 'auto';
    promptInput.disabled = true;
    btnSubmit.disabled = true;

    appendUserMessage(text);
    const loadingNode = appendLoadingIndicator();
    scrollToBottom();

    try {
        await handleUnifiedRequest(text, loadingNode);
    } catch (error) {
        console.error(error);
        loadingNode.remove();
        appendAiMessage(`<span style="color:var(--red-verdict)">Error: ${error.message}</span>`);
    } finally {
        promptInput.disabled = false;
        btnSubmit.disabled = false;
        promptInput.focus();
        scrollToBottom();
    }
}

function appendUserMessage(text) {
    const clone = tplUserMsg.content.cloneNode(true);
    clone.querySelector('.user-text').textContent = text;
    chatContainer.appendChild(clone);
}

function appendLoadingIndicator() {
    const clone = tplLoading.content.cloneNode(true);
    const node = clone.firstElementChild;
    chatContainer.appendChild(node);
    return node;
}

function appendAiMessage(htmlContent) {
    const clone = tplAiMsg.content.cloneNode(true);
    clone.querySelector('.ai-text').innerHTML = htmlContent;
    chatContainer.appendChild(clone);
}

function badgeClass(verdict) {
    if (['PASS', 'TRUSTWORTHY', 'SUPPORTED'].includes(verdict)) return 'success';
    if (['FAIL', 'UNTRUSTWORTHY', 'CONTRADICTED', 'UNSAFE'].includes(verdict)) return 'danger';
    if (['NEUTRAL', 'NOT_ENOUGH_INFO'].includes(verdict)) return 'warning';
    return 'info';
}

// --- Unified API Handler ---
async function handleUnifiedRequest(text, loadingNode) {
    const payload = {
        answer: text,
        mode: modeSelect.value,
        input_type: "ask",
        skip_generation: false,
        gemini_api_key: apiKeyInput.value.trim() || ""
    };

    const response = await fetch(`${API_BASE}/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        const errText = await response.text();
        throw new Error(`Server error ${response.status}: ${errText.substring(0, 200)}`);
    }

    const data = await response.json();
    loadingNode.remove();

    const chunks = data.chunks || [];
    let fullMarkdownText = "";

    if (chunks.length === 0) {
        fullMarkdownText = data.generated_answer || data.original_prompt || text;
    } else {
        if (data.generated_answer && data.generated_answer !== data.original_prompt) {
            fullMarkdownText += data.generated_answer + "\n\n";
        }
        // If there are chunks, we still just render them as cards but we can append them after typing.
        // For now, let's just combine the text to type out, or if there are structural cards, we'll just show them.
    }

    // Create the message container first
    const clone = tplAiMsg.content.cloneNode(true);
    const contentDiv = clone.querySelector('.ai-text');
    chatContainer.appendChild(clone);

    if (fullMarkdownText) {
        // Typewriter effect for text
        await typeOutMarkdown(fullMarkdownText, contentDiv);
    }

    // If there are structural chunks (like Code Sandbox Results), append them instantly at the end
    if (chunks.length > 0) {
        let chunksHtml = '';
        chunks.forEach(chunk => {
            if (chunk.type === 'prose') chunksHtml += renderProseChunk(chunk);
            else if (chunk.type === 'code') chunksHtml += renderCodeChunk(chunk);
        });
        if (chunksHtml) {
            const wrapper = document.createElement('div');
            wrapper.innerHTML = chunksHtml;
            contentDiv.appendChild(wrapper);
            scrollToBottom();
        }
    }
}

async function typeOutMarkdown(text, containerElement) {
    let currentText = "";
    // Speed up typing for large texts so it doesn't take forever
    const charsPerTick = Math.max(1, Math.floor(text.length / 100)); 
    
    for (let i = 0; i < text.length; i += charsPerTick) {
        currentText += text.substring(i, i + charsPerTick);
        const html = typeof marked !== 'undefined' ? marked.parse(currentText) : currentText.replace(/\n/g, '<br>');
        containerElement.innerHTML = `<div class="markdown-body">${html}</div>`;
        scrollToBottom();
        await new Promise(r => setTimeout(r, 15));
    }
    // Ensure final text is fully rendered
    const finalHtml = typeof marked !== 'undefined' ? marked.parse(text) : text.replace(/\n/g, '<br>');
    containerElement.innerHTML = `<div class="markdown-body">${finalHtml}</div>`;
    scrollToBottom();
}

function renderProseChunk(chunk) {
    const bc = badgeClass(chunk.verdict);
    let h = `
        <div class="assessment-panel">
            <div class="assessment-header">
                <div class="score-display">Fact Assessment <span class="badge ${bc}">${chunk.verdict}</span></div>
            </div>
            <p style="margin-bottom:10px"><strong>Claim:</strong> "${esc(chunk.content)}"</p>
            <p style="color:var(--text-secondary);line-height:1.6;margin-bottom:14px">${esc(chunk.explanation || '')}</p>
    `;

    if (chunk.evidence) {
        const evList = Array.isArray(chunk.evidence) ? chunk.evidence : [chunk.evidence];
        h += `<h4>Live Web Sources</h4><div class="evidence-list">`;
        evList.forEach(ev => {
            const txt = ev.text || ev.exact_quote || 'Source snippet unavailable';
            const src = ev.source || ev.source_link || '#';
            h += `
                <div class="evidence-card">
                    <div class="evidence-text">"${esc(txt)}"</div>
                    <a href="${src}" target="_blank" rel="noopener" class="evidence-link">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                        View Source
                    </a>
                </div>`;
        });
        h += `</div>`;
    }
    h += `</div>`;
    return h;
}

function renderCodeChunk(chunk) {
    const sa = chunk.static_analysis || {};
    const v = chunk.verdict || 'UNKNOWN';
    const issues = (sa.lint_errors || 0) + (sa.security_issues || 0);
    return `
        <div class="assessment-panel" style="border-color:rgba(139,92,246,0.3)">
            <div class="assessment-header">
                <div class="score-display">Code Analysis <span class="badge ${badgeClass(v)}">${v}</span></div>
            </div>
            <div class="metrics-row">
                <div class="metric-box">
                    <div class="metric-label">Time Complexity</div>
                    <div class="metric-value" style="color:var(--accent);font-family:monospace">${sa.time_complexity_big_o || 'O(1)'}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Complexity</div>
                    <div class="metric-value">${sa.complexity || 'LOW'}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Issues</div>
                    <div class="metric-value" style="color:${issues > 0 ? 'var(--red-verdict)' : 'var(--green-verdict)'}">${issues}</div>
                </div>
            </div>
            <h4>Algorithmic Breakdown</h4>
            <p style="color:var(--text-secondary);white-space:pre-wrap;margin-bottom:20px">${sa.detailed_breakdown || 'Select Gemini mode and provide an API key for deep analysis.'}</p>
            <h4>Optimization Strategy</h4>
            <p style="color:var(--text-secondary);margin-bottom:14px">${sa.complexity_improvement || 'No suggestions.'}</p>
            <h4>Optimized Code</h4>
            <pre><code>${sa.optimized_code ? esc(sa.optimized_code) : '# No optimized code returned.'}</code></pre>
        </div>`;
}

function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}

// --- Load History on Startup ---
async function loadChatHistory() {
    try {
        const response = await fetch(`${API_BASE}/history`);
        if (!response.ok) return;
        const historyData = await response.json();
        
        if (historyData && historyData.length > 0) {
            if (welcomeScreen) welcomeScreen.style.display = 'none';
            
            // Limit to last 10 interactions so it doesn't get crazy long
            const recentHistory = historyData.slice(-10);
            
            recentHistory.forEach(item => {
                if (item.original_prompt) {
                    appendUserMessage(item.original_prompt);
                }
                
                let aiHtml = '';
                if (item.generated_answer && item.generated_answer !== item.original_prompt) {
                    const mdHtml = typeof marked !== 'undefined' ? marked.parse(item.generated_answer) : item.generated_answer.replace(/\n/g, '<br>');
                    aiHtml += `<div class="markdown-body" style="margin-bottom:20px;">${mdHtml}</div>`;
                }
                
                if (item.chunks && item.chunks.length > 0) {
                    let chunksHtml = '';
                    item.chunks.forEach(chunk => {
                        if (chunk.type === 'prose') chunksHtml += renderProseChunk(chunk);
                        else if (chunk.type === 'code') chunksHtml += renderCodeChunk(chunk);
                    });
                    if (chunksHtml) aiHtml += `<div>${chunksHtml}</div>`;
                }
                
                if (aiHtml) {
                    appendAiMessage(aiHtml);
                }
            });
            scrollToBottom();
        }
    } catch (e) {
        console.log("Could not load history", e);
    }
}

// Initialize
document.addEventListener("DOMContentLoaded", loadChatHistory);
