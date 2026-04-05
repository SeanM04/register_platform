import { parseJsonScript } from "./shared.js";

export const createAcademicLevelContext = () => {
    const levelRows = parseJsonScript("academic-level-level-data", []);
    const genderRows = parseJsonScript("academic-level-gender-data", []);
    const programmeRows = parseJsonScript("academic-level-programme-data", []);
    const cardNarratives = parseJsonScript("academic-level-card-narratives", {});
    const overviewNarrativeSource = String(cardNarratives?.source || "rules").trim().toLowerCase();
    const overviewNarrativesAreAi = Boolean(overviewNarrativeSource && overviewNarrativeSource !== "rules");
    const topProgrammeRows = [...programmeRows]
        .sort((left, right) => right.registrations - left.registrations || left.programme.localeCompare(right.programme))
        .slice(0, 5);

    return {
        data: {
            levelRows,
            genderRows,
            programmeRows,
            cardNarratives,
            topProgrammeRows,
        },
        flags: {
            overviewNarrativeSource,
            overviewNarrativesAreAi,
        },
        elements: {
            levelSearchForm: document.querySelector(".level-toolbar"),
            levelSearchInput: document.querySelector(".level-search"),
            storyBanner: document.getElementById("academic-level-story-banner"),
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
            passTrendCard: document.getElementById("academic-level-pass-chart")?.closest(".level-insight-card"),
            topProgrammeCard: document.getElementById("academic-level-programme-top-chart")?.closest(".level-insight-card"),
            levelTableWrap: document.querySelector("[data-scroll-region]"),
            levelTableRows: Array.from(document.querySelectorAll("[data-level-row]")),
        },
    };
};
