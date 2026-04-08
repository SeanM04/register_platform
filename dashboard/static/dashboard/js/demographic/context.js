import { parseJsonScript } from "./shared.js";

export const createDemographicContext = (payload = {}) => {
    const chartPayload = payload.chartPayload || {};
    const cardNarratives = payload.cardNarratives || parseJsonScript("demographic-card-narratives", {});
    const overviewNarrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();

    return {
        data: {
            genderRows: chartPayload.genderRows || parseJsonScript("demographic-gender-data", []),
            locationRows: chartPayload.locationRows || parseJsonScript("demographic-location-data", []),
            locationMixRows: chartPayload.locationMixRows || parseJsonScript("demographic-location-mix-data", []),
            locationMapRows: chartPayload.locationMapRows || parseJsonScript("demographic-location-map-data", []),
            locationMapMeta: chartPayload.locationMapMeta || parseJsonScript("demographic-location-map-meta-data", {}),
            programmeRows: chartPayload.programmeRows || parseJsonScript("demographic-programme-data", []),
            cardNarratives,
        },
        flags: {
            overviewNarrativeSource,
            overviewNarrativesAreAi: Boolean(overviewNarrativeSource && overviewNarrativeSource !== "rules"),
        },
        elements: {
            storyBanner: document.getElementById("demographic-story-banner"),
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
            fullscreenButtons: Array.from(document.querySelectorAll("[data-chart-fullscreen-toggle]")),
            metricValues: Array.from(document.querySelectorAll("[data-metric-value]")),
        },
    };
};

export const updateDemographicContext = (context, payload = {}) => {
    const chartPayload = payload.chartPayload || {};
    const cardNarratives = payload.cardNarratives || {};

    context.data.genderRows = chartPayload.genderRows || context.data.genderRows;
    context.data.locationRows = chartPayload.locationRows || context.data.locationRows;
    context.data.locationMixRows = chartPayload.locationMixRows || context.data.locationMixRows;
    context.data.locationMapRows = chartPayload.locationMapRows || context.data.locationMapRows;
    context.data.locationMapMeta = chartPayload.locationMapMeta || context.data.locationMapMeta;
    context.data.programmeRows = chartPayload.programmeRows || context.data.programmeRows;
    context.data.cardNarratives = cardNarratives;

    const overviewNarrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();
    context.flags.overviewNarrativeSource = overviewNarrativeSource;
    context.flags.overviewNarrativesAreAi = Boolean(overviewNarrativeSource && overviewNarrativeSource !== "rules");

    return context;
};
