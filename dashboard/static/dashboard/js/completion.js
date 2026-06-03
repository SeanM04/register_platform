import {
    buildAnimationConfig,
    buildGradient,
    buildTooltipBase,
    buildTooltipMarkup,
    buildVerticalCategoryZoom,
    escapeTooltipHtml,
    formatChartLabel,
    getEchartsLib,
    setChartFallback,
} from "./insights/shared.js";
import {
    closeDrillDownModal,
    showCompletionDrillDownModal,
    showLoadingDrillDownModal,
} from "./completion/drilldown_modal.js?v=20260601-drilldown-numeric-align01";

class CompletionAnalysis {
    constructor() {
        this.root = document.querySelector(".completion-layout");
        this.metricsUrl = this.root?.dataset.metricsUrl || "/metrics/completion/";
        this.payloadUrl = this.root?.dataset.payloadUrl || "/metrics/completion/payload/";
        this.narrativesUrl = this.root?.dataset.narrativesUrl || "/metrics/completion/narratives/";
        this.currentData = null;
        this.currentNarratives = {};
        this.narrativeDiagnostics = {};
        this.currentPage = 1;
        this.itemsPerPage = 10;
        this.chartInstances = {};
        this.currentFilters = this.getFiltersFromURL();

        this.init();
    }

    async openDrillDown(chartKey, bucketKey, page = 1) {
        try {
            console.log("DEBUG: openDrillDown called with:", { chartKey, bucketKey, page });
            
            // Show instant loading indicator
            this.showDrilldownLoading();
            
            // Build drilldown request URL
            const drilldownUrl = new URL("/metrics/completion/drilldown/", window.location.origin);
            
            // Add current filters
            const currentUrl = new URL(window.location.href);
            currentUrl.searchParams.forEach((value, key) => {
                if (key === 'year' || key === 'period' || key === 'faculty') {
                    drilldownUrl.searchParams.set(key, value);
                }
            });
            
            // Add drilldown parameters
            drilldownUrl.searchParams.set('chart_key', chartKey);
            drilldownUrl.searchParams.set('bucket_key', bucketKey);
            drilldownUrl.searchParams.set('page', page);
            
            console.log("DEBUG: drilldownUrl:", drilldownUrl.toString());
            
            // Fetch drilldown data
            const response = await fetch(drilldownUrl.toString());
            if (!response.ok) {
                throw new Error(`Drilldown request failed: ${response.status}`);
            }
            
            const result = await response.json();
            console.log("DEBUG: drilldown response:", result);
            
            if (result.status === 'success' && result.data) {
                this.hideDrilldownLoading();
                showCompletionDrillDownModal(result.data, (page) => {
                    this.openDrillDown(chartKey, bucketKey, page);
                });
            } else {
                throw new Error(result.message || 'No drilldown data available');
            }
            
        } catch (error) {
            this.hideDrilldownLoading();
            console.error("Error opening drilldown:", error);
            // Show error modal or notification
            alert(`Error loading drilldown data: ${error.message}`);
        }
    }

    getFiltersFromURL() {
        const params = new URLSearchParams(window.location.search);
        return {
            year: params.get("year") || "",
            period: params.get("period") || "",
            faculty: params.get("faculty") || "",
        };
    }

    async loadFastMetrics() {
        if (!this.metricsUrl) {
            return;
        }
        try {
            const result = await this.fetchJson(this.metricsUrl);
            const kpis = result?.kpis || {};
            if (typeof kpis.total_students === "number") {
                this.updateMetricValue("total_students", kpis.total_students);
            }
            if (typeof kpis.total_cohorts === "number") {
                this.updateMetricValue("total_cohorts", kpis.total_cohorts);
            }
            this.updateMetricNotes(result?.summary_cards || []);
        } catch (_) {
            // payload will fill in the metrics
        }
    }

    async init() {
        this.bindEvents();
        await this.loadFastMetrics();
        await this.loadData();
        this.renderStoryBanner();
        this.renderFallbackNarratives();
        this.loadNarratives();
        this.syncFullscreenButtons();
    }

    buildRequestUrl(endpoint) {
        const requestUrl = new URL(endpoint, window.location.origin);
        const currentUrl = new URL(window.location.href);

        currentUrl.searchParams.forEach((value, key) => {
            requestUrl.searchParams.set(key, value);
        });

        return requestUrl;
    }

    async fetchJson(endpoint) {
        if (!endpoint) {
            return null;
        }

        const response = await fetch(this.buildRequestUrl(endpoint), {
            credentials: "same-origin",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
        });
        if (!response.ok) {
            throw new Error(`Request failed with status ${response.status}`);
        }
        return response.json();
    }

    bindEvents() {
        const searchInput = document.getElementById("student-search");
        if (searchInput) {
            searchInput.addEventListener("input", () => {
                this.currentPage = 1;
                this.updateStudentsTable();
            });
        }

        const exportButton = document.getElementById("export-students");
        if (exportButton) {
            exportButton.addEventListener("click", () => this.exportStudentsData());
        }

        const errorModalClose = document.getElementById("error-modal-close");
        if (errorModalClose) {
            errorModalClose.addEventListener("click", () => this.hideErrorModal());
        }

        const errorModal = document.getElementById("error-modal");
        if (errorModal) {
            errorModal.addEventListener("click", (event) => {
                if (event.target === errorModal) {
                    this.hideErrorModal();
                }
            });
        }

        document.querySelectorAll("[data-chart-fullscreen-toggle]").forEach((button) => {
            button.addEventListener("click", (event) => {
                this.toggleChartFullscreen(event.currentTarget);
            });
        });

        document.querySelectorAll(".demographic-accordion-toggle").forEach((button) => {
            button.addEventListener("click", () => {
                window.setTimeout(() => this.resizeCharts(), 260);
            });
        });

        window.addEventListener("resize", () => this.resizeCharts());
        document.addEventListener("fullscreenchange", () => {
            this.syncFullscreenButtons();
            this.resizeCharts();
        });
        document.addEventListener("webkitfullscreenchange", () => {
            this.syncFullscreenButtons();
            this.resizeCharts();
        });
    }

