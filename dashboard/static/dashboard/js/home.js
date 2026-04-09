import { initialiseOverviewPage } from "./home/index.js?v=20260408-home-ai02";

const MAX_LIBRARY_WAIT_MS = 2200;
let hasInitialised = false;

/**
 * Show drill-down modal with detailed information
 */
window.showDrillDownModal = (title, items) => {
    // Create modal HTML
    const modalHtml = `
        <div id="drill-down-modal" style="
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
        ">
            <div style="
                background: white;
                border-radius: 8px;
                padding: 2rem;
                max-width: 400px;
                width: 90%;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
            ">
                <h3 style="margin: 0 0 1.5rem 0; color: #123b68; font-size: 1.2rem;">${title}</h3>
                <div style="display: grid; gap: 1rem;">
                    ${items.map(item => `
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid #e5e7eb;">
                            <span style="color: #526277; font-weight: 600;">${item.label}:</span>
                            <span style="color: #141414; font-weight: 700;">${item.value}</span>
                        </div>
                    `).join('')}
                </div>
                <button onclick="closeDrillDownModal()" style="
                    margin-top: 1.5rem;
                    width: 100%;
                    padding: 0.75rem;
                    background: #123b68;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-weight: 600;
                    cursor: pointer;
                ">Close</button>
            </div>
        </div>
    `;
    
    // Add modal to page
    document.body.insertAdjacentHTML('beforeend', modalHtml);
};

/**
 * Close drill-down modal
 */
window.closeDrillDownModal = () => {
    const modal = document.getElementById('drill-down-modal');
    if (modal) {
        modal.remove();
    }
};

/**
 * Keep the chapter toggle button, ARIA state, and optional chart resize signal in sync.
 */
const syncToggleState = (toggle, content, isExpanded, shouldResize = false) => {
    const icon = toggle.querySelector(".home-flow-toggle-icon");
    const label = toggle.querySelector(".home-flow-toggle-label");
    const sectionTitle = toggle.dataset.sectionTitle || "section";

    if (content) {
        content.classList.toggle("collapsed", !isExpanded);
        content.classList.toggle("expanded", isExpanded);
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
