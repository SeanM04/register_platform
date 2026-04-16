import { initialiseProgrammePage } from "./programme/index.js?v=20260414-debug01";

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        initialiseProgrammePage();
    }, { once: true });
} else {
    initialiseProgrammePage();
}
