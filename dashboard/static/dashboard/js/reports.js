/* global document, fetch, URLSearchParams, URL */
/* Reports page — UniStudio v3 */
(() => {
    "use strict";

    // -------------------------------------------------------------------------
    // DOM refs
    // -------------------------------------------------------------------------
    const layout = document.querySelector(".rpt-layout");
    if (!layout) return;

    const generateUrl = layout.dataset.generateUrl;
    const exportUrl   = layout.dataset.exportUrl;
    const periodsUrl  = layout.dataset.periodsUrl;
    const studentUrl  = layout.dataset.studentUrl;   // e.g. /students/

    const generateBtn   = document.getElementById("rpt-generate");
    const exportBtn     = document.getElementById("rpt-export");
    const searchInput   = document.getElementById("rpt-search");
    const yearSelect    = document.getElementById("rpt-year");
    const periodSelect  = document.getElementById("rpt-period");
    const facultySelect = document.getElementById("rpt-faculty");
    const thresholdInput  = document.getElementById("rpt-threshold");
    const thresholdGroup  = document.getElementById("rpt-threshold-group");
    const truncBanner     = document.getElementById("rpt-truncation-banner");
    const truncText       = document.getElementById("rpt-truncation-text");

    const elEmpty   = document.getElementById("rpt-empty");
    const elLoading = document.getElementById("rpt-loading");
    const elError   = document.getElementById("rpt-error");
    const elErrText = document.getElementById("rpt-error-text");
    const elOutput  = document.getElementById("rpt-output");
    const elTitle   = document.getElementById("rpt-output-title");
    const elMeta    = document.getElementById("rpt-output-meta");
    const elSummary = document.getElementById("rpt-summary-cards");
    const elCount   = document.getElementById("rpt-row-count");
    const elThead   = document.getElementById("rpt-thead");
    const elTbody   = document.getElementById("rpt-tbody");

    // -------------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------------
    let _allRows    = [];
    let _columns    = [];
    let _reportType = "enrolment";
    let _sortCol    = -1;
    let _sortAsc    = true;
    let _lastParams = null;

    const REPORT_LABELS = {
        enrolment:   "Enrolment Summary",
        pass_rate:   "Pass Rate Analysis",
        at_risk:     "At-Risk Students",
        programme:   "Programme Performance",
        demographic: "Demographic Breakdown",
    };

    // -------------------------------------------------------------------------
    // Utilities
    // -------------------------------------------------------------------------
    function _show(...els) { els.forEach(el => el.classList.remove("is-hidden")); }
    function _hide(...els) { els.forEach(el => el.classList.add("is-hidden")); }

    function _setState(state) {
        _hide(elEmpty, elLoading, elError, elOutput);
        ({ empty: elEmpty, loading: elLoading, error: elError, output: elOutput }[state])
            ?.classList.remove("is-hidden");
    }

    function _csrf() {
        const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : "";
    }

    function _params() {
        const checked = layout.querySelector(".rpt-type-radio:checked");
        return new URLSearchParams({
            report_type: checked?.value || "enrolment",
            year:        yearSelect?.value    || "",
            period:      periodSelect?.value  || "",
            faculty:     facultySelect?.value || "",
            threshold:   thresholdInput?.value || "50",
        });
    }

    // -------------------------------------------------------------------------
    // Report-type card selection
    // -------------------------------------------------------------------------
    layout.querySelectorAll(".rpt-type-card").forEach(card => {
        const radio = card.querySelector(".rpt-type-radio");
        radio.addEventListener("change", () => {
            layout.querySelectorAll(".rpt-type-card").forEach(c => c.classList.remove("is-selected"));
            if (radio.checked) {
                card.classList.add("is-selected");
                _reportType = radio.value;
                _syncThresholdVisibility();
            }
        });
        if (radio.checked) {
            card.classList.add("is-selected");
            _reportType = radio.value;
        }
    });

    function _syncThresholdVisibility() {
        if (_reportType === "at_risk") {
            _show(thresholdGroup);
        } else {
            _hide(thresholdGroup);
        }
    }
    _syncThresholdVisibility();

    // -------------------------------------------------------------------------
    // Cascading year → period filter
    // -------------------------------------------------------------------------
    yearSelect?.addEventListener("change", async () => {
        const year = yearSelect.value;
        try {
            const res  = await fetch(`${periodsUrl}?year=${encodeURIComponent(year)}`, {
                credentials: "same-origin",
            });
            const json = await res.json();
            const current = periodSelect.value;
            periodSelect.innerHTML = '<option value="">All periods</option>';
            (json.periods || []).forEach(p => {
                const opt = document.createElement("option");
                opt.value = p;
                opt.textContent = p;
                if (p === current) opt.selected = true;
                periodSelect.appendChild(opt);
            });
        } catch (_) { /* leave period list unchanged on network error */ }
    });

    // -------------------------------------------------------------------------
    // Generate
    // -------------------------------------------------------------------------
    async function _generate() {
        const params = _params();
        _setState("loading");
        exportBtn.disabled   = true;
        generateBtn.disabled = true;
        searchInput.value    = "";

        try {
            const res  = await fetch(`${generateUrl}?${params}`, {
                headers: { "X-CSRFToken": _csrf() },
                credentials: "same-origin",
            });
            const json = await res.json();
            if (!res.ok || json.error) throw new Error(json.error || "Failed to generate report.");

            _allRows    = json.rows    || [];
            _columns    = json.columns || [];
            _reportType = json.report_type;
            _sortCol    = -1;
            _sortAsc    = true;
            _lastParams = params;

            _renderOutput(json);
            _setState("output");
            exportBtn.disabled = false;

        } catch (err) {
            elErrText.textContent = err.message || "An error occurred generating the report.";
            _setState("error");
        } finally {
            generateBtn.disabled = false;
        }
    }

    // -------------------------------------------------------------------------
    // Render full output
    // -------------------------------------------------------------------------
    function _renderOutput(json) {
        // Title + meta
        elTitle.textContent = REPORT_LABELS[json.report_type] || json.report_type;
        const parts = [];
        if (_lastParams.get("year"))    parts.push(`Year: ${_lastParams.get("year")}`);
        if (_lastParams.get("period"))  parts.push(`Period: ${_lastParams.get("period")}`);
        if (_lastParams.get("faculty")) parts.push(`Faculty: ${_lastParams.get("faculty")}`);
        if (_reportType === "at_risk")  parts.push(`Threshold: ${_lastParams.get("threshold")}`);
        elMeta.textContent = parts.length ? parts.join(" · ") : "All data — no filters applied";

        // Truncation banner
        if (json.truncated) {
            truncText.textContent =
                `Showing first ${json.max_rows.toLocaleString()} of ${json.total_db_rows.toLocaleString()} rows. ` +
                `Use Export CSV to download the full dataset.`;
            _show(truncBanner);
        } else {
            _hide(truncBanner);
        }

        // Summary cards
        elSummary.innerHTML = "";
        Object.entries(json.summary || {}).forEach(([label, value]) => {
            const card = document.createElement("div");
            card.className = "rpt-summary-card";
            card.innerHTML =
                `<span class="rpt-summary-value">${value}</span>` +
                `<span class="rpt-summary-label">${label}</span>`;
            elSummary.appendChild(card);
        });

        // Table
        _renderTable(_allRows);
    }

    // -------------------------------------------------------------------------
    // Table
    // -------------------------------------------------------------------------
    function _renderTable(rows) {
        // Header
        elThead.innerHTML = "";
        const tr = document.createElement("tr");
        _columns.forEach((col, i) => {
            const th = document.createElement("th");
            th.textContent = col;
            th.setAttribute("scope", "col");
            th.setAttribute("aria-sort", i === _sortCol
                ? (_sortAsc ? "ascending" : "descending")
                : "none");
            if (i === _sortCol) th.classList.add(_sortAsc ? "is-sorted-asc" : "is-sorted-desc");
            th.addEventListener("click", () => _sortBy(i, rows));
            tr.appendChild(th);
        });
        elThead.appendChild(tr);

        // Body
        elTbody.innerHTML = "";
        if (!rows.length) {
            const noRow = elTbody.insertRow();
            noRow.className = "rpt-no-results";
            const td = noRow.insertCell();
            td.colSpan = _columns.length || 1;
            td.textContent = "No results match the current filters.";
            elCount.textContent = "0 rows";
            return;
        }

        const frag = document.createDocumentFragment();
        rows.forEach(row => {
            const rowEl = document.createElement("tr");
            row.forEach((cell, colIdx) => {
                const td = document.createElement("td");

                // At-risk report: first column (Reg Number) → clickable link to student profile
                if (_reportType === "at_risk" && colIdx === 0 && studentUrl) {
                    const a = document.createElement("a");
                    a.href = `${studentUrl}${encodeURIComponent(cell)}/`;
                    a.className = "rpt-student-link";
                    a.textContent = cell ?? "—";
                    a.title = "Open student profile";
                    td.appendChild(a);
                } else {
                    td.textContent = cell ?? "—";
                }
                rowEl.appendChild(td);
            });
            frag.appendChild(rowEl);
        });
        elTbody.appendChild(frag);
        elCount.textContent = `${rows.length.toLocaleString()} row${rows.length === 1 ? "" : "s"}`;
    }

    // -------------------------------------------------------------------------
    // Sort
    // -------------------------------------------------------------------------
    function _sortBy(colIdx, currentRows) {
        _sortAsc = (_sortCol === colIdx) ? !_sortAsc : true;
        _sortCol = colIdx;
        const sorted = [...currentRows].sort((a, b) => {
            const av = a[colIdx], bv = b[colIdx];
            const cmp = (typeof av === "number" && typeof bv === "number")
                ? av - bv
                : String(av ?? "").localeCompare(String(bv ?? ""), undefined, { numeric: true });
            return _sortAsc ? cmp : -cmp;
        });
        _renderTable(sorted);
    }

    // -------------------------------------------------------------------------
    // Search
    // -------------------------------------------------------------------------
    function _filtered() {
        const q = searchInput.value.trim().toLowerCase();
        return q
            ? _allRows.filter(row => row.some(c => String(c ?? "").toLowerCase().includes(q)))
            : _allRows;
    }

    searchInput.addEventListener("input", () => {
        _sortCol = -1;
        _sortAsc = true;
        _renderTable(_filtered());
    });

    // -------------------------------------------------------------------------
    // CSV export
    // -------------------------------------------------------------------------
    exportBtn.addEventListener("click", () => {
        if (!_lastParams) return;
        const a = document.createElement("a");
        a.href = `${exportUrl}?${_lastParams}`;
        a.download = "";
        document.body.appendChild(a);
        a.click();
        a.remove();
    });

    // -------------------------------------------------------------------------
    // Wire up
    // -------------------------------------------------------------------------
    generateBtn.addEventListener("click", _generate);
    layout.querySelectorAll(".rpt-filter-select, #rpt-threshold").forEach(el => {
        el.addEventListener("keydown", e => { if (e.key === "Enter") _generate(); });
    });

    _setState("empty");
})();
