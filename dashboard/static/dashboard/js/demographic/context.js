import { parseJsonScript } from "./shared.js";

const isTrustedAiNarrativeSource = (source) => ["openai", "google"].includes(String(source || "").trim().toLowerCase());

export const createDemographicContext = (payload = {}) => {
    const chartPayload = payload.chartPayload || {};
    const cardNarratives = payload.cardNarratives || parseJsonScript("demographic-card-narratives", {});
    const narrativeDiagnostics = payload.narrativeDiagnostics || {};
    const overviewNarrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();

    return {
        config: {
            drilldownUrl: document.querySelector(".demographic-layout")?.dataset.drilldownUrl || "",
        },
        data: {
            genderRows: chartPayload.genderRows || parseJsonScript("demographic-gender-data", []),
            locationRows: chartPayload.locationRows || parseJsonScript("demographic-location-data", []),
            locationMixRows: chartPayload.locationMixRows || parseJsonScript("demographic-location-mix-data", []),
            locationMapRows: chartPayload.locationMapRows || parseJsonScript("demographic-location-map-data", []),
            locationMapMeta: chartPayload.locationMapMeta || parseJsonScript("demographic-location-map-meta-data", {}),
            programmeRows: chartPayload.programmeRows || parseJsonScript("demographic-programme-data", []),
            programmeGenderRows: chartPayload.programmeGenderRows || parseJsonScript("demographic-programme-gender-data", []),
            yearDistributionRows: chartPayload.yearDistributionRows || parseJsonScript("demographic-year-distribution-data", []),
            ageDistributionRows: chartPayload.ageDistributionRows || parseJsonScript("demographic-age-distribution-data", []),
            cardNarratives,
            narrativeDiagnostics,
        },
        flags: {
            overviewNarrativeSource,
            overviewNarrativesAreAi: isTrustedAiNarrativeSource(overviewNarrativeSource),
        },
        elements: {
            root: document.querySelector(".demographic-layout"),
            storyBanner: document.getElementById("demographic-story-banner"),
            narrativeStatus: document.getElementById("demographic-narrative-status"),
            genderCopy: document.getElementById("demographic-gender-copy"),
            genderHints: document.getElementById("demographic-gender-hints"),
            genderNote: document.getElementById("demographic-gender-note"),
            locationCopy: document.getElementById("demographic-location-copy"),
            locationHints: document.getElementById("demographic-location-hints"),
            locationNote: document.getElementById("demographic-location-note"),
            locationReset: document.getElementById("demographic-location-reset"),
            locationMixCopy: document.getElementById("demographic-location-mix-copy"),
            locationMixHints: document.getElementById("demographic-location-mix-hints"),
            locationMixNote: document.getElementById("demographic-location-mix-note"),
            originMapChart: document.getElementById("demographic-origin-map-chart"),
            originMapCopy: document.getElementById("demographic-origin-map-copy"),
            originMapHints: document.getElementById("demographic-origin-map-hints"),
            originMapNote: document.getElementById("demographic-origin-map-note"),
            originMapMeta: document.getElementById("demographic-origin-map-meta"),
            programmeCopy: document.getElementById("demographic-programme-copy"),
            programmeHints: document.getElementById("demographic-programme-hints"),
            programmeNote: document.getElementById("demographic-programme-note"),
            programmeGenderCopy: document.getElementById("demographic-programme-gender-copy"),
            programmeGenderHints: document.getElementById("demographic-programme-gender-hints"),
            programmeGenderNote: document.getElementById("demographic-programme-gender-note"),
            yearDistributionCopy: document.getElementById("demographic-year-distribution-copy"),
            yearDistributionHints: document.getElementById("demographic-year-distribution-hints"),
            yearDistributionNote: document.getElementById("demographic-year-distribution-note"),
            ageDistributionCopy: document.getElementById("demographic-age-distribution-copy"),
            ageDistributionHints: document.getElementById("demographic-age-distribution-hints"),
            ageDistributionNote: document.getElementById("demographic-age-distribution-note"),
            ageDistributionChart: document.getElementById("demographic-age-distribution-chart"),
            genderChart: document.getElementById("demographic-gender-chart"),
            locationChart: document.getElementById("demographic-location-chart"),
            yearDistributionChart: document.getElementById("demographic-year-distribution-chart"),
            programmeChart: document.getElementById("demographic-programme-chart"),
            locationMixChart: document.getElementById("demographic-location-mix-chart"),
            programmeGenderChart: document.getElementById("demographic-programme-gender-chart"),
            fullscreenButtons: Array.from(document.querySelectorAll("[data-chart-fullscreen-toggle]")),
            metricValues: Array.from(document.querySelectorAll("[data-metric-value]")),
        },
    };
};

export const updateDemographicContext = (context, payload = {}) => {
    const chartPayload = payload.chartPayload || {};
    const cardNarratives = Object.prototype.hasOwnProperty.call(payload, "cardNarratives")
        ? (payload.cardNarratives || {})
        : context.data.cardNarratives;
    const narrativeDiagnostics = Object.prototype.hasOwnProperty.call(payload, "narrativeDiagnostics")
        ? (payload.narrativeDiagnostics || {})
        : context.data.narrativeDiagnostics;

    context.data.genderRows = chartPayload.genderRows || context.data.genderRows;
    context.data.locationRows = chartPayload.locationRows || context.data.locationRows;
    context.data.locationMixRows = chartPayload.locationMixRows || context.data.locationMixRows;
    context.data.locationMapRows = chartPayload.locationMapRows || context.data.locationMapRows;
    context.data.locationMapMeta = chartPayload.locationMapMeta || context.data.locationMapMeta;
    context.data.programmeRows = chartPayload.programmeRows || context.data.programmeRows;
    context.data.programmeGenderRows = chartPayload.programmeGenderRows || context.data.programmeGenderRows;
    context.data.yearDistributionRows = chartPayload.yearDistributionRows || context.data.yearDistributionRows;
    context.data.ageDistributionRows = chartPayload.ageDistributionRows || context.data.ageDistributionRows;
    context.data.cardNarratives = cardNarratives;
    context.data.narrativeDiagnostics = narrativeDiagnostics;

    const overviewNarrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();
    context.flags.overviewNarrativeSource = overviewNarrativeSource;
    context.flags.overviewNarrativesAreAi = isTrustedAiNarrativeSource(overviewNarrativeSource);

    return context;
};
