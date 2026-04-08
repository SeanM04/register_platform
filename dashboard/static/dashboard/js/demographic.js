import { initialiseDemographicPage } from "./demographic/index.js";

const MAX_LIBRARY_WAIT_MS = 2200;
let hasInitialised = false;

const bootstrapDemographicPage = async () => {
    if (hasInitialised) {
        return;
    }

    hasInitialised = true;
    await initialiseDemographicPage();
};

const areLibrariesReady = () => Boolean(window.echarts && window.maplibregl);

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
