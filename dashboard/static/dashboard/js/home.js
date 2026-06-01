import { initialiseOverviewPage } from "./home/index.js?v=20260601-drilldown-numeric-align01";

let hasInitialised = false;

const MAX_LIBRARY_WAIT_MS = 2200;

/**
 * Resolve once ECharts is on window or the wait budget is exceeded.
 */
const createLibrariesReadyPromise = () =>
    new Promise((resolve) => {
        const startedAt = Date.now();
        const tick = () => {
            if (window.echarts || Date.now() - startedAt >= MAX_LIBRARY_WAIT_MS) {
                resolve();
                return;
            }
            window.setTimeout(tick, 50);
        };
        tick();
    });

/**
 * Keep the chapter toggle button, ARIA state, and optional chart resize signal in sync.
 */
const syncToggleState = (toggle, content, isExpanded, shouldResize = false) => {
    const icon = toggle.querySelector(".home-flow-toggle-icon");
    const label = toggle.querySelector(".home-flow-toggle-label");
    const sectionTitle = toggle.dataset.sectionTitle || "section";
    const stage = toggle.closest(".home-flow-stage");

    if (content) {
        content.classList.toggle("collapsed", !isExpanded);
        content.classList.toggle("expanded", isExpanded);
    }

    if (stage) {
        stage.classList.toggle("is-collapsed", !isExpanded);
        stage.classList.toggle("is-expanded", isExpanded);
    }

    if (icon) {
        icon.textContent = isExpanded ? "-" : "+";
    }

    if (label) {
        label.textContent = isExpanded ? "Collapse" : "Expand";
    }

    toggle.setAttribute("aria-expanded", String(isExpanded));
    toggle.setAttribute(
        "aria-label",
        `${isExpanded ? "Collapse" : "Expand"} ${sectionTitle} section`,
    );

    if (!shouldResize) {
        return;
    }

    window.requestAnimationFrame(() => {
        window.dispatchEvent(new Event("resize"));
    });
};

/**
 * Wire up the story-stage expand and collapse controls once the shell is ready.
 */
const initialiseCollapsibleSections = () => {
    const toggles = document.querySelectorAll(".home-flow-toggle");

    toggles.forEach((toggle) => {
        const contentId = toggle.getAttribute("aria-controls");
        const content = document.getElementById(contentId);

        if (!content) {
            return;
        }

        const startsExpanded = toggle.getAttribute("aria-expanded") !== "false";
        syncToggleState(toggle, content, startsExpanded);

        toggle.addEventListener("click", () => {
            const isExpanded = toggle.getAttribute("aria-expanded") === "true";

            if (!isExpanded) {
                toggles.forEach((otherToggle) => {
                    if (otherToggle !== toggle) {
                        const otherContentId = otherToggle.getAttribute("aria-controls");
                        const otherContent = document.getElementById(otherContentId);

                        if (otherContent && otherToggle.getAttribute("aria-expanded") === "true") {
                            syncToggleState(otherToggle, otherContent, false, true);
                        }
                    }
                });
            }

            syncToggleState(toggle, content, !isExpanded, true);
        });
    });
};

/**
 * Start the landing dashboard only once. Chart libraries and overview payload load in parallel.
 */
const bootstrapOverviewPage = async () => {
    if (hasInitialised) {
        return;
    }

    hasInitialised = true;
    initialiseCollapsibleSections();

    const librariesReady = createLibrariesReadyPromise();
    await initialiseOverviewPage(librariesReady);
};

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrapOverviewPage, { once: true });
} else {
    bootstrapOverviewPage();
}