    async loadData() {
        try {
            const payload = await this.fetchJson(this.payloadUrl);
            if (payload.status !== "success") {
                throw new Error(payload.message || "Failed to load completion analytics");
            }

            this.currentData = payload.data;
            this.updateMetrics();
            this.updateCharts();
            this.updateStudentsTable();
        } catch (error) {
            this.showError(`Failed to load completion data: ${error.message}`);
        }
    }

    updateMetrics() {
        const kpis = this.currentData?.kpis || {};
        this.updateMetricValue("total_students", kpis.total_students || 0);
        this.updateMetricValue("total_cohorts", kpis.total_cohorts || 0);
        this.updateMetricValue("average_completion_rate", kpis.average_completion_rate || 0, true);
        this.updateMetricValue("zero_completion_students", kpis.zero_completion_students || 0);
        this.updateMetricValue("shifted_students", kpis.shifted_students || 0);
        this.updateMetricNotes(this.currentData?.summary_cards || []);
    }

    updateMetricValue(key, value, isRate = false) {
        const element = document.querySelector(`[data-metric-value][data-metric-key="${key}"]`);
        if (!element) {
            return;
        }

        element.textContent = isRate ? `${Math.round(value)}%` : `${value}`;
    }

    updateMetricNotes(summaryCards = []) {
        if (!summaryCards.length) {
            return;
        }

        summaryCards.forEach((card) => {
            const note = document.querySelector(`.completion-metric-note[data-metric-key="${card.key}"]`);
            if (note) {
                note.textContent = card.note || "";
            }
        });
    }

    updateCharts() {
        const charts = this.currentData?.charts || {};
        this.renderCohortHeatmap(charts.cohort_completion || []);
        this.renderProgrammeChart(charts.programme_completion || []);
        this.renderZeroDriverChart(charts.zero_completion_drivers || []);
    }

    getHeatmapCellColor(completionRate) {
        if (completionRate === null || completionRate === undefined) {
            return "#f1f5f9";
        }
        const numericRate = Number(completionRate);
        if (Number.isNaN(numericRate)) {
            return "#f1f5f9";
        }
        if (numericRate < 50) {
            return "#dc2626";
        }
        if (numericRate < 75) {
            return "#f59e0b";
        }
        return "#16a34a";
    }

    renderStoryBanner() {
        const banner = document.getElementById("completion-story-banner");
        const data = this.currentData;
        if (!banner || !data) {
            return;
        }

        const kpis = data.kpis || {};
        const strongestProgramme = (data.charts?.programme_completion || [])[0] || null;
        const dominantDriver = (data.charts?.zero_completion_drivers || [])[0] || null;
        const averageCompletion = Number(kpis.average_completion_rate || 0);
        const zeroStudents = Number(kpis.zero_completion_students || 0);
        const shiftedStudents = Number(kpis.shifted_students || 0);
        const totalStudents = Math.max(Number(kpis.total_students || 0), 1);
        const zeroShare = Math.round((zeroStudents / totalStudents) * 100);
        const shiftedShare = Math.round((shiftedStudents / totalStudents) * 100);

        let title = "Completion pressure is visible in the current academic scope.";
        if (averageCompletion >= 75 && zeroShare < 15) {
            title = "Completion remains broadly strong, with only limited zero-progress pressure in the visible scope.";
        } else if (averageCompletion < 60 || zeroShare >= 25) {
            title = "Completion pressure is concentrated in zero-progress cases and shifted cohorts across the visible scope.";
        }

        const copyParts = [
            `${Math.round(averageCompletion)}% average completion across ${Number(kpis.total_students || 0)} visible students`,
            `${zeroStudents} students currently sit at 0% completion`,
            `${shiftedStudents} students have moved into later effective cohorts`,
        ];
        if (dominantDriver?.label) {
            copyParts.push(`${dominantDriver.label} is the largest visible zero-completion driver at ${dominantDriver.count} records`);
        }

        banner.innerHTML = `
            <div>
                <p class="completion-banner-title">${escapeTooltipHtml(title)}</p>
                <p class="completion-banner-description">${escapeTooltipHtml(`${copyParts.join(", ")}.`)}</p>
            </div>
            <div class="completion-banner-grid">
                <article class="completion-banner-card">
                    <p class="completion-banner-card-kicker">Completion Baseline</p>
                    <p class="completion-banner-card-value">${escapeTooltipHtml(`${Math.round(averageCompletion)}% avg`)}</p>
                    <p class="completion-banner-card-copy">${escapeTooltipHtml(`${zeroShare}% of visible students are currently in zero-completion positions.`)}</p>
                </article>
                <article class="completion-banner-card">
                    <p class="completion-banner-card-kicker">Shift Pressure</p>
                    <p class="completion-banner-card-value">${escapeTooltipHtml(`${shiftedShare}% shifted`)}</p>
                    <p class="completion-banner-card-copy">${escapeTooltipHtml(`${shiftedStudents} students are now being compared against later effective cohorts.`)}</p>
                </article>
                <article class="completion-banner-card">
                    <p class="completion-banner-card-kicker">${escapeTooltipHtml(dominantDriver?.label || "Top Programme")}</p>
                    <p class="completion-banner-card-value">${escapeTooltipHtml(
                        dominantDriver?.label
                            ? `${dominantDriver.count} records`
                            : `${Math.round(strongestProgramme?.completion_rate || 0)}%`,
                    )}</p>
                    <p class="completion-banner-card-copy">${escapeTooltipHtml(
                        dominantDriver?.label
                            ? `${dominantDriver.label} is the strongest visible zero-completion signal in this scope.`
                            : `${strongestProgramme?.programme_name || "No programme"} leads visible programme completion.`,
                    )}</p>
                </article>
            </div>
        `.trim();
    }

