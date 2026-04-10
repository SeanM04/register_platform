import { initialiseDemographicPage } from "./demographic/index.js";
import { initialiseAccordion } from "./demographic/accordion.js";

const MAX_LIBRARY_WAIT_MS = 2200;
let hasInitialised = false;

const bootstrapDemographicPage = async () => {
    if (hasInitialised) {
        return;
    }

    hasInitialised = true;
    initialiseAccordion();
    await initialiseDemographicPage();
};

const areLibrariesReady = () => Boolean(window.echarts);

const waitForLibrariesThenInitialise = (startedAt = Date.now()) => {
    if (areLibrariesReady() || Date.now() - startedAt >= MAX_LIBRARY_WAIT_MS) {
        bootstrapDemographicPage();
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
