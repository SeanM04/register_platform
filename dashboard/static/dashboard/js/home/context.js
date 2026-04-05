import { parseJsonScript } from "./shared.js?v=20260403-home-story04";

export const createHomeContext = () => {
    const cardNarratives = parseJsonScript("home-card-narratives", {});
    const overviewNarrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();

    return {
        data: {
            outcomeRows: parseJsonScript("home-outcome-data", []),
            riskDistributionRows: parseJsonScript("home-risk-distribution-data", []),
            facultyLoadRows: parseJsonScript("home-faculty-load-data", []),
            progressRows: parseJsonScript("home-progress-data", []),
            cardNarratives,
        },
        flags: {
            overviewNarrativeSource,
            overviewNarrativesAreAi: Boolean(overviewNarrativeSource && overviewNarrativeSource !== "rules"),
        },
        elements: {
            storyBanner: document.getElementById("home-story-banner"),
            outcomesChart: document.getElementById("home-outcomes-chart"),
            outcomesCopy: document.getElementById("home-outcomes-copy"),
            outcomesHints: document.getElementById("home-outcomes-hints"),
            outcomesNote: document.getElementById("home-outcomes-note"),
            riskChart: document.getElementById("home-risk-chart"),
            riskCopy: document.getElementById("home-risk-copy"),
            riskHints: document.getElementById("home-risk-hints"),
            riskNote: document.getElementById("home-risk-note"),
            facultyChart: document.getElementById("home-faculty-chart"),
            facultyCopy: document.getElementById("home-faculty-copy"),
            facultyHints: document.getElementById("home-faculty-hints"),
            facultyNote: document.getElementById("home-faculty-note"),
            progressChart: document.getElementById("home-progress-chart"),
            progressCopy: document.getElementById("home-progress-copy"),
            progressHints: document.getElementById("home-progress-hints"),
            progressNote: document.getElementById("home-progress-note"),
            fullscreenButtons: Array.from(document.querySelectorAll("[data-chart-fullscreen-toggle]")),
        },
    };
};
