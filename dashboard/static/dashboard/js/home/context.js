const homeRoot = document.querySelector(".home-layout");

/**
 * Capture the home dashboard's shared data, flags, and DOM references in one place.
 */
export const createHomeContext = (payload = {}) => {
    const chartPayload = payload.chartPayload || {};
    const cardNarratives = payload.cardNarratives || {};
    const actionCards = payload.actionCards || [];
    const aiNarrativesEnabled = homeRoot?.dataset.aiNarrativesEnabled === "true";
    const overviewNarrativeFetchCompleted = payload.narrativeFetchCompleted ?? (Boolean(cardNarratives?.source) || !aiNarrativesEnabled);
    const overviewNarrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();

    return {
        data: {
            outcomeRows: chartPayload.outcomeRows || [],
            riskDistributionRows: chartPayload.riskDistributionRows || [],
            facultyLoadRows: chartPayload.facultyLoadRows || [],
            progressRows: chartPayload.progressRows || [],
            cardNarratives,
            actionCards,
        },
        flags: {
            aiNarrativesEnabled,
            overviewNarrativeFetchCompleted,
            overviewNarrativesPending: aiNarrativesEnabled && !overviewNarrativeFetchCompleted,
            overviewNarrativeSource,
            overviewNarrativesAreAi: Boolean(overviewNarrativeSource && overviewNarrativeSource !== "rules"),
        },
        elements: {
            storyBanner: document.getElementById("home-story-banner"),
            chapterOneSummary: document.getElementById("home-chapter-one-summary"),
            chapterTwoSummary: document.getElementById("home-chapter-two-summary"),
            outcomesChart: document.getElementById("home-outcomes-chart"),
            outcomesAiState: document.getElementById("home-outcomes-ai-state"),
            outcomesCopy: document.getElementById("home-outcomes-copy"),
            outcomesHints: document.getElementById("home-outcomes-hints"),
            outcomesNote: document.getElementById("home-outcomes-note"),
            riskChart: document.getElementById("home-risk-chart"),
            riskAiState: document.getElementById("home-risk-ai-state"),
            riskCopy: document.getElementById("home-risk-copy"),
            riskHints: document.getElementById("home-risk-hints"),
            riskNote: document.getElementById("home-risk-note"),
            facultyChart: document.getElementById("home-faculty-chart"),
            facultyAiState: document.getElementById("home-faculty-ai-state"),
            facultyCopy: document.getElementById("home-faculty-copy"),
            facultyHints: document.getElementById("home-faculty-hints"),
            facultyNote: document.getElementById("home-faculty-note"),
            progressChart: document.getElementById("home-progress-chart"),
            progressAiState: document.getElementById("home-progress-ai-state"),
            progressCopy: document.getElementById("home-progress-copy"),
            progressHints: document.getElementById("home-progress-hints"),
            progressNote: document.getElementById("home-progress-note"),
            fullscreenButtons: Array.from(document.querySelectorAll("[data-chart-fullscreen-toggle]")),
            metricCards: Array.from(document.querySelectorAll("[data-metric-card]")),
            metricValues: Array.from(document.querySelectorAll("[data-metric-value]")),
            metricNotes: Array.from(document.querySelectorAll("[data-metric-note]")),
            actionGrid: document.getElementById("home-action-grid"),
        },
    };
};

/**
 * Merge newly fetched dashboard data into the existing context without rebuilding it.
 */
export const updateHomeContext = (context, payload = {}) => {
    const chartPayload = payload.chartPayload || {};
    const hasCardNarratives = Object.prototype.hasOwnProperty.call(payload, "cardNarratives");
    const cardNarratives = hasCardNarratives ? (payload.cardNarratives || {}) : context.data.cardNarratives;
    const overviewNarrativeFetchCompleted = payload.narrativeFetchCompleted ?? context.flags.overviewNarrativeFetchCompleted;

    context.data.outcomeRows = chartPayload.outcomeRows || context.data.outcomeRows;
    context.data.riskDistributionRows = chartPayload.riskDistributionRows || context.data.riskDistributionRows;
    context.data.facultyLoadRows = chartPayload.facultyLoadRows || context.data.facultyLoadRows;
    context.data.progressRows = chartPayload.progressRows || context.data.progressRows;
    context.data.cardNarratives = cardNarratives;
    context.data.actionCards = payload.actionCards || context.data.actionCards;

    const overviewNarrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();
    context.flags.overviewNarrativeFetchCompleted = overviewNarrativeFetchCompleted;
    context.flags.overviewNarrativesPending = context.flags.aiNarrativesEnabled && !overviewNarrativeFetchCompleted;
    context.flags.overviewNarrativeSource = overviewNarrativeSource;
    context.flags.overviewNarrativesAreAi = Boolean(overviewNarrativeSource && overviewNarrativeSource !== "rules");

    return context;
};
