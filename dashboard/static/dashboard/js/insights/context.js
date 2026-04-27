import { parseJsonScript } from "./shared.js?v=20260412-insights-shell01";

const isTrustedAiNarrativeSource = (source) => ["openai", "google"].includes(String(source || "").trim().toLowerCase());

export const createInsightContext = (payload = {}) => {
    const chartPayload = payload.chartPayload || {};
    const cardNarratives = payload.cardNarratives || parseJsonScript("insight-card-narratives", {});
    const overviewNarrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();
    const root = document.querySelector(".insight-layout");

    return {
        config: {
            payloadUrl: root?.dataset?.payloadUrl,
            drilldownUrl: root?.dataset?.drilldownUrl,
        },
        data: {
            distributionRows: chartPayload.distributionRows || parseJsonScript("insight-distribution-data", []),
            facultyLoadRows: chartPayload.facultyLoadRows || parseJsonScript("insight-faculty-load-data", []),
            facultyPressureRows: chartPayload.facultyPressureRows || parseJsonScript("insight-faculty-pressure-data", []),
            driverRows: chartPayload.driverRows || parseJsonScript("insight-driver-data", []),
            cardNarratives,
        },
        flags: {
            overviewNarrativeSource,
            overviewNarrativesAreAi: isTrustedAiNarrativeSource(overviewNarrativeSource),
        },
        elements: {
            root,
            storyBanner: document.getElementById("insight-story-banner"),
            distributionCopy: document.getElementById("insight-distribution-copy"),
            distributionHints: document.getElementById("insight-distribution-hints"),
            distributionNote: document.getElementById("insight-distribution-note"),
            facultyLoadCopy: document.getElementById("insight-faculty-load-copy"),
            facultyLoadHints: document.getElementById("insight-faculty-load-hints"),
            facultyLoadNote: document.getElementById("insight-faculty-load-note"),
            facultyPressureCopy: document.getElementById("insight-faculty-pressure-copy"),
            facultyPressureHints: document.getElementById("insight-faculty-pressure-hints"),
            facultyPressureNote: document.getElementById("insight-faculty-pressure-note"),
            driversCopy: document.getElementById("insight-drivers-copy"),
            driversHints: document.getElementById("insight-drivers-hints"),
            driversNote: document.getElementById("insight-drivers-note"),
            fullscreenButtons: Array.from(document.querySelectorAll("[data-chart-fullscreen-toggle]")),
            metricValues: Array.from(document.querySelectorAll("[data-metric-value]")),
            recommendationList: document.querySelector(".insight-recommendation-list"),
            confidenceList: document.querySelector(".insight-confidence-list"),
            flaggedCopy: document.getElementById("insight-flagged-copy"),
            flaggedList: document.querySelector(".insight-flagged-list"),
        },
    };
};

export const updateInsightContext = (context, payload = {}) => {
    const chartPayload = payload.chartPayload || {};
    const cardNarratives = Object.prototype.hasOwnProperty.call(payload, "cardNarratives")
        ? (payload.cardNarratives || {})
        : context.data.cardNarratives;

    context.data.distributionRows = chartPayload.distributionRows || context.data.distributionRows;
    context.data.facultyLoadRows = chartPayload.facultyLoadRows || context.data.facultyLoadRows;
    context.data.facultyPressureRows = chartPayload.facultyPressureRows || context.data.facultyPressureRows;
    context.data.driverRows = chartPayload.driverRows || context.data.driverRows;
    context.data.cardNarratives = cardNarratives;

    const overviewNarrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();
    context.flags.overviewNarrativeSource = overviewNarrativeSource;
    context.flags.overviewNarrativesAreAi = isTrustedAiNarrativeSource(overviewNarrativeSource);

    return context;
};