    normalizeCardSeverity(value) {
        const normalized = String(value || "stable").trim().toLowerCase();
        return ["stable", "medium", "high"].includes(normalized) ? normalized : "stable";
    }

    normalizeCardConfidence(value) {
        const normalized = String(value || "medium").trim().toLowerCase();
        return ["low", "medium", "high"].includes(normalized) ? normalized : "medium";
    }

    getSeverityLabel(severity) {
        if (severity === "high") {
            return "Priority";
        }
        if (severity === "medium") {
            return "Watch";
        }
        return "Monitor";
    }

    getConfidenceLabel(confidence) {
        if (confidence === "high") {
            return "High confidence";
        }
        if (confidence === "low") {
            return "Low confidence";
        }
        return "Medium confidence";
    }

    buildAiBadgeMarkup(source, severity = "stable", confidence = "medium") {
        const normalizedSource = String(source || "").trim().toLowerCase();
        const providerLabel = normalizedSource === "google"
            ? "AI-generated with Google Gemini"
            : normalizedSource === "openai"
                ? "AI-generated with OpenAI"
                : "AI-generated";
        const normalizedSeverity = this.normalizeCardSeverity(severity);
        const normalizedConfidence = this.normalizeCardConfidence(confidence);
        const attentionLabel = normalizedSeverity === "high"
            ? "needs attention"
            : normalizedSeverity === "medium"
                ? "watch item"
                : "monitoring";
        const confidenceLabel = this.getConfidenceLabel(normalizedConfidence).toLowerCase();

        return `
            <span class="completion-ai-badge-group">
                <span class="completion-ai-badge is-${normalizedSeverity}" title="${escapeTooltipHtml(`${providerLabel}; ${attentionLabel}; ${confidenceLabel}`)}" aria-label="${escapeTooltipHtml(`${providerLabel}; ${attentionLabel}; ${confidenceLabel}`)}">
                    <span class="completion-ai-badge-icon" aria-hidden="true">
                        <svg viewBox="0 0 20 20" focusable="false">
                            <path d="M7.2 4.1a3.6 3.6 0 0 0-3.6 3.6c0 .8.3 1.6.8 2.2-.3.4-.4.9-.4 1.4 0 1.3.9 2.5 2.2 2.8v.6c0 .8.6 1.4 1.4 1.4h1.1V9.3H7.6a.8.8 0 0 1 0-1.6h1.1V5.1c-.4-.6-.9-1-1.5-1Zm5.6 0c-.6 0-1.1.4-1.5 1v2.6h1.1a.8.8 0 1 1 0 1.6h-1.1v6.8h1.1c.8 0 1.4-.6 1.4-1.4v-.6a2.9 2.9 0 0 0 2.2-2.8c0-.5-.1-1-.4-1.4.5-.6.8-1.4.8-2.2a3.6 3.6 0 0 0-3.6-3.6Z"></path>
                            <path d="M10 6.2h2.1v1.4H10Zm-2.1 4.1H10v1.4H7.9Zm2.1 4.1h2.1v1.4H10Zm4.2-5.1h2.1v1.4h-2.1Z"></path>
                        </svg>
                    </span>
                    AI
                </span>
                <span class="completion-ai-context" aria-label="${escapeTooltipHtml(`${this.getSeverityLabel(normalizedSeverity)}. ${this.getConfidenceLabel(normalizedConfidence)}.`)}">
                    ${escapeTooltipHtml(`${this.getSeverityLabel(normalizedSeverity)} | ${this.getConfidenceLabel(normalizedConfidence)}`)}
                </span>
            </span>
        `.trim();
    }

    buildGuidanceBadgeMarkup(severity = "stable", confidence = "medium") {
        const normalizedSeverity = this.normalizeCardSeverity(severity);
        const normalizedConfidence = this.normalizeCardConfidence(confidence);

        return `
            <span class="completion-ai-badge-group">
                <span class="completion-ai-badge is-guidance is-${normalizedSeverity}" aria-label="${escapeTooltipHtml(`Rule-based guidance; ${this.getSeverityLabel(normalizedSeverity).toLowerCase()}; ${this.getConfidenceLabel(normalizedConfidence).toLowerCase()}`)}">
                    Guidance
                </span>
                <span class="completion-ai-context" aria-label="${escapeTooltipHtml(`${this.getSeverityLabel(normalizedSeverity)}. ${this.getConfidenceLabel(normalizedConfidence)}.`)}">
                    ${escapeTooltipHtml(`${this.getSeverityLabel(normalizedSeverity)} | ${this.getConfidenceLabel(normalizedConfidence)}`)}
                </span>
            </span>
        `.trim();
    }

    setActionText(element, text, options = {}) {
        if (!element) {
            return;
        }

        const hasText = Boolean(String(text || "").trim());
        const showAiBadge = Boolean(options.showAiBadge) && hasText;
        const showGuidanceBadge = Boolean(options.showGuidanceBadge) && hasText;
        element.innerHTML = `
            ${showAiBadge
                ? this.buildAiBadgeMarkup(options.source, options.severity, options.confidence)
                : showGuidanceBadge
                    ? this.buildGuidanceBadgeMarkup(options.severity, options.confidence)
                    : ""}
            <span class="completion-action-text">${escapeTooltipHtml(text)}</span>
        `.trim();
    }

