import { initialiseAcademicLevelPage } from "./academic_level/index.js?v=20260601-drilldown-numeric-align01";

/**
 * Keep the section toggle button, ARIA state, and optional chart resize signal in sync.
 */
const syncToggleState = (toggle, content, isExpanded, shouldResize = false) => {
    const icon = toggle.querySelector(".level-insight-toggle-icon, .level-section-toggle-icon");
    const label = toggle.querySelector(".level-insight-toggle-label, .level-section-toggle-label");
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
    const toggles = document.querySelectorAll(".level-insight-toggle, .level-section-toggle");

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

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        initialiseAcademicLevelPage();
        initialiseCollapsibleSections();
    }, { once: true });
} else {
    initialiseAcademicLevelPage();
    initialiseCollapsibleSections();
}
