import { initialiseProgrammePage } from "./programme/index.js?v=20260404-programmes-story01";

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        initialiseProgrammePage();
    }, { once: true });
} else {
    initialiseProgrammePage();
}
