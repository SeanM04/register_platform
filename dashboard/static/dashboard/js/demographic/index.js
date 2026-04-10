/* eslint-env browser */
/* global URL, window, fetch, document, ResizeObserver */

import { createDemographicContext, updateDemographicContext } from "./context.js";
import { initialiseFullscreenControls } from "./fullscreen.js";
import { initialiseGenderSection } from "./gender.js";
import { initialiseLocationSection } from "./locations.js";
import { initialiseLocationMixSection } from "./location_mix.js";
import { initialiseOriginMapSection } from "./origin_map.js";
import { initialiseProgrammeMixSection } from "./programme_mix.js";
import { initialiseProgrammeGenderSection } from "./programme_gender.js";
import { initialiseYearDistributionSection } from "./level_gender.js";
import { initialiseAgeDistributionSection } from "./age_distribution.js";
import {
    initialiseGenderNarrative,
    initialiseLocationNarrative,
    initialiseLocationMixNarrative,
    initialiseOriginMapNarrative,
    initialiseProgrammeNarrative,
    initialiseProgrammeGenderNarrative,
    initialiseYearDistributionNarrative,
    initialiseAgeDistributionNarrative,
    renderStoryBanner,
} from "./narratives.js";

const buildRequestUrl = (endpoint) => {
    const requestUrl = new URL(endpoint, window.location.origin);
    const currentUrl = new URL(window.location.href);

    currentUrl.searchParams.forEach((value, key) => {
        requestUrl.searchParams.set(key, value);
    });

    return requestUrl;
};

const fetchJson = async (endpoint) => {
    if (!endpoint) {
        return null;
    }

    const response = await fetch(buildRequestUrl(endpoint), {
        credentials: "same-origin",
        headers: {
            "X-Requested-With": "XMLHttpRequest",
        },
    });

    if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
    }

    return response.json();
};

const demographicRoot = document.querySelector(".demographic-layout");
const payloadPromise = demographicRoot
    ? fetchJson(demographicRoot.dataset.payloadUrl).catch(() => null)
    : Promise.resolve(null);
const MAP_LIBRARY_WAIT_MS = 2400;

const scheduleBackgroundTask = (callback, timeout = 1200, fallbackDelay = 48) => {
    if (window.requestIdleCallback) {
        window.requestIdleCallback(() => {
            callback();
        }, { timeout });
        return;
    }

    window.setTimeout(callback, fallbackDelay);
};

const waitForMapLibrary = (callback, startedAt = Date.now()) => {
    if (window.maplibregl || Date.now() - startedAt >= MAP_LIBRARY_WAIT_MS) {
        callback();
        return;
    }

    window.setTimeout(() => {
        waitForMapLibrary(callback, startedAt);
    }, 60);
};

const initialiseDeferredOriginMapSection = (context, controllers, resizeCharts) => {
    const originMapTarget = context.elements.originMapChart;
    if (!originMapTarget) {
        return;
    }

    let hasQueuedInitialisation = false;
    const start = () => {
        if (hasQueuedInitialisation) {
            return;
        }

        hasQueuedInitialisation = true;
        waitForMapLibrary(() => {
            controllers.push(initialiseOriginMapSection(context));
            resizeCharts();
        });
    };

    if (!window.IntersectionObserver) {
        window.setTimeout(start, 600);
        return;
    }

    const observer = new IntersectionObserver((entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) {
            return;
        }

        observer.disconnect();
        start();
    }, { rootMargin: "240px 0px" });

    observer.observe(originMapTarget);
    window.setTimeout(() => {
        observer.disconnect();
        start();
    }, 1800);
};

const buildMetricCards = (metrics = {}) => Object.keys(metrics).map((key) => ({
    key,
    value: metrics[key],
}));

const initialiseChartResizeHandling = (controllers, resizeCharts) => {
    const charts = controllers
        .map((controller) => controller.getChart())
        .filter(Boolean);

    if (!charts.length) {
        return;
    }

    window.addEventListener("resize", resizeCharts);

    if (!window.ResizeObserver) {
        return;
    }

    const observer = new ResizeObserver(() => {
        resizeCharts();
    });

    charts.forEach((chart) => {
        observer.observe(chart.getDom());
    });
};

