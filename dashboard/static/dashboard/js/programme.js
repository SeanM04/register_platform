import { initialiseProgrammePage } from "./programme/index.js?v=20260411-programme-axis06";

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        initialiseProgrammePage();
    }, { once: true });
} else {
    initialiseProgrammePage();
}
