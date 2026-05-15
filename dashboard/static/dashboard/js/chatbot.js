/* global document, sessionStorage, fetch, requestAnimationFrame */
(() => {
    "use strict";

    // -------------------------------------------------------------------------
    // Bootstrap config
    // -------------------------------------------------------------------------
    const configEl = document.getElementById("unistudio-chatbot-config");
    if (!configEl) return;

    let config = {};
    try { config = JSON.parse(configEl.textContent || "{}"); } catch (_) { return; }
    if (!config.enabled) return;

    // -------------------------------------------------------------------------
    // DOM refs — bail early if anything is missing
    // -------------------------------------------------------------------------
    const fab          = document.getElementById("usc-toggle");
    const topbarBtn    = document.getElementById("usc-topbar-toggle");
    const panel        = document.getElementById("usc-panel");
    const closeBtn     = document.getElementById("usc-close");
    const clearBtn     = document.getElementById("usc-clear");
    const form         = document.getElementById("usc-form");
    const input        = document.getElementById("usc-input");
    const messagesEl   = document.getElementById("usc-messages");
    const suggestEl    = document.getElementById("usc-suggestions");
    const statusEl     = document.getElementById("usc-status");

    if (!fab || !panel || !form || !input || !messagesEl || !suggestEl) return;

    // -------------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------------
    const STORAGE_KEY = "usc-history-v2";
    let history       = _loadHistory();
    let isOpen        = false;
    let isWaiting     = false;
    let _statusTimer  = null;

    // Status messages cycled client-side while waiting for the server.
    // Works under WSGI (where SSE events all arrive at once) and upgrades
    // automatically to real server events when running under ASGI/uvicorn.
    const TYPING_STEPS = [
        "Analysing your question\u2026",
        "Querying the database\u2026",
        "Looking up relevant data\u2026",
        "Preparing your answer\u2026",
    ];

    const SOURCE_LABELS = {
        google: "Google Gemini",
        openai: "OpenAI",
        rules : "Guidance",
        cache : "Cached",
    };

    // -------------------------------------------------------------------------
    // Utilities
    // -------------------------------------------------------------------------
    function _loadHistory() {
        try { return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "[]"); }
        catch (_) { return []; }
    }

    function _saveHistory() {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(-20)));
    }

    function _csrfToken() {
        const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : "";
    }

    function _currentFilters() {
        return {
            year   : document.getElementById("filter-year")?.value    || "",
            period : document.getElementById("filter-period")?.value   || "",
            faculty: document.getElementById("filter-faculty")?.value  || "",
        };
    }

    function _setStatus(text) {
        if (statusEl) statusEl.textContent = text;
    }

    // Auto-grow textarea — collapses to one line, expands up to ~6 lines.
    // Sets overflow-y only when capped so no scrollbar flashes mid-growth.
    const MAX_INPUT_H = 144; // px — ~6 lines at 0.87rem/1.5 line-height
    function _autoGrow() {
        input.style.height = "0";          // shrink first so scrollHeight is accurate
        const natural = input.scrollHeight;
        const capped  = Math.min(natural, MAX_INPUT_H);
        input.style.height = capped + "px";
        input.style.overflowY = natural > MAX_INPUT_H ? "auto" : "hidden";
    }

    // -------------------------------------------------------------------------
    // Rendering
    // -------------------------------------------------------------------------
    function _renderEmpty() {
        messagesEl.innerHTML = `
            <div class="usc-empty">
                <div class="usc-empty-icon">
                    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
                              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </div>
                <p class="usc-empty-title">How can I help?</p>
                <p class="usc-empty-sub">Ask about students, programmes, pass rates, or academic rules.</p>
            </div>
        `.trim();
    }

    function _createTypingBubble() {
        const wrap = document.createElement("div");
        wrap.className = "usc-msg usc-msg--assistant";
        wrap.id = "usc-typing";

        const bubble = document.createElement("div");
        bubble.className = "usc-msg-bubble usc-typing";
        bubble.innerHTML = `
            <span class="usc-typing-dots">
                <span class="usc-typing-dot"></span>
                <span class="usc-typing-dot"></span>
                <span class="usc-typing-dot"></span>
            </span>
            <span class="usc-typing-status" aria-live="polite"></span>
        `.trim();

        wrap.appendChild(bubble);
        return wrap;
    }

    function _updateTypingStatus(step) {
        const typingEl = document.getElementById("usc-typing");
        if (!typingEl) return;
        const statusSpan = typingEl.querySelector(".usc-typing-status");
        if (statusSpan) statusSpan.textContent = step;
    }

    // Start cycling through TYPING_STEPS immediately so the user always sees
    // what's happening — even when the server delivers all SSE events at once.
    function _startStatusCycle() {
        let i = 0;
        _updateTypingStatus(TYPING_STEPS[0]);
        _statusTimer = setInterval(() => {
            i = (i + 1) % TYPING_STEPS.length;
            _updateTypingStatus(TYPING_STEPS[i]);
        }, 1800);
    }

    // Stop the cycle (called when a real server event or final reply arrives).
    function _stopStatusCycle() {
        if (_statusTimer !== null) {
            clearInterval(_statusTimer);
            _statusTimer = null;
        }
    }

    function _appendTyping() {
        const existing = document.getElementById("usc-typing");
        if (existing) existing.remove();
        messagesEl.appendChild(_createTypingBubble());
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function _removeTyping() {
        document.getElementById("usc-typing")?.remove();
    }

    function _renderMessage(entry) {
        const wrap = document.createElement("div");
        wrap.className = `usc-msg usc-msg--${entry.role}`;

        const bubble = document.createElement("div");
        bubble.className = "usc-msg-bubble";
        bubble.textContent = entry.content;
        wrap.appendChild(bubble);

        if (entry.role === "assistant" && entry.source === "cache") {
            const meta = document.createElement("div");
            meta.className = "usc-msg-meta";

            const badge = document.createElement("span");
            badge.className = "usc-msg-meta-badge";
            badge.textContent = "Cached";
            meta.appendChild(badge);
            wrap.appendChild(meta);
        }

        return wrap;
    }

    function _renderAll() {
        messagesEl.innerHTML = "";

        if (!history.length) {
            _renderEmpty();
            return;
        }

        history.forEach((entry) => {
            if (!entry.pending) {
                messagesEl.appendChild(_renderMessage(entry));
            }
        });

        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function _renderSuggestions() {
        suggestEl.innerHTML = "";
        // Hide chips once the user has had a conversation
        if (history.length > 0) return;

        (config.suggestions || []).forEach((prompt) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "usc-chip";
            btn.textContent = prompt;
            btn.addEventListener("click", () => {
                input.value = prompt;
                _autoGrow();
                input.focus();
                suggestEl.innerHTML = "";
            });
            suggestEl.appendChild(btn);
        });
    }

    // -------------------------------------------------------------------------
    // Panel open / close
    // -------------------------------------------------------------------------
    function _syncTriggers(expanded) {
        const label = expanded ? "Close UniStudio assistant" : "Open UniStudio assistant";
        fab.setAttribute("aria-expanded", String(expanded));
        fab.setAttribute("aria-label", label);
        if (topbarBtn) {
            topbarBtn.setAttribute("aria-expanded", String(expanded));
            topbarBtn.setAttribute("aria-label", label);
        }
    }

    function _open() {
        panel.hidden = false;           // semantic
        panel.style.display = "flex";   // explicit — beats any CSS specificity issue
        isOpen = true;
        _syncTriggers(true);
        _renderAll();
        _renderSuggestions();
        requestAnimationFrame(() => input.focus());
    }

    function _close() {
        panel.hidden = true;            // semantic
        panel.style.display = "none";   // explicit
        isOpen = false;
        _syncTriggers(false);
    }

    // -------------------------------------------------------------------------
    // Send message
    // -------------------------------------------------------------------------
    async function _send(message) {
        if (isWaiting || !message) return;
        isWaiting = true;

        // Optimistic UI
        history.push({ role: "user", content: message });
        _saveHistory();
        _renderAll();
        _appendTyping();
        _startStatusCycle();
        suggestEl.innerHTML = "";

        input.value = "";
        input.style.height = "2.5rem";
        input.style.overflowY = "hidden";
        input.disabled = true;
        const sendBtn = form.querySelector(".usc-send");
        if (sendBtn) sendBtn.disabled = true;
        _setStatus("Thinking\u2026");

        // Prefer the streaming SSE endpoint; fall back to the plain JSON one
        const useStream = !!(config.stream_endpoint && typeof ReadableStream !== "undefined");
        let replied = false;

        try {
            const res = await fetch(useStream ? config.stream_endpoint : config.endpoint, {
                method : "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken" : _csrfToken(),
                },
                credentials: "same-origin",
                body: JSON.stringify({
                    message,
                    filters : _currentFilters(),
                    page_key: config.page_key,
                }),
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.error || "The assistant could not respond.");
            }

            if (useStream) {
                // ---- SSE streaming path ------------------------------------
                const reader  = res.body.getReader();
                const decoder = new TextDecoder();
                let buffer    = "";

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    // Split on blank lines (SSE record separator)
                    const lines = buffer.split("\n");
                    buffer = lines.pop(); // keep the incomplete trailing chunk

                    for (const line of lines) {
                        if (!line.startsWith("data: ")) continue;
                        let event;
                        try { event = JSON.parse(line.slice(6)); } catch (_) { continue; }

                        if (event.type === "status") {
                            _stopStatusCycle();   // hand off to real server step
                            _updateTypingStatus(event.step);
                        } else if (event.type === "reply") {
                            replied = true;
                            const reply = event.reply || "I could not produce a response for that request.";
                            history.push({ role: "assistant", content: reply, source: event.source || "rules" });
                            _setStatus(SOURCE_LABELS[event.source] || "Guidance");
                        } else if (event.type === "error") {
                            throw new Error(event.error || "The assistant could not respond.");
                        }
                    }
                }

                if (!replied) throw new Error("No reply received from the assistant.");

            } else {
                // ---- Plain JSON fallback -----------------------------------
                const payload = await res.json();
                const reply = payload.reply || "I could not produce a response for that request.";
                history.push({ role: "assistant", content: reply, source: payload.source || "rules" });
                _setStatus(SOURCE_LABELS[payload.source] || "Guidance");
            }

        } catch (err) {
            history.push({ role: "assistant", content: err.message || "Something went wrong. Please try again.", source: "rules" });
            _setStatus("Offline");
        } finally {
            _stopStatusCycle();
            _saveHistory();
            _removeTyping();
            _renderAll();
            isWaiting = false;
            input.disabled = false;
            if (sendBtn) sendBtn.disabled = false;
            input.focus();
        }
    }

    // -------------------------------------------------------------------------
    // Event wiring
    // -------------------------------------------------------------------------
    fab.addEventListener("click", () => (isOpen ? _close() : _open()));
    topbarBtn?.addEventListener("click", () => (isOpen ? _close() : _open()));
    closeBtn?.addEventListener("click", _close);

    clearBtn?.addEventListener("click", () => {
        history = [];
        _saveHistory();
        _renderAll();
        _renderSuggestions();
        _setStatus(config.ai_available ? "Online" : "Guidance mode");
    });

    form.addEventListener("submit", (e) => {
        e.preventDefault();
        const message = input.value.trim();
        if (message) _send(message);
    });

    // Enter to send, Shift+Enter for newline
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            const message = input.value.trim();
            if (message) _send(message);
        }
    });

    // Auto-grow as the user types
    input.addEventListener("input", _autoGrow);

    // Close panel on Escape
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && isOpen) _close();
    });
})();
