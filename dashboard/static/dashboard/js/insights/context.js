import { parseJsonScript } from "./shared.js?v=20260403-insights-story02";

export const createInsightContext = () => {
    const cardNarratives = parseJsonScript("insight-card-narratives", {});
    const overviewNarrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();

    return {
        data: {
            distributionRows: parseJsonScript("insight-distribution-data", []),
            facultyLoadRows: parseJsonScript("insight-faculty-load-data", []),
            facultyPressureRows: parseJsonScript("insight-faculty-pressure-data", []),
            driverRows: parseJsonScript("insight-driver-data", []),
            cardNarratives,
        },
        flags: {
            overviewNarrativeSource,
            overviewNarrativesAreAi: Boolean(overviewNarrativeSource && overviewNarrativeSource !== "rules"),
        },
        elements: {
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
        },
    };
};
