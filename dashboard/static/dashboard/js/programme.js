import { initialiseProgrammePage } from "./programme/index.js?v=20260405-programmes-progressive01";

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        initialiseProgrammePage();
    }, { once: true });
} else {
    initialiseProgrammePage();
}
