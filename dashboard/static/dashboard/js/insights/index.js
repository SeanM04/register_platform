import { createInsightContext, updateInsightContext } from "./context.js?v=20260420-kpi-note-fix01";
import { initialiseDistributionSection } from "./distribution.js?v=20260403-insights-story02";
import { initialiseDriversSection } from "./drivers.js?v=20260403-insights-story02";
import { initialiseFacultyLoadSection } from "./faculty_load.js?v=20260403-insights-story02";
import { initialiseFacultyPressureSection } from "./faculty_pressure.js?v=20260403-insights-story02";
import { initialiseFullscreenControls } from "./fullscreen.js?v=20260403-insights-story02";
import { renderStoryBanner } from "./narratives.js?v=20260403-insights-story02";
import { escapeTooltipHtml } from "./shared.js?v=20260412-insights-shell01";

const buildRequestUrl = (endpoint) => {
    const requestUrl = new URL(endpoint, window.location.origin);
    const currentUrl = new URL(window.location.href);

    currentUrl.searchParams.forEach((value, key) => {
        requestUrl.searchParams.set(key, value);
    });

    return requestUrl;
};

const fetchJson = async (endpoint) => {
    if (!endpoint) {
        return null;
    }

    const response = await fetch(buildRequestUrl(endpoint), {
        credentials: "same-origin",
        headers: {
            "X-Requested-With": "XMLHttpRequest",
        },
    });

    if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
    }

    return response.json();
};

const FLAGGED_STUDENTS_PAGE_SIZE = 10;

const initialiseChartResizeHandling = (controllers, resizeCharts) => {
    const charts = controllers
        .map((controller) => controller.getChart())
        .filter(Boolean);

    if (!charts.length) {
        return;
    }

    window.addEventListener("resize", resizeCharts);

    if (!window.ResizeObserver) {
        return;
    }

    const observer = new ResizeObserver(() => {
        resizeCharts();
    });

    charts.forEach((chart) => {
        observer.observe(chart.getDom());
    });
};

const hydrateSummaryCards = (context, summaryCards = []) => {
    context.elements.metricValues.forEach((element) => {
        const metricIndex = Number(element.dataset.metricIndex);
        const card = Number.isNaN(metricIndex) ? null : summaryCards[metricIndex];
        if (!card) {
            return;
        }

        element.textContent = card.value;
    });

    context.elements.metricNotes.forEach((element) => {
        const metricIndex = Number(element.dataset.metricIndex);
        const card = Number.isNaN(metricIndex) ? null : summaryCards[metricIndex];
        if (!card || typeof card.note === "undefined") {
            return;
        }

        element.textContent = card.note;
    });
};

const renderRecommendations = (container, recommendations = []) => {
    if (!container) {
        return;
    }

    if (!recommendations.length) {
        container.innerHTML = `<div class="insight-empty-state">No operational recommendations are available for the selected scope.</div>`;
        return;
    }

    container.innerHTML = recommendations.map((recommendation) => `
        <article class="insight-recommendation-card">
            <div class="insight-recommendation-head">
                <h3>${escapeTooltipHtml(recommendation.title)}</h3>
                <span class="insight-priority insight-priority-${escapeTooltipHtml(recommendation.priority_key)}">${escapeTooltipHtml(recommendation.priority)}</span>
            </div>
            <p class="insight-recommendation-copy">${escapeTooltipHtml(recommendation.description)}</p>
            <a class="insight-recommendation-action" href="${escapeTooltipHtml(recommendation.action_url)}">${escapeTooltipHtml(recommendation.action_label)}</a>
        </article>
    `).join("").trim();
};

const renderConfidenceRows = (container, rows = []) => {
    if (!container) {
        return;
    }

    if (!rows.length) {
        container.innerHTML = `<div class="insight-empty-state">No confidence signals are available for the selected scope.</div>`;
        return;
    }

    container.innerHTML = rows.map((row) => `
        <div class="insight-confidence-row">
            <div class="insight-confidence-meta">
                <span class="insight-confidence-label">${escapeTooltipHtml(row.label)}</span>
                <span class="insight-confidence-value">${escapeTooltipHtml(row.value)}%</span>
            </div>
            <div class="insight-confidence-track">
                <span class="insight-confidence-fill" style="width: ${escapeTooltipHtml(row.value)}%"></span>
            </div>
        </div>
    `).join("").trim();
};