const hydrateSummaryCards = (context, summaryCards = []) => {
    if (!summaryCards.length) {
        return;
    }

    summaryCards.forEach((card) => {
        const metricValue = context.elements.metricValues.find(
            (node) => node.dataset.metricKey === card.key,
        );

        if (metricValue) {
            metricValue.textContent = card.value;
            metricValue.classList.remove("is-loading");
            metricValue.classList.add("is-loaded");
        }
    });
};

const loadNarrativesInBackground = (context) => {
    if (!demographicRoot?.dataset.narrativesUrl) {
        return;
    }

    scheduleBackgroundTask(() => {
        fetchJson(demographicRoot.dataset.narrativesUrl)
            .then((payload) => {
                const cardNarratives = payload?.card_narratives || {};
                updateDemographicContext(context, { cardNarratives });
                hydrateNarratives(context);
            })
            .catch(() => {});
    }, 1600, 120);
};

const hydrateNarratives = (context) => {
    initialiseGenderNarrative(context.elements, context.data.genderRows, context.data.cardNarratives, context.flags);
    initialiseLocationNarrative(context.elements, context.data.locationRows, context.data.cardNarratives, context.flags);
    initialiseLocationMixNarrative(context.elements, context.data.locationMixRows, context.data.cardNarratives, context.flags);
    initialiseProgrammeNarrative(context.elements, context.data.programmeRows, context.data.cardNarratives, context.flags);
    initialiseProgrammeGenderNarrative(context.elements, context.data.programmeGenderRows, context.data.cardNarratives, context.flags);
    initialiseYearDistributionNarrative(context.elements, context.data.yearDistributionRows, context.data.cardNarratives, context.flags);
    initialiseAgeDistributionNarrative(context.elements, context.data.ageDistributionRows, context.data.cardNarratives, context.flags);
    initialiseOriginMapNarrative(context.elements, context.data.locationMapRows, context.data.locationMapMeta, context.data.cardNarratives, context.flags);
};

const setDemographicShellErrorState = (context) => {
    if (context.elements.storyBanner) {
        context.elements.storyBanner.innerHTML = `
            <p class="demographic-banner-loading">The page shell loaded, but the demographic dataset could not be retrieved. Try refreshing this workspace.</p>
        `.trim();
        context.elements.storyBanner.hidden = false;
    }
};

export const initialiseDemographicPage = async () => {
    const shellContext = createDemographicContext();
    const root = document.querySelector(".demographic-layout");

    if (!root || !shellContext.elements.storyBanner) {
        return;
    }

    let chartPayload = null;
    const payloadResponse = await payloadPromise;
    if (!payloadResponse) {
        setDemographicShellErrorState(shellContext);
        return;
    }

    chartPayload = {
        genderRows: payloadResponse?.gender_rows || [],
        locationRows: payloadResponse?.location_rows || [],
        locationMixRows: payloadResponse?.location_mix_rows || [],
        locationMapRows: payloadResponse?.location_map_rows || [],
        locationMapMeta: payloadResponse?.location_map_meta || {},
        programmeRows: payloadResponse?.programme_rows || [],
        programmeGenderRows: payloadResponse?.programme_gender_rows || [],
        yearDistributionRows: payloadResponse?.year_distribution_rows || [],
        ageDistributionRows: payloadResponse?.age_distribution_rows || [],
    };

    const context = updateDemographicContext(shellContext, { chartPayload });
    hydrateSummaryCards(context, buildMetricCards(payloadResponse?.metrics || {}));

    renderStoryBanner(context.elements.storyBanner, context.data.genderRows, context.data.locationRows, context.data.programmeRows);

    const controllers = [
        initialiseGenderSection(context),
        initialiseLocationSection(context),
        initialiseLocationMixSection(context),
        initialiseProgrammeMixSection(context),
        initialiseProgrammeGenderSection(context),
        initialiseYearDistributionSection(context),
        initialiseAgeDistributionSection(context),
    ];
    const resizeCharts = () => {
        controllers.forEach((controller) => {
            controller.resize();
        });
    };

    initialiseChartResizeHandling(controllers, resizeCharts);
    initialiseFullscreenControls(context.elements.fullscreenButtons, resizeCharts);
    initialiseDeferredOriginMapSection(context, controllers, resizeCharts);
    loadNarrativesInBackground(context);
};
