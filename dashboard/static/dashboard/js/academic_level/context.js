import { parseJsonScript } from "./shared.js";

const isTrustedAiNarrativeSource = (source) => ["openai", "google"].includes(String(source || "").trim().toLowerCase());

export const createAcademicLevelContext = (payload = {}) => {
    const chartPayload = payload.chartPayload || {};
    const cardNarratives = payload.cardNarratives || parseJsonScript("academic-level-card-narratives", {});
    const narrativeDiagnostics = payload.narrativeDiagnostics || parseJsonScript("academic-level-narrative-diagnostics", {});
    const levelRows = chartPayload.levelRows || parseJsonScript("academic-level-level-data", []);
    const genderRows = chartPayload.genderRows || parseJsonScript("academic-level-gender-data", []);
    const programmeRows = chartPayload.programmeRows || parseJsonScript("academic-level-programme-data", []);
    const overviewNarrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();
    const overviewNarrativesAreAi = isTrustedAiNarrativeSource(overviewNarrativeSource);
    const topProgrammeRows = [...programmeRows]
        .sort((left, right) => right.registrations - left.registrations || left.programme.localeCompare(right.programme))
        .slice(0, Math.min(5, programmeRows.length));

    const levelTableBody = document.querySelector(".level-table tbody");

    return {
        data: {
            levelRows,
            genderRows,
            programmeRows,
            cardNarratives,
            narrativeDiagnostics,
            topProgrammeRows,
        },
        flags: {
            overviewNarrativeSource,
            overviewNarrativesAreAi,
        },
        elements: {
            root: document.querySelector(".level-layout"),
            levelSearchForm: document.querySelector(".level-toolbar"),
            levelSearchInput: document.querySelector(".level-search"),
            storyBanner: document.getElementById("academic-level-story-banner"),
            narrativeStatus: document.getElementById("academic-level-narrative-status"),
            metricNotes: Array.from(document.querySelectorAll("[data-metric-note]")),
            metricValues: Array.from(document.querySelectorAll("[data-metric-value]")),
            genderCopy: document.getElementById("academic-level-gender-copy"),
            genderNote: document.getElementById("academic-level-gender-note"),
            genderHints: document.getElementById("academic-level-gender-hints"),
            topProgrammeCopy: document.getElementById("academic-level-programme-top-copy"),
            topProgrammeHints: document.getElementById("academic-level-programme-top-hints"),
            passTrendCopy: document.getElementById("academic-level-pass-copy"),
            passTrendHints: document.getElementById("academic-level-pass-hints"),
            passTrendStatus: document.getElementById("academic-level-pass-status"),
            passTrendReset: document.getElementById("academic-level-pass-reset"),
            passTrendJump: document.getElementById("academic-level-pass-jump"),
            passTrendContext: document.getElementById("academic-level-pass-context"),
            passTrendTitle: document.getElementById("academic-level-pass-title"),
            passLegendButtons: Array.from(document.querySelectorAll("[data-pass-series]")),
            programmeTopStatus: document.getElementById("academic-level-programme-top-status"),
            programmeTopReset: document.getElementById("academic-level-programme-top-reset"),
            programmeTopContext: document.getElementById("academic-level-programme-top-context"),
            programmeTopTitle: document.getElementById("academic-level-programme-top-title"),
            fullscreenButtons: Array.from(document.querySelectorAll("[data-chart-fullscreen-toggle]")),
            passTrendCard: document.getElementById("academic-level-pass-chart")?.closest(".demographic-accordion-item"),
            topProgrammeCard: document.getElementById("academic-level-programme-top-chart")?.closest(".demographic-accordion-item"),
            levelTableWrap: document.querySelector("[data-scroll-region]"),
            levelTableBody: levelTableBody,
            levelTableRows: Array.from(document.querySelectorAll("[data-level-row]")),
        },
        config: {
            drilldownUrl: document.querySelector(".level-layout")?.dataset.drilldownUrl || "",
        },
    };
};

export const updateAcademicLevelContext = (context, payload = {}) => {
    const chartPayload = payload.chartPayload || {};
    const cardNarratives = Object.prototype.hasOwnProperty.call(payload, "cardNarratives")
        ? (payload.cardNarratives || {})
        : context.data.cardNarratives;
    const narrativeDiagnostics = Object.prototype.hasOwnProperty.call(payload, "narrativeDiagnostics")
        ? (payload.narrativeDiagnostics || {})
        : context.data.narrativeDiagnostics;

    context.data.levelRows = chartPayload.levelRows || context.data.levelRows;
    context.data.genderRows = chartPayload.genderRows || context.data.genderRows;
    context.data.programmeRows = chartPayload.programmeRows || context.data.programmeRows;
    context.data.cardNarratives = cardNarratives;
    context.data.narrativeDiagnostics = narrativeDiagnostics;
    context.data.topProgrammeRows = [...context.data.programmeRows]
        .sort((left, right) => right.registrations - left.registrations || left.programme.localeCompare(right.programme))
        .slice(0, Math.min(5, context.data.programmeRows.length));

    const overviewNarrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();
    context.flags.overviewNarrativeSource = overviewNarrativeSource;
    context.flags.overviewNarrativesAreAi = isTrustedAiNarrativeSource(overviewNarrativeSource);

    return context;
};

/** Re-query table row nodes after tbody is re-rendered (pass trend uses these for highlight / jump). */
export const refreshAcademicLevelTableDomRefs = (context) => {
    if (!context?.elements) {
        return;
    }
    context.elements.levelTableBody = document.querySelector(".level-table tbody");
    context.elements.levelTableRows = Array.from(document.querySelectorAll("[data-level-row]"));
    context.elements.levelTableWrap = document.querySelector("[data-scroll-region]");
};