    getFallbackNarratives() {
        const charts = this.currentData?.charts || {};
        const kpis = this.currentData?.kpis || {};
        const cohortRows = charts.cohort_completion || [];
        const programmeRows = charts.programme_completion || [];
        const driverRows = charts.zero_completion_drivers || [];

        const weakestCohort = [...cohortRows].sort((left, right) => left.completion_rate - right.completion_rate)[0] || null;
        const strongestProgramme = programmeRows[0] || null;
        const weakestProgramme = [...programmeRows].slice(-1)[0] || null;
        const dominantDriver = driverRows[0] || null;
        const averageCompletion = Math.round(Number(kpis.average_completion_rate || 0));
        const totalStudents = Math.max(Number(kpis.total_students || 0), 1);
        const zeroShare = Math.round((Number(kpis.zero_completion_students || 0) / totalStudents) * 100);

        return {
            cohort: {
                insight: weakestCohort
                    ? `${weakestCohort.effective_cohort_label} at ${weakestCohort.progression_label} is the clearest cohort pressure point at ${Math.round(weakestCohort.completion_rate)}% completion.`
                    : "No cohort completion narrative is available for the current filters.",
                action: weakestCohort
                    ? "Use the heatmap to isolate cohorts where zero-completion counts are clustering before moving into programme-level detail."
                    : "Adjust the current filters to bring the cohort completion story back into view.",
                severity: averageCompletion < 60 ? "high" : averageCompletion < 75 ? "medium" : "stable",
                confidence: "low",
            },
            programme: {
                insight: strongestProgramme && weakestProgramme
                    ? `${this.formatProgrammeAxisLabel(strongestProgramme.programme_name)} leads at ${Math.round(strongestProgramme.completion_rate)}%, while ${this.formatProgrammeAxisLabel(weakestProgramme.programme_name)} sits lowest at ${Math.round(weakestProgramme.completion_rate)}%.`
                    : "No programme completion narrative is available for the current filters.",
                action: weakestProgramme
                    ? "Use the programme ranking first to compare the lowest-completion programmes and the ones already carrying visible zero-completion share."
                    : "Adjust the current filters to bring the programme completion story back into view.",
                severity: weakestProgramme && weakestProgramme.completion_rate < 60 ? "high" : weakestProgramme && weakestProgramme.completion_rate < 75 ? "medium" : "stable",
                confidence: "low",
            },
            drivers: {
                insight: dominantDriver
                    ? `${dominantDriver.label} is currently the largest visible zero-completion driver with ${dominantDriver.count} records, while ${zeroShare}% of visible students sit at 0% completion.`
                    : "No zero-completion driver narrative is available for the current filters.",
                action: dominantDriver
                    ? "Use the driver chart to separate admin or decision-driven zero progress from true failed-course pressure before opening the student list."
                    : "Adjust the current filters to bring zero-completion drivers back into view.",
                severity: zeroShare >= 25 ? "high" : zeroShare >= 12 ? "medium" : "stable",
                confidence: "low",
            },
        };
    }

    renderFallbackNarratives() {
        const fallback = this.getFallbackNarratives();
        this.applyNarrativeCard("cohort", fallback.cohort, { narrativeSource: "rules", narrativesAreAi: false });
        this.applyNarrativeCard("programme", fallback.programme, { narrativeSource: "rules", narrativesAreAi: false });
        this.applyNarrativeCard("drivers", fallback.drivers, { narrativeSource: "rules", narrativesAreAi: false });
    }

    applyNarrativeCard(cardKey, narrative, flags = {}) {
        const copyElement = document.getElementById(`completion-${cardKey}-copy`);
        const hintElement = document.getElementById(`completion-${cardKey}-hints`);
        const noteElement = document.getElementById(`completion-${cardKey}-note`);
        if (copyElement) {
            copyElement.textContent = narrative?.insight || "";
        }
        if (hintElement) {
            hintElement.innerHTML = "";
        }
        const normalizedSource = String(flags.narrativeSource || "").trim().toLowerCase();
        const showAiBadge = Boolean(flags.narrativesAreAi) && ["openai", "google"].includes(normalizedSource);
        this.setActionText(noteElement, narrative?.action || "", {
            showAiBadge,
            showGuidanceBadge: !showAiBadge,
            source: normalizedSource,
            severity: narrative?.severity,
            confidence: narrative?.confidence,
        });
    }

    loadNarratives() {
        if (!this.narrativesUrl) {
            return;
        }

        this.fetchJson(this.narrativesUrl)
            .then((payload) => {
                this.currentNarratives = payload?.card_narratives || {};
                const diagnostics = payload?.diagnostics || {};

                const flags = {
                    narrativeSource: diagnostics.returned_source || this.currentNarratives.source || "rules",
                    narrativesAreAi: diagnostics.status === "ai",
                };
                const fallback = this.getFallbackNarratives();
                const cards = this.currentNarratives.cards || {};

                this.applyNarrativeCard("cohort", { ...fallback.cohort, ...(cards.cohort || {}) }, flags);
                this.applyNarrativeCard("programme", { ...fallback.programme, ...(cards.programme || {}) }, flags);
                this.applyNarrativeCard("drivers", { ...fallback.drivers, ...(cards.drivers || {}) }, flags);
            })
            .catch(() => {});
    }

    getOrCreateChart(elementId) {
        const element = document.getElementById(elementId);
        if (!element) {
            return null;
        }

        const echartsLib = getEchartsLib();
        if (!echartsLib) {
            setChartFallback(element, "ECharts could not load. The completion table is still available.");
            return null;
        }

        if (!this.chartInstances[elementId]) {
            element.classList.remove("is-empty");
            element.textContent = "";
            this.chartInstances[elementId] = echartsLib.init(element, null, {
                renderer: "canvas",
                useDirtyRect: true,
            });
        }

        return this.chartInstances[elementId];
    }

