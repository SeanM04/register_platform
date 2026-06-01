import { createHomeContext, updateHomeContext } from "./context.js?v=20260514-home-parallel-metrics01";
import { initialiseFacultyLoadSection } from "./faculty_load.js?v=20260601-drilldown-numeric-align01";
import { initialiseFullscreenControls } from "./fullscreen.js?v=20260601-drilldown-numeric-align01";
import {
    initialiseFacultyNarrative,
    initialiseChapterOneNarrative,
    initialiseChapterTwoNarrative,
    initialiseOutcomeNarrative,
    initialiseProgressNarrative,
    initialiseRiskNarrative,
    renderStoryBanner,
} from "./narratives.js?v=20260416-home-banner-text02";
import { initialiseOutcomeSection } from "./outcomes.js?v=20260601-drilldown-numeric-align01";
import { initialiseProgressSection } from "./progress.js?v=20260601-drilldown-numeric-align01";
import { initialiseRiskDistributionSection } from "./risk_distribution.js?v=20260601-drilldown-numeric-align01";
import { escapeTooltipHtml } from "./shared.js?v=20260403-home-story04";

/**
 * Carry the current filter query string over to async shell endpoints.
 */
const buildRequestUrl = (endpoint) => {
    const requestUrl = new URL(endpoint, window.location.origin);
    const currentUrl = new URL(window.location.href);

    currentUrl.searchParams.forEach((value, key) => {
        requestUrl.searchParams.set(key, value);
    });

    return requestUrl;
};

/**
 * Fetch JSON from a dashboard endpoint while preserving shared AJAX headers.
 */
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

const homeRoot = document.querySelector(".home-layout");
const payloadPromise = homeRoot
    ? fetchJson(homeRoot.dataset.payloadUrl).catch(() => null)
    : Promise.resolve(null);
let narrativesPromise = null;

/**
 * Resize chart instances when the viewport or their container dimensions change.
 */
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

/**
 * Replace the shell KPI placeholders with the hydrated summary-card response.
 */
const hydrateSummaryCards = (context, summaryCards = []) => {
    if (!summaryCards.length) {
        return;
    }

    summaryCards.forEach((card) => {
        const metricCard = context.elements.metricCards.find(
            (node) => node.dataset.metricKey === card.key,
        );
        const metricValue = context.elements.metricValues.find(
            (node) => node.dataset.metricKey === card.key,
        );
        const metricNote = context.elements.metricNotes.find(
            (node) => node.dataset.metricKey === card.key,
        );

        if (metricCard) {
            metricCard.className = `home-metric home-metric-${card.tone}`;
        }
        if (metricValue) {
            metricValue.textContent = card.value;
            metricValue.classList.remove("is-loading");
            metricValue.classList.add("is-loaded");
        }
        if (metricNote) {
            metricNote.textContent = card.note || "";
        }
    });
};

/**
 * Render the "Next Actions" cards returned by the async overview payload.
 */
const renderActionCards = (context, actionCards = []) => {
    if (!context.elements.actionGrid || !actionCards.length) {
        return;
    }

    context.elements.actionGrid.innerHTML = actionCards.map((card) => `
        <article class="home-action-card home-action-card-${escapeTooltipHtml(card.tone)}">
            <p class="home-action-kicker">${escapeTooltipHtml(card.kicker)}</p>
            <h3 class="home-action-title">${escapeTooltipHtml(card.title)}</h3>
            <p class="home-action-copy">${escapeTooltipHtml(card.copy)}</p>
            <a class="home-action-link" href="${escapeTooltipHtml(card.action_url)}">${escapeTooltipHtml(card.action_label)}</a>
        </article>
    `).join("").trim();
};

const renderNarrativeDiagnostics = (context) => {
    const statusElement = context.elements.narrativeStatus;
    if (statusElement) {
        statusElement.hidden = true;
        statusElement.textContent = "";
        statusElement.className = "home-narrative-status";
    }
};

/**
 * Apply chapter summaries and card-level narrative copy from the current context.
 */
