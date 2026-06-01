import { initialiseProgrammePage } from "./programme/index.js?v=20260601-drilldown-click-reliability01";

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        initialiseProgrammePage();
    }, { once: true });
} else {
    initialiseProgrammePage();
}
