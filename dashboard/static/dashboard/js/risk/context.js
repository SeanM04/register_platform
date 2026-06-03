import { parseJsonScript } from "./shared.js";

const isTrustedAiNarrativeSource = (source) => ["openai", "google"].includes(String(source || "").trim().toLowerCase());

export const createRiskContext = (payload = {}) => {
    const chartPayload = payload.chartPayload || {};
    const cardNarratives = payload.cardNarratives || parseJsonScript("risk-card-narratives", {});
    const overviewNarrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();

    return {
        config: {
            drilldownUrl: document.querySelector(".risk-layout")?.dataset.drilldownUrl || "",
        },
        data: {
            distributionRows: chartPayload.distributionRows || parseJsonScript("risk-distribution-data", []),
            driverRows: chartPayload.driverRows || parseJsonScript("risk-driver-data", []),
            levelRows: chartPayload.levelRows || parseJsonScript("risk-level-data", []),
            programmeRows: chartPayload.programmeRows || parseJsonScript("risk-programme-data", []),
            cardNarratives,
        },
        flags: {
            overviewNarrativeSource,
            overviewNarrativesAreAi: isTrustedAiNarrativeSource(overviewNarrativeSource),
        },
        elements: {
            root: document.querySelector(".risk-layout"),
            storyBanner: document.getElementById("risk-story-banner"),
            distributionCopy: document.getElementById("risk-distribution-copy"),
            distributionHints: document.getElementById("risk-distribution-hints"),
            distributionNote: document.getElementById("risk-distribution-note"),
            driversCopy: document.getElementById("risk-drivers-copy"),
            driversHints: document.getElementById("risk-drivers-hints"),
            driversNote: document.getElementById("risk-drivers-note"),
            levelsCopy: document.getElementById("risk-levels-copy"),
            levelsHints: document.getElementById("risk-levels-hints"),
            levelsNote: document.getElementById("risk-levels-note"),
            programmesCopy: document.getElementById("risk-programmes-copy"),
            programmesHints: document.getElementById("risk-programmes-hints"),
            programmesNote: document.getElementById("risk-programmes-note"),
            fullscreenButtons: Array.from(document.querySelectorAll("[data-chart-fullscreen-toggle]")),
            searchForm: document.querySelector(".risk-toolbar"),
            searchInput: document.querySelector(".risk-search"),
            metricNotes: Array.from(document.querySelectorAll("[data-metric-note]")),
            metricValues: Array.from(document.querySelectorAll("[data-metric-value]")),
            registerBody: document.getElementById("risk-register-body"),
            resultsMeta: document.getElementById("risk-results-meta"),
            pagination: document.getElementById("risk-pagination"),
        },
    };
};

export const updateRiskContext = (context, payload = {}) => {
    const chartPayload = payload.chartPayload || {};
    const cardNarratives = Object.prototype.hasOwnProperty.call(payload, "cardNarratives")
        ? (payload.cardNarratives || {})
        : context.data.cardNarratives;

    context.data.distributionRows = chartPayload.distributionRows || context.data.distributionRows;
    context.data.driverRows = chartPayload.driverRows || context.data.driverRows;
    context.data.levelRows = chartPayload.levelRows || context.data.levelRows;
    context.data.programmeRows = chartPayload.programmeRows || context.data.programmeRows;
    context.data.cardNarratives = cardNarratives;

    const overviewNarrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();
    context.flags.overviewNarrativeSource = overviewNarrativeSource;
    context.flags.overviewNarrativesAreAi = isTrustedAiNarrativeSource(overviewNarrativeSource);

    return context;
};