const hydrateNarratives = (context) => {
    initialiseChapterOneNarrative(
        context.elements,
        {
            outcomeRows: context.data.outcomeRows,
            riskRows: context.data.riskDistributionRows,
        },
        context.data.cardNarratives,
        context.flags,
    );
    initialiseChapterTwoNarrative(
        context.elements,
        {
            facultyRows: context.data.facultyLoadRows,
            progressRows: context.data.progressRows,
        },
        context.data.cardNarratives,
        context.flags,
    );
    initialiseOutcomeNarrative(context.elements, context.data.outcomeRows, context.data.cardNarratives, context.flags);
    initialiseRiskNarrative(context.elements, context.data.riskDistributionRows, context.data.cardNarratives, context.flags);
    initialiseFacultyNarrative(context.elements, context.data.facultyLoadRows, context.data.cardNarratives, context.flags);
    initialiseProgressNarrative(context.elements, context.data.progressRows, context.data.cardNarratives, context.flags);
};

/**
 * Resolve the optional narrative request and then refresh all narrative surfaces.
 */
const loadNarratives = (context) => {
    if (!homeRoot?.dataset.narrativesUrl || !context.flags.aiNarrativesEnabled) {
        return;
    }

    if (!narrativesPromise) {
        narrativesPromise = fetchJson(homeRoot.dataset.narrativesUrl).catch(() => null);
    }

    narrativesPromise
        .then((payload) => {
            const cardNarratives = payload?.card_narratives;
            updateHomeContext(context, {
                cardNarratives: cardNarratives || context.data.cardNarratives,
                narrativeDiagnostics: payload?.diagnostics || context.data.narrativeDiagnostics,
                narrativeFetchCompleted: true,
            });
            if (homeRoot) {
                const diagnostics = context.data.narrativeDiagnostics || {};
                homeRoot.dataset.narrativeSource = diagnostics.returned_source || "";
                homeRoot.dataset.narrativeStatus = diagnostics.status || "";
                homeRoot.dataset.narrativeProvider = diagnostics.provider_attempted || diagnostics.configured_provider || "";
                homeRoot.dataset.narrativeFallbackReason = diagnostics.fallback_reason || "";
            }
            if (window.console?.info && payload?.diagnostics) {
                window.console.info("[Home narratives diagnostics]", payload.diagnostics);
            }
            renderNarrativeDiagnostics(context);
            hydrateNarratives(context);
        });
};

/**
 * Fall back to a shell-level message when the main payload cannot be retrieved.
 */
const setHomeShellErrorState = (context) => {
    if (context.elements.storyBanner) {
        context.elements.storyBanner.hidden = false;
        context.elements.storyBanner.innerHTML = `
            <h1 class="home-banner-title">The dashboard shell loaded, but the live overview dataset could not be retrieved.</h1>
            <p class="home-banner-copy">Refresh this workspace to try the landing-page analytics again.</p>
        `.trim();
    }
};

/**
 * Bootstrap the story-first landing dashboard from the lightweight shell.
 * @param {Promise<void>} librariesReadyPromise Resolves when chart libraries (e.g. ECharts) are available.
 */
export const initialiseOverviewPage = async (librariesReadyPromise = Promise.resolve()) => {
    const shellContext = createHomeContext();

    if (!homeRoot || !shellContext.elements.storyBanner) {
        return;
    }

    const [, payloadResponse] = await Promise.all([librariesReadyPromise, payloadPromise]);
    if (!payloadResponse) {
        setHomeShellErrorState(shellContext);
        return;
    }

    const chartPayload = {
        outcomeRows: payloadResponse?.outcome_rows || [],
        riskDistributionRows: payloadResponse?.risk_distribution_rows || [],
        facultyLoadRows: payloadResponse?.faculty_load_rows || [],
        progressRows: payloadResponse?.progress_rows || [],
    };
    const context = updateHomeContext(shellContext, {
        chartPayload,
        actionCards: payloadResponse?.action_cards || [],
    });

    hydrateSummaryCards(context, payloadResponse?.summary_cards || []);
    renderActionCards(context, context.data.actionCards);

    renderStoryBanner(
        context.elements.storyBanner,
        context.data.outcomeRows,
        context.data.riskDistributionRows,
        context.data.facultyLoadRows,
        context.data.progressRows,
    );
    renderNarrativeDiagnostics(context);
    hydrateNarratives(context);

    const controllers = [
        initialiseOutcomeSection(context),
        initialiseRiskDistributionSection(context),
        initialiseFacultyLoadSection(context),
        initialiseProgressSection(context),
    ];

    const resizeCharts = () => {
        controllers.forEach((controller) => {
            controller.resize();
        });
    };

    initialiseChartResizeHandling(controllers, resizeCharts);
    initialiseFullscreenControls(context.elements.fullscreenButtons, resizeCharts);
    loadNarratives(context);
};
