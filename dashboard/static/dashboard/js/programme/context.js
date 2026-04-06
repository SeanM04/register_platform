import { parseJsonScript } from "./shared.js?v=20260405-programmes-progressive01";

const normalizeNarrativeFlags = (cardNarratives) => {
    const narrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();

    return {
        narrativeSource,
        narrativesAreAi: Boolean(narrativeSource && narrativeSource !== "rules"),
    };
};

export const createProgrammeContext = (payload = {}) => {
    const chartPayload = payload.chartPayload || {};
    const cardNarratives = payload.cardNarratives || parseJsonScript("programme-card-narratives", {});

    return {
        data: {
            topLoadRows: chartPayload.topLoadRows || parseJsonScript("programme-top-load-data", []),
            departmentRows: chartPayload.departmentRows || parseJsonScript("programme-department-data", []),
            lowPassRows: chartPayload.lowPassRows || parseJsonScript("programme-low-pass-data", []),
            performanceRows: chartPayload.performanceRows || parseJsonScript("programme-performance-data", []),
            programmeRows: chartPayload.programmeRows || [],
            registerMeta: chartPayload.registerMeta || {},
            cardNarratives,
        },
        flags: normalizeNarrativeFlags(cardNarratives),
        elements: {
            root: document.querySelector(".programme-dashboard"),
            storyBanner: document.getElementById("programme-story-banner"),
            metricCards: Array.from(document.querySelectorAll("[data-metric-card]")),
            metricNotes: Array.from(document.querySelectorAll("[data-metric-note]")),
            metricValues: Array.from(document.querySelectorAll("[data-metric-value]")),
            loadChart: document.getElementById("programme-load-chart"),
            loadCopy: document.getElementById("programme-load-copy"),
            loadHints: document.getElementById("programme-load-hints"),
            loadNote: document.getElementById("programme-load-note"),
            departmentsChart: document.getElementById("programme-departments-chart"),
            departmentsCopy: document.getElementById("programme-departments-copy"),
            departmentsHints: document.getElementById("programme-departments-hints"),
            departmentsNote: document.getElementById("programme-departments-note"),
            qualityChart: document.getElementById("programme-quality-chart"),
            qualityCopy: document.getElementById("programme-quality-copy"),
            qualityHints: document.getElementById("programme-quality-hints"),
            qualityNote: document.getElementById("programme-quality-note"),
            performanceChart: document.getElementById("programme-performance-chart"),
            performanceCopy: document.getElementById("programme-performance-copy"),
            performanceHints: document.getElementById("programme-performance-hints"),
            performanceNote: document.getElementById("programme-performance-note"),
            searchForm: document.querySelector(".programme-toolbar"),
            searchInput: document.querySelector(".programme-search"),
            registerBody: document.getElementById("programme-register-body"),
            registerMeta: document.getElementById("programme-register-meta"),
            fullscreenButtons: Array.from(document.querySelectorAll("[data-chart-fullscreen-toggle]")),
        },
    };
};

export const updateProgrammeNarrativeContext = (context, cardNarratives = {}) => {
    context.data.cardNarratives = cardNarratives;
    context.flags = normalizeNarrativeFlags(cardNarratives);
    return context;
};
