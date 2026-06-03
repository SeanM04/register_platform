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
    showDrillDownModal,
    showGraduationDrillDownModal,
    showLoadingDrillDownModal,
} from "./graduation/drilldown_modal.js?v=20260601-drilldown-numeric-align01";

class GraduationAnalysis {
    constructor() {
        this.root = document.querySelector(".graduation-layout");
        this.payloadUrl = this.root?.dataset.payloadUrl || "/metrics/graduation/payload/";
        this.narrativesUrl = this.root?.dataset.narrativesUrl || "/metrics/graduation/narratives/";
        this.currentData = null;
        this.currentNarratives = {};
        this.narrativeDiagnostics = {};
        this.currentPage = 1;
        this.itemsPerPage = 10;
        this.chartInstances = {};
        this.resizeTimeout = null;

        this.init();
    }

    async openDrillDown(chartKey, bucketKey, page = 1) {
        try {
            console.log("DEBUG: openDrillDown called with:", { chartKey, bucketKey, page });
            
            // Show instant loading indicator
            this.showDrilldownLoading();
            
            // Build drilldown request URL
            const drilldownUrl = new URL("/metrics/graduation/drilldown/", window.location.origin);
            
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
            
            // Fetch drilldown data with timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
            
            try {
                const response = await fetch(drilldownUrl.toString(), {
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                if (!response.ok) {
                    throw new Error(`Drilldown request failed: ${response.status} ${response.statusText}`);
                }
                
                const result = await response.json();
                console.log("DEBUG: drilldown response:", result);
                console.log("DEBUG: response status:", result.status);
                console.log("DEBUG: response data:", result.data);
                
                if (result.status === 'success' && result.data) {
                    this.hideDrilldownLoading();
                    showGraduationDrillDownModal(result.data, (page) => {
                        this.openDrillDown(chartKey, bucketKey, page);
                    });
                } else {
                    console.log("DEBUG: response format unexpected:", result);
                    throw new Error(result.message || 'No drilldown data available');
                }
            } catch (fetchError) {
                clearTimeout(timeoutId);
                if (fetchError.name === 'AbortError') {
                    throw new Error('Drilldown request timed out. Please try again.');
                }
                throw fetchError;
            }
            
        } catch (error) {
            this.hideDrilldownLoading();
            console.error("Error opening drilldown:", error);
            // Show error modal or notification
            alert(`Error loading drilldown data: ${error.message}`);
        }
    }

    async init() {
        this.bindEvents();
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
            headers: { "X-Requested-With": "XMLHttpRequest" },
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
            }, { passive: true });
        }

        const exportButton = document.getElementById("export-students");
        if (exportButton) {
            exportButton.addEventListener("click", () => this.exportStudentsData(), { passive: true });
        }

        const errorModalClose = document.getElementById("error-modal-close");
        if (errorModalClose) {
            errorModalClose.addEventListener("click", () => this.hideErrorModal(), { passive: true });
        }

        const errorModal = document.getElementById("error-modal");
        if (errorModal) {
            errorModal.addEventListener("click", (event) => {
                if (event.target === errorModal) {
                    this.hideErrorModal();
                }
            }, { passive: true });
        }

        document.querySelectorAll("[data-chart-fullscreen-toggle]").forEach((button) => {
            button.addEventListener("click", (event) => this.toggleChartFullscreen(event.currentTarget), { passive: true });
        });

        document.querySelectorAll(".demographic-accordion-toggle").forEach((button) => {
            button.addEventListener("click", () => {
                // Use a more efficient approach with debouncing
                this.debouncedResizeCharts();
            }, { passive: true });
        });

