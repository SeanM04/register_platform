import { initialiseOverviewPage } from "./home/index.js?v=20260416-home-drilldown16";

const MAX_LIBRARY_WAIT_MS = 2200;
let hasInitialised = false;

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
                // If expanding this section, collapse all other sections first
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

            // Then toggle this section
            syncToggleState(toggle, content, !isExpanded, true);
        });
    });
};

/**
 * Start the landing dashboard only once, even if library polling resolves multiple times.
 */
const bootstrapOverviewPage = async () => {
    if (hasInitialised) {
        return;
    }

    hasInitialised = true;
    initialiseCollapsibleSections();
    await initialiseOverviewPage();
};

/**
 * Guard the dashboard bootstrap until ECharts is present on the page.
 */
const areLibrariesReady = () => Boolean(window.echarts);

/**
 * Poll for shared chart libraries so the page can stay resilient to CDN latency.
 */
const waitForLibrariesThenInitialise = (startedAt = Date.now()) => {
    if (areLibrariesReady() || Date.now() - startedAt >= MAX_LIBRARY_WAIT_MS) {
        bootstrapOverviewPage();
        return;
    }

    window.setTimeout(() => {
        waitForLibrariesThenInitialise(startedAt);
    }, 50);
};

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        waitForLibrariesThenInitialise();
    }, { once: true });
} else {
    waitForLibrariesThenInitialise();
}
