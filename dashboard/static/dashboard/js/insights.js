import { initialiseInsightsPage } from "./insights/index.js?v=20260403-insights-story02";

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        initialiseInsightsPage();
    }, { once: true });
} else {
    initialiseInsightsPage();
}
