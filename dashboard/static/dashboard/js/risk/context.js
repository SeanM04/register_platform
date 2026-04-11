import { parseJsonScript } from "./shared.js";

const isTrustedAiNarrativeSource = (source) => ["openai", "google"].includes(String(source || "").trim().toLowerCase());

export const createRiskContext = () => {
    const cardNarratives = parseJsonScript("risk-card-narratives", {});
    const overviewNarrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();

    return {
        data: {
            distributionRows: parseJsonScript("risk-distribution-data", []),
            driverRows: parseJsonScript("risk-driver-data", []),
            levelRows: parseJsonScript("risk-level-data", []),
            programmeRows: parseJsonScript("risk-programme-data", []),
            cardNarratives,
        },
        flags: {
            overviewNarrativeSource,
            overviewNarrativesAreAi: isTrustedAiNarrativeSource(overviewNarrativeSource),
        },
        elements: {
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
        },
    };
};