    renderCohortHeatmap(rows) {
        const element = document.getElementById("cohort-completion-chart");
        if (!element) {
            return;
        }

        if (!rows.length) {
            setChartFallback(element, "No cohort completion data is available for the current filters.");
            return;
        }

        const chart = this.getOrCreateChart("cohort-completion-chart");
        if (!chart) {
            return;
        }

        element.classList.remove("is-empty");
        const sortedRows = [...rows].sort((left, right) => {
            if (left.effective_cohort_sort_index !== right.effective_cohort_sort_index) {
                return left.effective_cohort_sort_index - right.effective_cohort_sort_index;
            }
            return (left.progression_period || 0) - (right.progression_period || 0);
        });

        const progressionLabels = [...new Set(sortedRows.map((row) => row.progression_label))];
        const cohortLabels = [...new Set(sortedRows.map((row) => row.effective_cohort_label))];
        const heatmapData = sortedRows.map((row) => ({
            name: row.effective_cohort_label,
            value: [
                progressionLabels.indexOf(row.progression_label),
                cohortLabels.indexOf(row.effective_cohort_label),
                row.completion_rate,  // Keep null for blank cells
            ],
            itemStyle: {
                color: this.getHeatmapCellColor(row.completion_rate),
            },
            studentCount: row.student_count,
            zeroCompletionCount: row.zero_completion_count,
            passShareRate: row.pass_share_rate,
            progressionLabel: row.progression_label,
            completionRate: row.completion_rate,
        }));

        chart.setOption({
            ...buildAnimationConfig(sortedRows),
            grid: {
                left: 132,
                right: 32,
                top: 24,
                bottom: 52,
            },
            tooltip: {
                ...buildTooltipBase("item"),
                formatter: (params) => {
                    // Handle null completion rate (blank cells)
                    const completionRate = params.data.completionRate;
                    const completionText = completionRate === null ? "No data" : `${Math.round(completionRate)}%`;
                    
                    return buildTooltipMarkup(
                        `${params.data.name} · ${params.data.progressionLabel}`,
                        [
                            { label: "Average completion", value: completionText },
                            { label: "Visible records", value: `${params.data.studentCount}` },
                            { label: "Zero completion", value: `${params.data.zeroCompletionCount}` },
                            { label: "Non-zero share", value: params.data.studentCount > 0 ? `${Math.round(params.data.passShareRate)}%` : "N/A" },
                        ]
                    );
                },
            },
            xAxis: {
                type: "category",
                data: progressionLabels,
                splitArea: { show: true },
                axisLabel: {
                    color: "#334155",
                    fontSize: 11,
                    fontWeight: 700,
                },
                axisLine: {
                    lineStyle: { color: "#cbd5e1" },
                },
            },
            yAxis: {
                type: "category",
                data: cohortLabels,
                splitArea: { show: true },
                axisLabel: {
                    color: "#334155",
                    fontSize: 11,
                    width: 120,
                    overflow: "truncate",
                },
                axisLine: {
                    lineStyle: { color: "#cbd5e1" },
                },
            },
            visualMap: {
                 type: "piecewise",
                orient: "horizontal",
                left: "center",
                bottom: 0,
                text: ["100%", "0%"],
                pieces: [
        { value: null, label: "No data", color: "#f1f5f9" },
        { gte: 0, lt: 50, label: "0% - 49%", color: "#dc2626" },
        { gte: 50, lt: 75, label: "50% - 74%", color: "#f59e0b" },
        { gte: 75, lte: 100, label: "75% - 100%", color: "#16a34a" },
    ],
            },
            series: [
                {
                    type: "heatmap",
                    data: heatmapData,
                    label: {
                        show: true,
                        color: "#ffffff",
                        fontSize: 10,
                        fontWeight: 700,
                        formatter: ({ data }) => (
                            data.completionRate === null || data.completionRate === undefined
                                ? ""
                                : `${Math.round(data.completionRate)}%`
                        ),
                    },
                    emphasis: {
                        itemStyle: {
                            shadowBlur: 18,
                            shadowColor: "rgba(8, 35, 64, 0.24)",
                        },
                    },
                },
            ],
        }, true);

        // Add click handler for drilldown
        chart.off('click').on('click', (params) => {
            console.log("DEBUG: cohort heatmap clicked:", params);
            if (params.data && params.data.name) {
                // For cohort heatmap, use the cohort name as bucketKey
                this.openDrillDown('cohorts', params.data.name);
            }
        });
    }

    renderProgrammeChart(rows) {
        const element = document.getElementById("programme-completion-chart");
        if (!element) {
            return;
        }

        if (!rows.length) {
            setChartFallback(element, "No programme completion data is available for the current filters.");
            return;
        }

        const chart = this.getOrCreateChart("programme-completion-chart");
        if (!chart) {
            return;
        }

        element.classList.remove("is-empty");
        const topRows = [...rows].slice(0, 12).reverse();
        const backgroundTrackColor = "rgba(148, 163, 184, 0.18)";
        const barCornerRadius = 5;

        chart.setOption({
            ...buildAnimationConfig(topRows),
            grid: {
                left: 168,
                right: 28,
                top: 18,
                bottom: 24,
            },
            tooltip: {
                ...buildTooltipBase("item"),
                formatter: (params) => {
                    const row = topRows[params.dataIndex];
                    return buildTooltipMarkup(row.programme_name, [
                        { label: "Average completion", value: `${Math.round(row.completion_rate)}%` },
                        { label: "Students", value: `${row.student_count}` },
                        { label: "Semester records", value: `${row.record_count}` },
                        { label: "Zero-completion share", value: `${Math.round(row.zero_completion_rate)}%` },
                    ]);
                },
            },
            xAxis: {
                type: "value",
                min: 0,
                max: 100,
                axisLabel: {
                    color: "#475569",
                    formatter: (value) => `${Math.round(value)}%`,
                },
                splitLine: {
                    lineStyle: { color: "rgba(148, 163, 184, 0.2)" },
                },
            },
            yAxis: {
                type: "category",
                data: topRows.map((row) => this.formatProgrammeAxisLabel(row.programme_name)),
                axisLabel: {
                    color: "#334155",
                    fontSize: 11,
                    fontWeight: 700,
                    width: 154,
                    overflow: "truncate",
                },
                axisLine: {
                    lineStyle: { color: "#cbd5e1" },
                },
            },
            series: [
                {
                    type: "bar",
                    barWidth: 18,
                    showBackground: true,
                    backgroundStyle: {
                        color: backgroundTrackColor,
                        borderRadius: [0, barCornerRadius, barCornerRadius, 0],
                    },
                    data: topRows.map((row) => ({
                        value: row.completion_rate,
                        raw: { programme: row.programme_name },
                        itemStyle: {
                            borderRadius: [0, barCornerRadius, barCornerRadius, 0],
                            color: buildGradient("#0d4c92", "#67c1e1"),
                        },
                    })),
                    label: {
                        show: true,
                        position: "right",
                        color: "#0f172a",
                        fontWeight: 700,
                        formatter: (params) => `${Math.round(params.value)}%`,
                    },
                },
            ],
        }, true);

        // Add click handler for drilldown
        chart.off('click').on('click', (params) => {
            console.log("DEBUG: programme chart clicked:", params);
            if (params.data && params.data.raw && params.data.raw.programme) {
                // For programme chart, use the programme name as bucketKey
                this.openDrillDown('programme_load', params.data.raw.programme);
            }
        });
    }