const renderFlaggedStudents = (context, flaggedStudents = [], flaggedTotal = 0, page = 1) => {
    const { flaggedCopy, flaggedList, root } = context.elements;
    const pagination = document.getElementById("insight-flagged-pagination");
    const resultsMeta = document.getElementById("insight-flagged-results");
    if (!flaggedList) {
        return;
    }

    if (flaggedCopy) {
        flaggedCopy.textContent = flaggedTotal
            ? `${flaggedTotal} students currently need closer academic attention in the visible scope.`
            : "No students currently need closer academic attention in the visible scope.";
    }

    const totalPages = Math.max(1, Math.ceil(flaggedStudents.length / FLAGGED_STUDENTS_PAGE_SIZE));
    const currentPage = Math.min(Math.max(Number(page) || 1, 1), totalPages);
    const startIndex = (currentPage - 1) * FLAGGED_STUDENTS_PAGE_SIZE;
    const paginatedStudents = flaggedStudents.slice(startIndex, startIndex + FLAGGED_STUDENTS_PAGE_SIZE);

    if (!flaggedStudents.length) {
        flaggedList.innerHTML = `<div class="insight-empty-state">No students are currently flagged in the selected insight scope.</div>`;
        if (resultsMeta) {
            resultsMeta.textContent = "No students currently need closer academic attention.";
        }
        if (pagination) {
            pagination.innerHTML = "";
        }
        return;
    }

    const studentDetailPrefix = root?.dataset.studentDetailPrefix || "/students/";
    flaggedList.innerHTML = paginatedStudents.map((student) => `
        <a class="insight-flagged-item" href="${escapeTooltipHtml(`${studentDetailPrefix}${encodeURIComponent(student.detail_slug)}/`)}">
            <span class="insight-flagged-body">
                <span class="insight-flagged-name">${escapeTooltipHtml(student.name)}</span>
                <span class="insight-flagged-meta">${escapeTooltipHtml(student.meta)}</span>
            </span>
            <span class="insight-risk-badge insight-risk-badge-${escapeTooltipHtml(student.risk_key)}">${escapeTooltipHtml(student.risk_level)}</span>
        </a>
    `).join("").trim();

    if (resultsMeta) {
        const visibleStart = startIndex + 1;
        const visibleEnd = Math.min(startIndex + FLAGGED_STUDENTS_PAGE_SIZE, flaggedStudents.length);
        resultsMeta.textContent = `Showing ${visibleStart}-${visibleEnd} of ${flaggedStudents.length} students`;
    }

    if (pagination) {
        const previousDisabled = currentPage <= 1 ? "disabled" : "";
        const nextDisabled = currentPage >= totalPages ? "disabled" : "";
        pagination.innerHTML = `
            <button class="insight-flagged-pagination-button" type="button" data-flagged-page="${currentPage - 1}" ${previousDisabled}>Prev</button>
            <span class="insight-flagged-pagination-info">Page ${currentPage} of ${totalPages}</span>
            <button class="insight-flagged-pagination-button" type="button" data-flagged-page="${currentPage + 1}" ${nextDisabled}>Next</button>
        `.trim();

        pagination.querySelectorAll("[data-flagged-page]").forEach((button) => {
            button.addEventListener("click", () => {
                const nextPage = Number(button.dataset.flaggedPage);
                if (!Number.isNaN(nextPage)) {
                    renderFlaggedStudents(context, flaggedStudents, flaggedTotal, nextPage);
                }
            });
        });
    }
};

const setInsightShellErrorState = (context) => {
    if (context.elements.storyBanner) {
        context.elements.storyBanner.innerHTML = `
            <div class="insight-story-main">
                <p class="insight-story-kicker">Primary Takeaway</p>
                <h2 class="insight-story-title">the page shell loaded, but the institutional insights dataset could not be retrieved.</h2>
                <p class="insight-story-copy">Refresh the page to retry the institutional insights payload.</p>
            </div>
        `.trim();
    }
};

export const initialiseInsightsPage = async () => {
    const shellContext = createInsightContext();
    const { elements } = shellContext;
    const payloadUrl = elements.root?.dataset.payloadUrl;

    if (!payloadUrl) {
        setInsightShellErrorState(shellContext);
        return;
    }

    let payloadResponse = null;
    try {
        payloadResponse = await fetchJson(payloadUrl);
    } catch (error) {
        setInsightShellErrorState(shellContext);
        return;
    }

    const context = updateInsightContext(shellContext, {
        chartPayload: {
            distributionRows: payloadResponse?.risk_distribution_rows || [],
            facultyLoadRows: payloadResponse?.faculty_load_rows || [],
            facultyPressureRows: payloadResponse?.faculty_pressure_rows || [],
            driverRows: payloadResponse?.driver_rows || [],
        },
        cardNarratives: payloadResponse?.insight_card_narratives || {},
    });
    const { data, elements: hydratedElements } = context;

    hydrateSummaryCards(context, payloadResponse?.summary_cards || []);
    renderRecommendations(hydratedElements.recommendationList, payloadResponse?.recommendations || []);
    renderConfidenceRows(hydratedElements.confidenceList, payloadResponse?.confidence_rows || []);
    renderFlaggedStudents(context, payloadResponse?.flagged_students || [], payloadResponse?.flagged_total || 0);

    renderStoryBanner(
        hydratedElements.storyBanner,
        data.distributionRows,
        data.facultyLoadRows,
        data.facultyPressureRows,
        data.driverRows,
    );

    const controllers = [
        initialiseDistributionSection(context),
        initialiseFacultyLoadSection(context),
        initialiseFacultyPressureSection(context),
        initialiseDriversSection(context),
    ];
    const resizeCharts = () => {
        controllers.forEach((controller) => {
            controller.resize();
        });
    };

    initialiseChartResizeHandling(controllers, resizeCharts);
    initialiseFullscreenControls(hydratedElements.fullscreenButtons, resizeCharts);
};
