import { initialiseRiskPage } from "./risk/index.js?v=20260403-risk-storyflow10";

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        initialiseRiskPage();
    }, { once: true });
} else {
    initialiseRiskPage();
}