    formatProgrammeAxisLabel(programmeName) {
        const abbreviated = String(programmeName || "")
            .replace(/Bachelor of Science/gi, "BSc")
            .replace(/Bachelor of Commerce/gi, "BCom")
            .replace(/Bachelor of Accounting/gi, "BAcc")
            .replace(/Bachelor of Engineering/gi, "BEng")
            .replace(/Bachelor of Arts/gi, "BA")
            .replace(/Bachelor of Laws/gi, "LLB")
            .replace(/Masters of Science/gi, "MSc")
            .replace(/Master of Science/gi, "MSc")
            .replace(/Masters of Commerce/gi, "MCom")
            .replace(/Master of Commerce/gi, "MCom")
            .replace(/Honours Degree/gi, "Hons")
            .replace(/\s+/g, " ")
            .trim();

        return formatChartLabel(abbreviated, 24);
    }

    renderZeroDriverChart(rows) {
        const element = document.getElementById("decision-impact-chart");
        if (!element) {
            return;
        }

        if (!rows.length) {
            setChartFallback(element, "No zero-completion records are visible in the current filters.");
            return;
        }

        const chart = this.getOrCreateChart("decision-impact-chart");
        if (!chart) {
            return;
        }

        element.classList.remove("is-empty");
        const palette = ["#b91c1c", "#dc2626", "#ea580c", "#d97706", "#0f766e", "#0369a1", "#4338ca", "#475569"];
        const sortedRows = [...rows].sort((left, right) => right.count - left.count);
        const barCornerRadius = 5;

        chart.setOption({
            ...buildAnimationConfig(sortedRows),
            color: palette,
            grid: {
                left: 52,
                right: 24,
                top: 20,
                bottom: 96,
            },
            tooltip: {
                ...buildTooltipBase("item"),
                formatter: (params) => buildTooltipMarkup(params.name, [
                    { label: "Visible zero-completion records", value: `${params.value}` },
                ]),
            },
            xAxis: {
                type: "category",
                data: sortedRows.map((row) => formatChartLabel(row.label, 18)),
                axisLabel: {
                    color: "#475569",
                    fontSize: 11,
                    interval: 0,
                    rotate: sortedRows.length > 6 ? 28 : 0,
                },
                axisLine: {
                    lineStyle: { color: "#cbd5e1" },
                },
                axisTick: {
                    show: true,
                    alignWithLabel: true,
                },
            },
            yAxis: {
                type: "value",
                minInterval: 1,
                axisLabel: {
                    color: "#475569",
                    fontSize: 11,
                },
                axisLine: {
                    lineStyle: { color: "#cbd5e1" },
                },
                axisTick: {
                    show: true,
                },
                splitLine: {
                    lineStyle: { color: "rgba(148, 163, 184, 0.2)" },
                },
            },
            dataZoom: sortedRows.length > 8 ? [
                {
                    type: "inside",
                    xAxisIndex: 0,
                    startValue: 0,
                    endValue: 7,
                    filterMode: "weakFilter",
                },
                {
                    type: "slider",
                    xAxisIndex: 0,
                    bottom: 10,
                    height: 14,
                    startValue: 0,
                    endValue: 7,
                    filterMode: "weakFilter",
                    brushSelect: false,
                    moveHandleSize: 0,
                    textStyle: { color: "#4b5563" },
                    borderColor: "#d9e2ec",
                    fillerColor: "rgba(79, 176, 209, 0.18)",
                    dataBackground: {
                        lineStyle: { color: "#9cabbc" },
                        areaStyle: { color: "rgba(156, 171, 188, 0.18)" },
                    },
                },
            ] : [],
            series: [
                {
                    type: "bar",
                    barWidth: 18,
                    data: sortedRows.map((row, index) => ({
                        value: row.count,
                        raw: { key: row.label },
                        itemStyle: {
                            borderRadius: [barCornerRadius, barCornerRadius, 0, 0],
                            color: palette[index % palette.length],
                        },
                    })),
                    label: {
                        show: true,
                        position: "top",
                        color: "#0f172a",
                        fontWeight: 700,
                        formatter: "{c}",
                    },
                },
            ],
        }, true);

        // Add click handler for drilldown
        chart.off('click').on('click', (params) => {
            console.log("DEBUG: zero driver chart clicked:", params);
            console.log("DEBUG: params.data:", params.data);
            console.log("DEBUG: params.data.raw:", params.data?.raw);
            if (params.data && params.data.raw && params.data.raw.key) {
                // For zero driver chart, use the driver key as bucketKey
                console.log("DEBUG: opening drilldown for driver:", params.data.raw.key);
                this.openDrillDown('drivers', params.data.raw.key);
            } else {
                console.log("DEBUG: no raw.key found in click data");
            }
        });
    }