        window.addEventListener("resize", () => this.debouncedResizeCharts(), { passive: true });
        document.addEventListener("fullscreenchange", () => {
            this.syncFullscreenButtons();
            this.debouncedResizeCharts();
        }, { passive: true });
        document.addEventListener("webkitfullscreenchange", () => {
            this.syncFullscreenButtons();
            this.debouncedResizeCharts();
        }, { passive: true });
    }

    async loadData() {
        try {
            const payload = await this.fetchJson(this.payloadUrl);
            if (payload.status !== "success") {
                throw new Error(payload.message || "Failed to load graduation analytics");
            }

            this.currentData = payload.data;
            this.updateMetrics();
            this.updateCharts();
            this.updateStudentsTable();
        } catch (error) {
            this.showError(`Failed to load graduation data: ${error.message}`);
        }
    }

    updateMetrics() {
        const kpis = this.currentData?.kpis || {};
        this.updateMetricValue("total_graduated_students", kpis.total_graduated_students || 0);
        this.updateMetricValue("average_graduation_rate", kpis.average_graduation_rate || 0, true);
        this.updateMetricValue("on_time_graduation_rate", kpis.on_time_graduation_rate || 0, true);
        this.updateMetricValue("best_faculty_rate", kpis.best_faculty_rate || 0, true);
        this.updateMetricNotes(this.currentData?.summary_cards || []);

        const facultyNameElement = document.getElementById("best-faculty-name");
        if (facultyNameElement) {
            facultyNameElement.textContent = kpis.best_faculty_name || "";
            facultyNameElement.removeAttribute("data-faculty-loading");
        }
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
            const note = document.querySelector(`.graduation-metric-note[data-metric-key="${card.key}"]`);
            if (note) {
                note.textContent = card.note || "";
            }
        });
    }

    updateCharts() {
        const charts = this.currentData?.charts || {};
        this.renderProgrammeChart(charts.programme_graduation_rate || []);
        this.renderCohortChart(charts.cohort_graduation_rate || []);
        this.renderFacultyChart(charts.faculty_graduation_rate || []);
        this.renderTimingChart(charts.graduation_timing || []);
        this.renderReadinessProgrammeChart(charts.readiness_programmes || []);
        this.renderReadinessCohortChart(charts.readiness_cohorts || []);
        this.renderReadinessNotes();
    }

    renderStoryBanner() {
        const banner = document.getElementById("graduation-story-banner");
        const data = this.currentData;
        if (!banner || !data) {
            return;
        }

        const kpis = data.kpis || {};
        const programmeRows = data.charts?.programme_graduation_rate || [];
        const facultyRows = data.charts?.faculty_graduation_rate || [];
        const timingRows = data.charts?.graduation_timing || [];
        const topProgramme = programmeRows[0] || null;
        const topFaculty = facultyRows[0] || null;
        const onTimeCount = (timingRows.find((row) => row.label === "On-time") || {}).count || 0;
        const delayedCount = (timingRows.find((row) => row.label === "Delayed") || {}).count || 0;
        const totalGraduates = Number(kpis.total_graduated_students || 0);
        const averageRate = Number(kpis.average_graduation_rate || 0);
        const onTimeRate = Number(kpis.on_time_graduation_rate || 0);
        const meta = data.meta || {};
        const oneStepCount = Number(meta.students_one_step_from_target || 0);
        const withinTwoCount = Number(meta.students_within_two_steps || 0);

        if (!meta.has_graduates) {
            banner.innerHTML = `
                <div>
                    <p class="completion-banner-title">Current graduation filters show active progression data, but no visible student has reached the documented graduation rule yet.</p>
                    <p class="completion-banner-description">${escapeTooltipHtml(meta.snapshot_message || "The current snapshot contains progression records but no terminal graduation evidence.")}</p>
                </div>
                <div class="completion-banner-grid">
                    <article class="completion-banner-card">
                        <p class="completion-banner-card-kicker">Visible Graduates</p>
                        <p class="completion-banner-card-value">0</p>
                        <p class="completion-banner-card-copy">No visible records currently satisfy the documented graduation rule.</p>
                    </article>
                    <article class="completion-banner-card">
                        <p class="completion-banner-card-kicker">One Step Away</p>
                        <p class="completion-banner-card-value">${escapeTooltipHtml(`${oneStepCount}`)}</p>
                        <p class="completion-banner-card-copy">${escapeTooltipHtml(`${oneStepCount} students are one visible step from their target graduation stage.`)}</p>
                    </article>
                    <article class="completion-banner-card">
                        <p class="completion-banner-card-kicker">Within Two Steps</p>
                        <p class="completion-banner-card-value">${escapeTooltipHtml(`${withinTwoCount}`)}</p>
                        <p class="completion-banner-card-copy">${escapeTooltipHtml(`${withinTwoCount} students are within two visible steps of graduation eligibility.`)}</p>
                    </article>
                </div>
            `.trim();
            return;
        }

        let title = "Graduation outcomes are visible across the current scope.";
        if (averageRate >= 75 && onTimeRate >= 70) {
            title = "Graduation performance is broadly strong, with most visible graduates finishing on time.";
        } else if (averageRate < 60 || onTimeRate < 50) {
            title = "Graduation pressure is concentrated in delayed outcomes and weaker cohort conversion across the visible scope.";
        }

        const copyParts = [
            `${Math.round(averageRate)}% average graduation rate across ${totalGraduates} visible graduates`,
            `${Math.round(onTimeRate)}% of visible graduates finished on time`,
            `${delayedCount} visible graduates completed after a cohort shift`,
        ];
        if (topProgramme?.programme_name) {
            copyParts.push(`${this.formatProgrammeAxisLabel(topProgramme.programme_name)} leads visible programme graduation at ${Math.round(topProgramme.graduation_rate)}%`);
        }

        banner.innerHTML = `
            <div>
                <p class="completion-banner-title">${escapeTooltipHtml(title)}</p>
                <p class="completion-banner-description">${escapeTooltipHtml(`${copyParts.join(", ")}.`)}</p>
            </div>
            <div class="completion-banner-grid">
                <article class="completion-banner-card">
                    <p class="completion-banner-card-kicker">Graduation Baseline</p>
                    <p class="completion-banner-card-value">${escapeTooltipHtml(`${Math.round(averageRate)}% avg`)}</p>
                    <p class="completion-banner-card-copy">${escapeTooltipHtml(`${totalGraduates} visible graduates are in the current scope.`)}</p>
                </article>
                <article class="completion-banner-card">
                    <p class="completion-banner-card-kicker">Timing Pressure</p>
                    <p class="completion-banner-card-value">${escapeTooltipHtml(`${Math.round(onTimeRate)}% on time`)}</p>
                    <p class="completion-banner-card-copy">${escapeTooltipHtml(`${onTimeCount} on-time graduates versus ${delayedCount} delayed graduates are visible here.`)}</p>
                </article>
                <article class="completion-banner-card">
                    <p class="completion-banner-card-kicker">${escapeTooltipHtml(topFaculty?.faculty || "Best Faculty")}</p>
                    <p class="completion-banner-card-value">${escapeTooltipHtml(`${Math.round(topFaculty?.graduation_rate || 0)}%`)}</p>
                    <p class="completion-banner-card-copy">${escapeTooltipHtml(
                        topFaculty?.faculty
                            ? `${topFaculty.faculty} currently leads faculty-level graduation performance.`
                            : "Faculty leadership becomes visible once graduation rows are available.",
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

        return `
            <span class="completion-ai-badge-group">
                <span class="completion-ai-badge is-${normalizedSeverity}" title="${escapeTooltipHtml(`${providerLabel}; ${this.getSeverityLabel(normalizedSeverity).toLowerCase()}; ${this.getConfidenceLabel(normalizedConfidence).toLowerCase()}`)}" aria-label="${escapeTooltipHtml(`${providerLabel}; ${this.getSeverityLabel(normalizedSeverity).toLowerCase()}; ${this.getConfidenceLabel(normalizedConfidence).toLowerCase()}`)}">
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
        const meta = this.currentData?.meta || {};
        const programmeRows = charts.programme_graduation_rate || [];
        const cohortRows = charts.cohort_graduation_rate || [];
        const facultyRows = charts.faculty_graduation_rate || [];
        const timingRows = charts.graduation_timing || [];
        const strongestProgramme = programmeRows[0] || null;
        const weakestProgramme = [...programmeRows].slice(-1)[0] || null;
        const weakestCohort = [...cohortRows].sort((left, right) => left.graduation_rate - right.graduation_rate)[0] || null;
        const strongestFaculty = facultyRows[0] || null;
        const weakestFaculty = [...facultyRows].slice(-1)[0] || null;
        const onTimeCount = (timingRows.find((row) => row.label === "On-time") || {}).count || 0;
        const delayedCount = (timingRows.find((row) => row.label === "Delayed") || {}).count || 0;
        const totalTimed = Math.max(onTimeCount + delayedCount, 1);
        const onTimeRate = Math.round((onTimeCount / totalTimed) * 100);
        const oneStepCount = Number(meta.students_one_step_from_target || 0);
        const withinTwoCount = Number(meta.students_within_two_steps || 0);

        if (!meta.has_graduates) {
            return {
                programme: {
                    insight: meta.snapshot_message || "No visible students currently meet the documented graduation rule.",
                    action: `Use the readiness charts first: ${oneStepCount} students are one visible step from target and ${withinTwoCount} are within two steps.`,
                    severity: oneStepCount > 0 ? "medium" : "stable",
                    confidence: "low",
                },
                cohort: {
                    insight: "Cohort graduation rates remain empty because no effective cohort has yet produced a visible graduate in the current snapshot.",
                    action: "Use readiness by cohort to see which effective intakes are closest to producing the first visible graduates.",
                    severity: "stable",
                    confidence: "low",
                },
                faculty: {
                    insight: "Faculty graduation rates remain empty because the current snapshot has progression records but no terminal graduation evidence.",
                    action: "Use readiness and later-period data to see which faculties are closest to crossing into visible graduation outcomes.",
                    severity: "stable",
                    confidence: "low",
                },
                timing: {
                    insight: "On-time versus delayed graduation will only appear once at least one visible student reaches the documented graduation rule.",
                    action: "Use the readiness charts to monitor whether near-target students are concentrated in one programme or cohort before the next data refresh.",
                    severity: "stable",
                    confidence: "low",
                },
            };
        }

        return {
            programme: {
                insight: strongestProgramme && weakestProgramme
                    ? `${this.formatProgrammeAxisLabel(strongestProgramme.programme_name)} leads visible programme graduation at ${Math.round(strongestProgramme.graduation_rate)}%, while ${this.formatProgrammeAxisLabel(weakestProgramme.programme_name)} trails at ${Math.round(weakestProgramme.graduation_rate)}%.`
                    : "No programme graduation narrative is available for the current filters.",
                action: weakestProgramme
                    ? "Use the programme chart to focus first on the weakest graduation programmes before moving into student-level detail."
                    : "Adjust the current filters to bring programme graduation patterns back into view.",
                severity: weakestProgramme && weakestProgramme.graduation_rate < 50 ? "high" : weakestProgramme && weakestProgramme.graduation_rate < 70 ? "medium" : "stable",
                confidence: "low",
            },
            cohort: {
                insight: weakestCohort
                    ? `${weakestCohort.effective_cohort_label} is the weakest visible graduation cohort at ${Math.round(weakestCohort.graduation_rate)}% with ${weakestCohort.graduated_count} graduates.`
                    : "No cohort graduation narrative is available for the current filters.",
                action: weakestCohort
                    ? "Use the cohort chart to compare intakes where graduation conversion is lagging behind the stronger cohorts."
                    : "Adjust the current filters to bring cohort graduation patterns back into view.",
                severity: weakestCohort && weakestCohort.graduation_rate < 45 ? "high" : weakestCohort && weakestCohort.graduation_rate < 65 ? "medium" : "stable",
                confidence: "low",
            },
            faculty: {
                insight: strongestFaculty && weakestFaculty
                    ? `${strongestFaculty.faculty} leads faculty graduation at ${Math.round(strongestFaculty.graduation_rate)}%, while ${weakestFaculty.faculty} is lowest at ${Math.round(weakestFaculty.graduation_rate)}%.`
                    : "No faculty graduation narrative is available for the current filters.",
                action: strongestFaculty
                    ? "Use the faculty comparison to see whether weak graduation outcomes are concentrated in one part of the institution."
                    : "Adjust the current filters to bring faculty graduation patterns back into view.",
                severity: weakestFaculty && weakestFaculty.graduation_rate < 50 ? "high" : weakestFaculty && weakestFaculty.graduation_rate < 70 ? "medium" : "stable",
                confidence: "low",
            },
            timing: {
                insight: `${onTimeRate}% of visible graduates are on time, while ${Math.round((delayedCount / totalTimed) * 100)}% completed after an effective-cohort shift.`,
                action: "Use the timing split to separate clean graduation flow from delayed progression paths.",
                severity: onTimeRate < 45 ? "high" : onTimeRate < 70 ? "medium" : "stable",
                confidence: "low",
            },
        };
    }

    renderFallbackNarratives() {
        const fallback = this.getFallbackNarratives();
        this.applyNarrativeCard("programme", fallback.programme, { narrativeSource: "rules", narrativesAreAi: false });
        this.applyNarrativeCard("cohort", fallback.cohort, { narrativeSource: "rules", narrativesAreAi: false });
        this.applyNarrativeCard("faculty", fallback.faculty, { narrativeSource: "rules", narrativesAreAi: false });
        this.applyNarrativeCard("timing", fallback.timing, { narrativeSource: "rules", narrativesAreAi: false });
    }

    applyNarrativeCard(cardKey, narrative, flags = {}) {
        const copyElement = document.getElementById(`graduation-${cardKey}-copy`);
        const hintElement = document.getElementById(`graduation-${cardKey}-hints`);
        const noteElement = document.getElementById(`graduation-${cardKey}-note`);
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

                this.applyNarrativeCard("programme", { ...fallback.programme, ...(cards.programme || {}) }, flags);
                this.applyNarrativeCard("cohort", { ...fallback.cohort, ...(cards.cohort || {}) }, flags);
                this.applyNarrativeCard("faculty", { ...fallback.faculty, ...(cards.faculty || {}) }, flags);
                this.applyNarrativeCard("timing", { ...fallback.timing, ...(cards.timing || {}) }, flags);
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
            setChartFallback(element, "ECharts could not load. The graduation table is still available.");
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

    renderProgrammeChart(rows) {
        const element = document.getElementById("programme-graduation-chart");
        if (!element) {
            return;
        }
        if (!rows || rows.length === 0) {
            setChartFallback(element, "No programme graduation data is available for the current filters.");
            return;
        }

        const chart = this.getOrCreateChart("programme-graduation-chart");
        if (!chart) {
            return;
        }

        const topRows = [...rows].slice(0, 12).reverse();
        const backgroundTrackColor = "rgba(148, 163, 184, 0.18)";
        const barCornerRadius = 5;

        chart.setOption({
            ...buildAnimationConfig(topRows),
            grid: { left: 168, right: 28, top: 18, bottom: 24 },
            tooltip: {
                ...buildTooltipBase("item"),
                formatter: (params) => {
                    const row = topRows[params.dataIndex];
                    return buildTooltipMarkup(row.programme_name, [
                        { label: "Graduation rate", value: `${row.graduation_rate}%` },
                        { label: "Graduates", value: `${row.graduated_count}` },
                    ]);
                },
            },
            xAxis: {
                type: "value",
                min: 0,
                max: 100,
                axisLabel: { color: "#475569", formatter: "{value}%" },
                splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.2)" } },
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
                    autoSkip: false,
                    maxRotation: 45,
                    minRotation: 45
                },
                axisLine: { lineStyle: { color: "#cbd5e1" } },
            },
            dataZoom: buildVerticalCategoryZoom(topRows, { visibleCount: 12, showSlider: true }),
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
                        value: row.graduation_rate,
                        raw: { programme_name: row.programme_name },
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
                        formatter: "{c}%",
                    },
                },
            ],
        }, true);

        // Add click handler for drilldown
        chart.off('click').on('click', (params) => {
            console.log("DEBUG: programme graduation chart clicked:", params);
            if (params.dataIndex !== undefined && topRows[params.dataIndex]) {
                const programme = topRows[params.dataIndex];
                if (programme.programme_name) {
                    this.openDrillDown('graduation_programmes', programme.programme_name);
                }
            }
        });
    }

    renderCohortChart(rows) {
        const element = document.getElementById("cohort-graduation-chart");
        if (!element) {
            return;
        }
        if (!rows || rows.length === 0) {
            setChartFallback(element, "No cohort graduation data is available for the current filters.");
            return;
        }

        const chart = this.getOrCreateChart("cohort-graduation-chart");
        if (!chart) {
            return;
        }

        const sortedRows = [...rows].sort((a, b) => a.effective_cohort_sort_index - b.effective_cohort_sort_index);
        const barCornerRadius = 5;

        chart.setOption({
            ...buildAnimationConfig(sortedRows),
            grid: { left: 52, right: 24, top: 18, bottom: 86 },
            tooltip: {
                ...buildTooltipBase("item"),
                formatter: (params) => {
                    const row = sortedRows[params.dataIndex];
                    return buildTooltipMarkup(row.original_cohort_label, [
                        { label: "Graduation rate", value: `${row.graduation_rate}%` },
                        { label: "Graduated", value: `${row.graduated_count}` },
                        { label: "Enrolled", value: `${row.enrolled_count}` },
                    ]);
                },
            },
            xAxis: {
                type: "category",
                data: sortedRows.map((row) => formatChartLabel(row.original_cohort_label, 18)),
                axisLabel: {
                    color: "#475569",
                    fontSize: 11,
                    interval: 0,
                    rotate: sortedRows.length > 6 ? 24 : 0,
                    autoSkip: false,
                    maxRotation: 45,
                    minRotation: 45
                },
                axisLine: { lineStyle: { color: "#cbd5e1" } },
                axisTick: { show: true, alignWithLabel: true },
            },
            yAxis: {
                type: "value",
                min: 0,
                max: 100,
                axisLabel: { color: "#475569", formatter: "{value}%" },
                splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.2)" } },
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
                    barWidth: 22,
                    data: sortedRows.map((row) => ({
                        value: row.graduation_rate,
                        raw: { original_cohort_label: row.original_cohort_label },
                        itemStyle: {
                            borderRadius: [barCornerRadius, barCornerRadius, 0, 0],
                            color: buildGradient("#0f4c81", "#50b0d1", "vertical"),
                        },
                    })),
                    label: {
                        show: true,
                        position: "top",
                        color: "#0f172a",
                        fontWeight: 700,
                        formatter: "{c}%",
                    },
                },
            ],
        }, true);

        // Add click handler for drilldown
        chart.off('click').on('click', (params) => {
            console.log("DEBUG: cohort graduation chart clicked:", params);
            if (params.data && params.data.raw && params.data.raw.original_cohort_label) {
                this.openDrillDown('graduation_cohorts', params.data.raw.original_cohort_label);
            }
        });
    }

    renderFacultyChart(rows) {
        const element = document.getElementById("faculty-graduation-chart");
        if (!element) {
            return;
        }
        if (!rows || rows.length === 0) {
            setChartFallback(element, "No faculty graduation data is available for the current filters.");
            return;
        }

        const chart = this.getOrCreateChart("faculty-graduation-chart");
        if (!chart) {
            return;
        }

        const sortedRows = [...rows].slice(0, 10);
        const barCornerRadius = 5;

        chart.setOption({
            ...buildAnimationConfig(sortedRows),
            grid: { left: 52, right: 24, top: 18, bottom: 86 },
            tooltip: {
                ...buildTooltipBase("item"),
                formatter: (params) => {
                    const row = sortedRows[params.dataIndex];
                    const hierarchy = row.hierarchy || {};
                    const deptCount = hierarchy.departments ? hierarchy.departments.length : 0;
                    const progCount = hierarchy.programmes ? hierarchy.programmes.length : 0;
                    
                    return buildTooltipMarkup(row.faculty, [
                        { label: "Graduation rate", value: `${row.graduation_rate}%` },
                        { label: "Graduated", value: `${row.graduated_count}` },
                        { label: "Enrolled", value: `${row.enrolled_count}` },
                        { label: "Departments", value: `${deptCount}` },
                        { label: "Programmes", value: `${progCount}` },
                        { label: "Click to drill down", value: "View departments/programmes" },
                    ]);
                },
            },
            xAxis: {
                type: "category",
                data: sortedRows.map((row) => formatChartLabel(row.faculty, 18)),
                axisLabel: {
                    color: "#475569",
                    fontSize: 11,
                    interval: 0,
                    rotate: sortedRows.length > 4 ? 18 : 0,
                },
                axisLine: { lineStyle: { color: "#cbd5e1" } },
                axisTick: { show: true, alignWithLabel: true },
            },
            yAxis: {
                type: "value",
                min: 0,
                max: 100,
                axisLabel: { color: "#475569", formatter: "{value}%" },
                splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.2)" } },
            },
            series: [
                {
                    type: "bar",
                    barWidth: 24,
                    showBackground: true,
                    backgroundStyle: {
                        color: "rgba(148, 163, 184, 0.16)",
                        borderRadius: [barCornerRadius, barCornerRadius, 0, 0],
                    },
                    data: sortedRows.map((row) => ({
                        value: row.graduation_rate,
                        raw: { faculty_name: row.faculty_name },
                        itemStyle: {
                            borderRadius: [barCornerRadius, barCornerRadius, 0, 0],
                            color: buildGradient("#0c7489", "#74d2e7", "vertical"),
                        },
                    })),
                    label: {
                        show: true,
                        position: "top",
                        color: "#0f172a",
                        fontWeight: 700,
                        formatter: "{c}%",
                    },
                },
            ],
        }, true);

        // Add click handler for drilldown
        chart.off('click').on('click', (params) => {
            console.log("DEBUG: faculty graduation chart clicked:", params);
            if (params.dataIndex !== undefined && sortedRows[params.dataIndex]) {
                const faculty = sortedRows[params.dataIndex];
                this.showHierarchicalDrilldown(faculty);
            }
        });
    }

    showHierarchicalDrilldown(faculty) {
        const hierarchy = faculty.hierarchy || {};
        const departments = hierarchy.departments || [];
        const programmes = hierarchy.programmes || [];

        const data = [
            {
                label: `All ${faculty.faculty} students`,
                count: Number(faculty.enrolled_count || 0),
                department: `Faculty total, ${Math.round(faculty.graduation_rate || 0)}% graduation rate`,
                next_chart: "faculties",
                next_bucket: faculty.faculty,
            },
            ...departments.map((dept) => ({
                label: dept.department,
                count: Number(dept.enrolled_count || dept.graduated_count || 0),
                department: `Department, ${Math.round(dept.graduation_rate || 0)}% graduation rate`,
                next_chart: "departments",
                next_bucket: dept.department,
            })),
            ...programmes.map((programme) => ({
                label: programme.programme,
                count: Number(programme.enrolled_count || programme.graduated_count || 0),
                department: `Programme, ${Math.round(programme.graduation_rate || 0)}% graduation rate`,
                next_chart: "programmes",
                next_bucket: programme.programme,
            })),
        ];

        showDrillDownModal({
            title: `${faculty.faculty} Drill-Down`,
            subtitle: "Choose a department or programme to view matching students.",
            type: "programmes",
            data,
            breadcrumbs: [{ label: faculty.faculty }],
        }, [], {
            onNavigate: (target) => {
                if (!target?.chart || !target?.bucket) {
                    return;
                }
                this.openDrillDown(target.chart, target.bucket);
            },
        });
    }

    renderTimingChart(rows) {
        const element = document.getElementById("graduation-timing-chart");
        if (!element) {
            return;
        }
        if (!rows || rows.length === 0) {
            setChartFallback(element, "No graduation timing data is available for the current filters.");
            return;
        }

        const chart = this.getOrCreateChart("graduation-timing-chart");
        if (!chart) {
            return;
        }

        const total = Math.max(rows.reduce((sum, row) => sum + Number(row.count || 0), 0), 1);
        const palette = { "On-time": "#0f766e", Delayed: "#dc2626" };
        const barCornerRadius = 5;

        chart.setOption({
            ...buildAnimationConfig(rows),
            grid: { left: 48, right: 18, top: 18, bottom: 40 },
            tooltip: {
                ...buildTooltipBase("item"),
                formatter: (params) => {
                    const row = rows[params.dataIndex];
                    const share = Math.round((Number(row.count || 0) / total) * 100);
                    return buildTooltipMarkup(row.label, [
                        { label: "Graduates", value: `${row.count}` },
                        { label: "Share", value: `${share}%` },
                    ]);
                },
            },
            xAxis: {
                type: "category",
                data: rows.map((row) => row.label),
                axisLabel: { color: "#475569", fontWeight: 700 },
                axisLine: { lineStyle: { color: "#cbd5e1" } },
                axisTick: { show: true, alignWithLabel: true },
            },
            yAxis: {
                type: "value",
                minInterval: 1,
                axisLabel: { color: "#475569" },
                splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.2)" } },
            },
            series: [
                {
                    type: "bar",
                    barWidth: 28,
                    data: rows.map((row) => ({
                        value: row.count,
                        itemStyle: {
                            borderRadius: [barCornerRadius, barCornerRadius, 0, 0],
                            color: palette[row.label] || "#4fb0d1",
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
            console.log("DEBUG: graduation timing chart clicked:", params);
            if (params.dataIndex !== undefined && rows[params.dataIndex]) {
                const timing = rows[params.dataIndex];
                if (timing.label) {
                    this.openDrillDown('timing', timing.label);
                }
            }
        });
    }

    renderReadinessProgrammeChart(rows) {
        const element = document.getElementById("graduation-readiness-programme-chart");
        if (!element) {
            return;
        }
        if (!rows || rows.length === 0) {
            setChartFallback(element, "No near-graduation programme readiness data is available for the current filters.");
            return;
        }

        const chart = this.getOrCreateChart("graduation-readiness-programme-chart");
        if (!chart) {
            return;
        }

        const topRows = [...rows].slice(0, 12).reverse();
        const barCornerRadius = 5;
        const backgroundTrackColor = "rgba(148, 163, 184, 0.18)";

        chart.setOption({
            ...buildAnimationConfig(topRows),
            grid: { left: 168, right: 28, top: 18, bottom: 24 },
            tooltip: {
                ...buildTooltipBase("item"),
                formatter: (params) => {
                    const row = topRows[params.dataIndex];
                    return buildTooltipMarkup(row.programme_name, [
                        { label: "One-step students", value: `${row.student_count}` },
                        { label: "Closest remaining steps", value: `${row.closest_remaining_steps}` },
                    ]);
                },
            },
            xAxis: {
                type: "value",
                minInterval: 1,
                axisLabel: { color: "#475569" },
                splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.2)" } },
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
                axisLine: { lineStyle: { color: "#cbd5e1" } },
            },
            dataZoom: buildVerticalCategoryZoom(topRows, { visibleCount: 12, showSlider: true }),
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
                        value: row.student_count,
                        itemStyle: {
                            borderRadius: [0, barCornerRadius, barCornerRadius, 0],
                            color: buildGradient("#0f766e", "#6ee7b7"),
                        },
                    })),
                    label: {
                        show: true,
                        position: "right",
                        color: "#0f172a",
                        fontWeight: 700,
                        formatter: "{c}",
                    },
                },
            ],
        }, true);

        // Add click handler for drilldown
        chart.off('click').on('click', (params) => {
            console.log("DEBUG: readiness programme chart clicked:", params);
            if (params.dataIndex !== undefined && topRows[params.dataIndex]) {
                const programme = topRows[params.dataIndex];
                if (programme.programme_name) {
                    this.openDrillDown('readiness_programmes', programme.programme_name);
                }
            }
        });
    }

    renderReadinessCohortChart(rows) {
        const element = document.getElementById("graduation-readiness-cohort-chart");
        if (!element) {
            return;
        }
        if (!rows || rows.length === 0) {
            setChartFallback(element, "No near-graduation cohort readiness data is available for the current filters.");
            return;
        }

        const chart = this.getOrCreateChart("graduation-readiness-cohort-chart");
        if (!chart) {
            return;
        }

        const sortedRows = [...rows].sort((a, b) => a.effective_cohort_sort_index - b.effective_cohort_sort_index);
        const barCornerRadius = 5;

        chart.setOption({
            ...buildAnimationConfig(sortedRows),
            grid: { left: 52, right: 24, top: 18, bottom: 86 },
            tooltip: {
                ...buildTooltipBase("item"),
                formatter: (params) => {
                    const row = sortedRows[params.dataIndex];
                    return buildTooltipMarkup(row.effective_cohort_label, [
                        { label: "One-step students", value: `${row.student_count}` },
                        { label: "Closest remaining steps", value: `${row.closest_remaining_steps}` },
                    ]);
                },
            },
            xAxis: {
                type: "category",
                data: sortedRows.map((row) => formatChartLabel(row.effective_cohort_label, 18)),
                axisLabel: {
                    color: "#475569",
                    fontSize: 11,
                    interval: 0,
                    rotate: sortedRows.length > 6 ? 24 : 0,
                },
                axisLine: { lineStyle: { color: "#cbd5e1" } },
                axisTick: { show: true, alignWithLabel: true },
            },
            yAxis: {
                type: "value",
                minInterval: 1,
                axisLabel: { color: "#475569" },
                splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.2)" } },
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
                    barWidth: 22,
                    showBackground: true,
                    backgroundStyle: {
                        color: "rgba(148, 163, 184, 0.16)",
                        borderRadius: [barCornerRadius, barCornerRadius, 0, 0],
                    },
                    data: sortedRows.map((row) => ({
                        value: row.student_count,
                        itemStyle: {
                            borderRadius: [barCornerRadius, barCornerRadius, 0, 0],
                            color: buildGradient("#0f4c81", "#50b0d1", "vertical"),
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
            console.log("DEBUG: readiness cohort chart clicked:", params);
            if (params.dataIndex !== undefined && sortedRows[params.dataIndex]) {
                const cohort = sortedRows[params.dataIndex];
                if (cohort.effective_cohort_label) {
                    this.openDrillDown('readiness_cohorts', cohort.effective_cohort_label);
                }
            }
        });
    }

    renderReadinessNotes() {
        this.setActionText(
            document.getElementById("graduation-readiness-programme-note"),
            "Use this chart to see which programmes are one visible step from the documented graduation target.",
            { showGuidanceBadge: true, severity: "medium", confidence: "medium" },
        );
        this.setActionText(
            document.getElementById("graduation-readiness-cohort-note"),
            "Use this chart to see which effective cohorts are closest to producing the first visible graduates in the current snapshot.",
            { showGuidanceBadge: true, severity: "medium", confidence: "medium" },
        );
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

    getFilteredStudents(students) {
        const searchTerm = (document.getElementById("student-search")?.value || "").trim().toLowerCase();
        if (!searchTerm) {
            return students;
        }
        return students.filter((student) => (
            (student.regnum || "").toLowerCase().includes(searchTerm)
            || (student.student_name || "").toLowerCase().includes(searchTerm)
            || (student.programme_name || "").toLowerCase().includes(searchTerm)
            || (student.faculty || "").toLowerCase().includes(searchTerm)
            || (student.graduation_stage || "").toLowerCase().includes(searchTerm)
            || (student.effective_cohort || "").toLowerCase().includes(searchTerm)
        ));
    }

    updateStudentsTable() {
        const students = this.currentData?.students || [];

        const sortedStudents = [...students].sort((a, b) => {
    const getLastName = (name) => {
        const parts = (name || "").trim().split(" ");
        return parts[parts.length - 1].toLowerCase();
    };

    return getLastName(a.student_name).localeCompare(getLastName(b.student_name));
});

        const tbody = document.getElementById("students-tbody");
        if (!tbody) {
            return;
        }

        const filteredStudents = this.getFilteredStudents(sortedStudents);
        const paginatedStudents = this.getPaginatedStudents(filteredStudents);

        if (!paginatedStudents.length) {
            const message = String(this.currentData?.meta?.snapshot_message || "").trim();
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="completion-empty-state">
                        <div class="completion-empty-state-title">No Graduates Found</div>
                        <div class="completion-empty-state-description">${escapeTooltipHtml(message || "No graduation records match the current filters.")}</div>
                    </td>
                </tr>
            `;
            this.updatePagination(filteredStudents.length);
            return;
        }

        tbody.innerHTML = "";
        const fragment = document.createDocumentFragment();
        paginatedStudents.forEach((student) => fragment.appendChild(this.createStudentRow(student)));
        tbody.appendChild(fragment);
        this.updatePagination(filteredStudents.length);
    }

    createStudentRow(student) {
    const row = document.createElement("tr");

    const graduationStage = String(
        student.graduation_period_label || student.graduation_stage || ""
    )
        .replace(/,\s*/g, " ")
        .replace(/\s+/g, " ")
        .trim();

    const effectiveCohort = String(student.effective_cohort || "")
        .replace(/^is-(original|shifted)"?>?/i, "")
        .trim();

    row.innerHTML = `
        <td class="students-td-name">
            <a class="student-link" href="/students/${encodeURIComponent(student.detail_slug || String(student.regnum || "").toLowerCase())}/" aria-label="View ${escapeTooltipHtml(student.student_name || "")} profile">
                <span class="student-link-name">${escapeTooltipHtml(student.student_name || "")}</span>
            </a>
        </td>
        <td>${escapeTooltipHtml(student.programme_name || "")}</td>
        <td>${escapeTooltipHtml(student.faculty || "")}</td>
        <td>${escapeTooltipHtml(graduationStage)}</td>
        <td>${escapeTooltipHtml(effectiveCohort)}</td>
        <td>${Math.round(student.graduation_rate || 0)}%</td>
        <td class="graduation-timing-cell ${student.on_time ? "on-time" : "delayed"}">${student.on_time ? "On time" : "Delayed"}</td>
    `;

    return row;

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
        resultsMeta.textContent = `Showing ${startItem}-${endItem} of ${totalItems} graduates`;

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
        }, { passive: true });
        return link;
    }

    exportStudentsData() {
        const students = this.currentData?.students || [];
        if (!students.length) {
            this.showError("No graduation data is available to export.");
            return;
        }

        const filteredStudents = this.getFilteredStudents(students);
        const headers = ["Registration Number", "Student Name", "Programme", "Faculty", "Graduation Stage", "Graduation Period", "Effective Cohort", "Original Cohort", "On Time", "Graduation Rate"];
        const rows = filteredStudents.map((student) => [
            student.regnum || "",
            student.student_name || "",
            student.programme_name || "",
            student.faculty || "",
            student.graduation_stage || "",
            student.graduation_period_label || "",
            student.effective_cohort || "",
            student.original_cohort || "",
            student.on_time ? "Yes" : "No",
            `${Math.round(student.graduation_rate || 0)}%`,
        ]);

        const csvContent = [headers, ...rows]
            .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, "\"\"")}"`).join(","))
            .join("\n");

        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `graduation_analysis_${new Date().toISOString().split("T")[0]}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
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

    debouncedResizeCharts() {
        // Clear existing timeout
        if (this.resizeTimeout) {
            clearTimeout(this.resizeTimeout);
        }
        
        // Set new timeout with reduced delay
        this.resizeTimeout = setTimeout(() => {
            this.resizeCharts();
        }, 100);
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
            modalOverlay.id = "graduation-drilldown-loading-modal";
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
                <div class="graduation-drilldown-state">
                    <div class="graduation-drilldown-spinner"></div>
                    <p class="graduation-drilldown-state-title">Loading student data...</p>
                    <p class="graduation-drilldown-state-copy">Please wait while we gather the requested information.</p>
                </div>
            `.trim(),
        });
    }

    hideDrilldownLoading() {
        closeDrillDownModal();
        return;
        const loadingOverlay = document.getElementById("graduation-drilldown-loading-modal");
        if (loadingOverlay) {
            loadingOverlay.remove();
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    window.graduationAnalysis = new GraduationAnalysis();
}, { passive: true });
