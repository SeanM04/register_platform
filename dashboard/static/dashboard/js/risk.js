import { initialiseRiskPage } from "./risk/index.js?v=20260412-risk-shell01";

/**
 * Keep the section toggle button, ARIA state, and optional chart resize signal in sync.
 */
const syncToggleState = (toggle, content, isExpanded, shouldResize = false) => {
    const icon = toggle.querySelector(".risk-flow-toggle-icon");
    const label = toggle.querySelector(".risk-flow-toggle-label");
    const sectionTitle = toggle.dataset.sectionTitle || "section";

    if (content) {
        content.classList.toggle("is-expanded", isExpanded);
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
 * Wire up the section expand and collapse controls once the shell is ready.
 */
const initialiseCollapsibleSections = () => {
    const toggles = document.querySelectorAll(".risk-flow-toggle");

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

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        initialiseRiskPage();
        initialiseCollapsibleSections();
    }, { once: true });
} else {
    initialiseRiskPage();
    initialiseCollapsibleSections();
}