    getFilteredStudents(students) {
        const searchTerm = (document.getElementById("student-search")?.value || "").trim().toLowerCase();
        if (!searchTerm) {
            return students;
        }

        return students.filter((student) => (
            (student.regnum || "").toLowerCase().includes(searchTerm)
            || (student.student_name || "").toLowerCase().includes(searchTerm)
            || (student.programme_name || "").toLowerCase().includes(searchTerm)
            || (student.effective_cohort || "").toLowerCase().includes(searchTerm)
            || (student.zero_completion_reason || "").toLowerCase().includes(searchTerm)
        ));
    }

    updateStudentsTable() {
        const students = this.currentData?.students || [];
        const tbody = document.getElementById("students-tbody");
        if (!tbody) {
            return;
        }

     const filteredStudents = this.getFilteredStudents(students).sort((a, b) => {
    const getLastName = (name) => {
        const parts = (name || "").trim().split(" ");
        return parts[parts.length - 1].toLowerCase();
    };

    return getLastName(a.student_name).localeCompare(getLastName(b.student_name));
});
        const paginatedStudents = this.getPaginatedStudents(filteredStudents);

        if (!paginatedStudents.length) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="completion-empty-state">
                        <div class="completion-empty-state-title">No Students Found</div>
                        <div class="completion-empty-state-description">No completion records match the current filters.</div>
                    </td>
                </tr>
            `;
            this.updatePagination(filteredStudents.length);
            return;
        }

        tbody.innerHTML = "";
        const fragment = document.createDocumentFragment();
        paginatedStudents.forEach((student) => {
            fragment.appendChild(this.createStudentRow(student));
        });
        tbody.appendChild(fragment);
        this.updatePagination(filteredStudents.length);
    }

    createStudentRow(student) {
        const row = document.createElement("tr");
        const decisionClass = this.getDecisionClass(student);
        const rateClass = this.getRateClass(student.completion_rate);
        const cohortClass = student.is_shifted ? "is-shifted" : "is-original";
        

        row.innerHTML = `
            <td class="students-td-name">
                <a class="student-link" href="/students/${student.detail_slug}/" aria-label="View ${escapeTooltipHtml(student.student_name)} profile">
                    ${escapeTooltipHtml(student.student_name || "")}
                </a>
            </td>
            <td>${escapeTooltipHtml(student.programme_name || "")}</td>
            <td>${escapeTooltipHtml((student.academic_stage || "").replace(", ", " "))}</td>
            <td>${escapeTooltipHtml(student.decision || "")}</td>

<td>${escapeTooltipHtml(student.effective_cohort || "")}</td>

<td>
    <span 
        class="completion-rate-value"
        ${student.completion_rate === 0 && student.zero_completion_reason
            ? `title="${escapeTooltipHtml(student.zero_completion_reason)}"`
            : ""
        }
    >
        ${Math.round(student.completion_rate || 0)}%
    </span>
</td>
        `;
        return row;
    }

    getDecisionClass(student) {
        if (student.zero_completion_reason && student.zero_completion_reason !== "Failed 4+ courses" && student.zero_completion_reason !== "No marks recorded") {
            return "low";
        }

        const decision = (student.decision || "").toLowerCase();
        if (decision.includes("proceed")) {
            return "high";
        }
        if (decision.includes("pending")) {
            return "medium";
        }
        return "low";
    }

    getRateClass(rate) {
        if (rate >= 80) {
            return "high";
        }
        if (rate >= 50) {
            return "medium";
        }
        return "low";
    }

    getPaginatedStudents(students) {
        const startIndex = (this.currentPage - 1) * this.itemsPerPage;
        return students.slice(startIndex, startIndex + this.itemsPerPage);
    }

    updatePagination(totalItems) {
        const paginationContainer = document.getElementById("pagination");
        const resultsMeta = document.getElementById("results-meta");
        if (!paginationContainer || !resultsMeta) {
            return;
        }

        const totalPages = Math.max(Math.ceil(totalItems / this.itemsPerPage), 1);
        if (this.currentPage > totalPages) {
            this.currentPage = totalPages;
        }

        const startItem = totalItems ? ((this.currentPage - 1) * this.itemsPerPage) + 1 : 0;
        const endItem = Math.min(this.currentPage * this.itemsPerPage, totalItems);
        resultsMeta.textContent = `Showing ${startItem}-${endItem} of ${totalItems} students`;

        paginationContainer.innerHTML = "";
        if (totalPages <= 1) {
            return;
        }

        paginationContainer.appendChild(this.buildPaginationLink("Prev", this.currentPage === 1, () => {
            this.currentPage -= 1;
            this.updateStudentsTable();
        }));

        const startPage = Math.max(1, this.currentPage - 2);
        const endPage = Math.min(totalPages, this.currentPage + 2);
        for (let page = startPage; page <= endPage; page += 1) {
            if (page === this.currentPage) {
                const current = document.createElement("span");
                current.className = "page-link is-current";
                current.textContent = `${page}`;
                paginationContainer.appendChild(current);
                continue;
            }

            paginationContainer.appendChild(this.buildPaginationLink(`${page}`, false, () => {
                this.currentPage = page;
                this.updateStudentsTable();
            }));
        }

        paginationContainer.appendChild(this.buildPaginationLink("Next", this.currentPage === totalPages, () => {
            this.currentPage += 1;
            this.updateStudentsTable();
        }));
    }

    buildPaginationLink(label, disabled, onClick) {
        const link = document.createElement("button");
        link.type = "button";
        link.className = "page-link";
        if (label === "Prev" || label === "Next") {
            link.classList.add("page-link-arrow");
        }
        if (disabled) {
            link.classList.add("is-disabled");
            link.disabled = true;
            link.textContent = label;
            return link;
        }

        link.textContent = label;
        link.addEventListener("click", () => {
            onClick();
        });
        return link;
    }

    exportStudentsData() {
        const students = this.currentData?.students || [];
        if (!students.length) {
            this.showError("No student data is available to export.");
            return;
        }

        const filteredStudents = this.getFilteredStudents(students);
        const headers = [
            "Registration Number",
            "Student Name",
            "Programme",
            "Academic Stage",
            "Decision",
            "Effective Cohort",
            "Original Cohort",
            "Shifted",
            "Zero Completion Reason",
            "Completion Rate",
        ];
        const rows = filteredStudents.map((student) => [
            student.regnum || "",
            student.student_name || "",
            student.programme_name || "",
            student.academic_stage || "",
            student.decision || "",
            student.effective_cohort || "",
            student.original_cohort || "",
            student.is_shifted ? "Yes" : "No",
            student.zero_completion_reason || "",
            `${Math.round(student.completion_rate || 0)}%`,
        ]);

        const csvContent = [headers, ...rows]
            .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, "\"\"")}"`).join(","))
            .join("\n");

        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `completion_analysis_${new Date().toISOString().split("T")[0]}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
    }

    resizeCharts() {
        Object.values(this.charts).forEach(chart => {
            if (chart && chart.chart) {
                chart.chart.resize();
            }
        });
    }

    toggleChartFullscreen(button) {
        const chartCard = button.closest(".demographic-insight-card");
        if (!chartCard) {
            return;
        }

        try {
            if (document.fullscreenElement === chartCard) {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                } else if (document.webkitExitFullscreen) {
                    document.webkitExitFullscreen();
                }
                this.fallbackFullscreenCard = null;
            } else if (this.fallbackFullscreenCard === chartCard) {
                this.fallbackFullscreenCard = null;
            } else if (chartCard.requestFullscreen) {
                chartCard.requestFullscreen();
            } else if (chartCard.webkitRequestFullscreen) {
                chartCard.webkitRequestFullscreen();
            } else {
                this.fallbackFullscreenCard = chartCard;
            }
        } catch (error) {
            this.fallbackFullscreenCard = this.fallbackFullscreenCard === chartCard ? null : chartCard;
        }

        this.syncFullscreenButtons();
        window.requestAnimationFrame(() => this.resizeCharts());
    }

    syncFullscreenButtons() {
        const fullscreenElement = document.fullscreenElement || document.webkitFullscreenElement || this.fallbackFullscreenCard;
        document.querySelectorAll("[data-chart-fullscreen-toggle]").forEach((button) => {
            const card = button.closest(".demographic-insight-card");
            const isActive = Boolean(card && fullscreenElement === card);
            if (card) {
                card.classList.toggle("is-fullscreen", isActive);
            }
            button.textContent = isActive ? "Exit full screen" : "Full screen";
            button.setAttribute("aria-pressed", isActive ? "true" : "false");
        });
    }

    resizeCharts() {
        Object.values(this.chartInstances).forEach((chart) => {
            if (chart && typeof chart.resize === "function") {
                chart.resize();
            }
        });
    }

    showError(message) {
        const messageElement = document.getElementById("error-message");
        const modal = document.getElementById("error-modal");
        if (messageElement) {
            messageElement.textContent = message;
        }
        if (modal) {
            modal.classList.add("active");
        }
    }

    hideErrorModal() {
        const modal = document.getElementById("error-modal");
        if (modal) {
            modal.classList.remove("active");
        }
    }

    showDrilldownLoading() {
        showLoadingDrillDownModal("Loading Drill-Down", "Loading student data.");
        return;
        // Use renderModal approach for consistency
        const renderModal = ({ title, subtitle = "", bodyHtml, toneClass = "" }) => {
            // Close any existing modal
            this.hideDrilldownLoading();
            
            const modalOverlay = document.createElement("div");
            modalOverlay.id = "completion-drilldown-loading-modal";
            modalOverlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.5);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 10010;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            `;
            
            const modalDialog = document.createElement("div");
            modalDialog.style.cssText = `
                background: white;
                padding: 30px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
                max-width: 400px;
                border: 1px solid rgba(184, 200, 217, 0.9);
            `;
            
            const modalHeader = document.createElement("div");
            modalHeader.style.cssText = `
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 20px;
            `;
            
            const modalTitle = document.createElement("h2");
            modalTitle.textContent = title;
            modalTitle.style.cssText = `
                margin: 0;
                color: #0d2f54;
                font-size: 1.05rem;
                font-weight: 700;
                line-height: 1.3;
            `;
            
            const modalClose = document.createElement("button");
            modalClose.textContent = "×";
            modalClose.style.cssText = `
                background: none;
                border: none;
                font-size: 1.5rem;
                cursor: pointer;
                color: #666;
                padding: 0;
                width: 24px;
                height: 24px;
            `;
            
            const modalBody = document.createElement("div");
            modalBody.innerHTML = bodyHtml;
            
            modalHeader.appendChild(modalTitle);
            modalHeader.appendChild(modalClose);
            modalDialog.appendChild(modalHeader);
            modalDialog.appendChild(modalBody);
            modalOverlay.appendChild(modalDialog);
            
            document.body.appendChild(modalOverlay);
            
            // Handle close button
            modalClose.addEventListener('click', () => {
                this.hideDrilldownLoading();
            });
            
            // Handle backdrop click
            modalOverlay.addEventListener('click', (e) => {
                if (e.target === modalOverlay) {
                    this.hideDrilldownLoading();
                }
            });
        };
        
        renderModal({
            title: "Loading Drilldown Data",
            subtitle: "",
            toneClass: "is-loading",
            bodyHtml: `
                <div class="completion-drilldown-state">
                    <div class="completion-drilldown-spinner"></div>
                    <p class="completion-drilldown-state-title">Loading student data...</p>
                    <p class="completion-drilldown-state-copy">Please wait while we gather the requested information.</p>
                </div>
            `.trim(),
        });
    }

    hideDrilldownLoading() {
        closeDrillDownModal();
        return;
        const loadingOverlay = document.getElementById("completion-drilldown-loading-modal");
        if (loadingOverlay) {
            loadingOverlay.remove();
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    new CompletionAnalysis();
});
