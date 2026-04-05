import { parseJsonScript } from "./shared.js?v=20260404-programmes-story01";

export const createProgrammeContext = () => {
    const cardNarratives = parseJsonScript("programme-card-narratives", {});
    const narrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();

    return {
        data: {
            topLoadRows: parseJsonScript("programme-top-load-data", []),
            departmentRows: parseJsonScript("programme-department-data", []),
            lowPassRows: parseJsonScript("programme-low-pass-data", []),
            performanceRows: parseJsonScript("programme-performance-data", []),
            cardNarratives,
        },
        flags: {
            narrativeSource,
            narrativesAreAi: Boolean(narrativeSource && narrativeSource !== "rules"),
        },
        elements: {
            storyBanner: document.getElementById("programme-story-banner"),
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
            fullscreenButtons: Array.from(document.querySelectorAll("[data-chart-fullscreen-toggle]")),
        },
    };
};
