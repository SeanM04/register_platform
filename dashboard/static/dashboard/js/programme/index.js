import { createProgrammeContext, updateProgrammeNarrativeContext } from "./context.js?v=20260411-programme-axis05";
import { initialiseDepartmentSection } from "./departments.js?v=20260411-programme-axis04";
import { initialiseFullscreenControls } from "./fullscreen.js?v=20260405-programmes-progressive01";
import { initialiseLoadSection } from "./load.js?v=20260411-programme-axis04";
import { initialiseAccordion } from "./accordion.js?v=20260405-programmes-progressive01";
import {
    initialiseDepartmentNarrative,
    initialiseLoadNarrative,
    initialisePerformanceNarrative,
    initialiseQualityNarrative,
    renderStoryBanner,
} from "./narratives.js?v=20260411-programme-axis05";
import { initialisePerformanceSection } from "./performance.js?v=20260405-programmes-progressive01";
import { initialiseQualitySection } from "./quality.js?v=20260405-programmes-progressive01";
import { initialiseRegisterInteractions, renderProgrammeRegister } from "./register.js?v=20260414-instant01";

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

const hydrateNarratives = (context) => {
    initialiseLoadNarrative(context.elements, context.data.topLoadRows, context.data.cardNarratives, context.flags);
    initialiseDepartmentNarrative(context.elements, context.data.departmentRows, context.data.cardNarratives, context.flags);
    initialiseQualityNarrative(context.elements, context.data.lowPassRows, context.data.cardNarratives, context.flags);
    initialisePerformanceNarrative(context.elements, context.data.performanceRows, context.data.cardNarratives, context.flags);
};

const renderNarrativeDiagnostics = (context) => {
    const diagnostics = context.data.narrativeDiagnostics || {};
    const statusElement = context.elements.narrativeStatus;
    const root = context.elements.root;

    if (root) {
        root.dataset.narrativeSource = diagnostics.returned_source || "";
        root.dataset.narrativeStatus = diagnostics.status || "";
        root.dataset.narrativeProvider = diagnostics.provider_attempted || diagnostics.configured_provider || "";
        root.dataset.narrativeFallbackReason = diagnostics.fallback_reason || "";
    }

    if (!statusElement) {
        return;
    }

    const message = String(diagnostics.message || "").trim();
    if (!message) {
        statusElement.hidden = true;
        statusElement.textContent = "";
        statusElement.className = "programme-narrative-status";
        return;
    }

    statusElement.hidden = false;
    statusElement.textContent = message;
    statusElement.className = `programme-narrative-status is-${diagnostics.status || "rules"}`;

    if (diagnostics.fallback_detail) {
        statusElement.title = diagnostics.fallback_detail;
    } else {
        statusElement.removeAttribute("title");
    }

    if (window.console?.info) {
        window.console.info("[Programme narratives diagnostics]", diagnostics);
    }
};

const hydrateSummaryCards = (context, summaryCards = []) => {
    if (!summaryCards.length) {
        return;
    }

    summaryCards.forEach((card) => {
        const metricValue = context.elements.metricValues.find((node) => node.dataset.metricKey === card.key);
        const metricNote = context.elements.metricNotes.find((node) => node.dataset.metricKey === card.key);

        if (metricValue) {
            metricValue.textContent = card.value;
            metricValue.classList.remove("is-loading");
            metricValue.classList.add("is-loaded");
        }

        if (metricNote) {
            metricNote.textContent = card.note;
        }
    });
};

const setProgrammeShellErrorState = (context) => {
    if (context.elements.storyBanner) {
        context.elements.storyBanner.innerHTML = `
            <p class="programme-banner-loading">The page shell loaded, but the programme dataset could not be retrieved. Try refreshing this workspace.</p>
        `.trim();
        context.elements.storyBanner.hidden = false;
    }

    if (context.elements.registerMeta) {
        context.elements.registerMeta.textContent = "Programme rows could not be loaded for the current scope.";
    }
};

export const initialiseProgrammePage = async () => {
    const shellContext = createProgrammeContext();
    const root = shellContext.elements.root;

    if (!root || !shellContext.elements.storyBanner) {
        return;
    }

    let chartPayload = null;
    try {
        const payloadResponse = await fetchJson(root.dataset.payloadUrl);
        
        chartPayload = {
            topLoadRows: payloadResponse?.top_load_rows || [],
            departmentRows: payloadResponse?.department_rows || [],
            lowPassRows: payloadResponse?.low_pass_rows || [],
            performanceRows: payloadResponse?.performance_rows || [],
            programmeRows: payloadResponse?.programme_rows || [],
            registerMeta: payloadResponse?.register_meta || {
                visibleCount: 0,
                current_page: 1,
                per_page: 10,
                total_pages: 1,
                has_previous: false,
                has_next: false,
            },
        };
        hydrateSummaryCards(shellContext, payloadResponse?.summary_cards || []);
    } catch (error) {
        console.error('Error fetching payload:', error);
        setProgrammeShellErrorState(shellContext);
        renderProgrammeRegister(shellContext.elements.registerBody, shellContext.elements.registerMeta, [], {});
        return;
    }

    const context = createProgrammeContext({ chartPayload });

    initialiseAccordion();

    renderStoryBanner(
        context.elements.storyBanner,
        context.data.topLoadRows,
        context.data.departmentRows,
        context.data.lowPassRows,
    );
    renderNarrativeDiagnostics(context);
    renderProgrammeRegister(
        context.elements.registerBody,
        context.elements.registerMeta,
        context.data.programmeRows,
        context.data.registerMeta,
    );

    const controllers = [
        initialiseLoadSection(context),
        initialiseDepartmentSection(context),
        initialiseQualitySection(context),
        initialisePerformanceSection(context),
    ];

    const resizeCharts = () => {
        controllers.forEach((controller) => {
            controller.resize();
        });
    };

    initialiseChartResizeHandling(controllers, resizeCharts);
    initialiseRegisterInteractions(context.elements.searchForm, context.elements.searchInput);
    initialiseFullscreenControls(context.elements.fullscreenButtons, resizeCharts);

    fetchJson(root.dataset.narrativesUrl)
        .then((payload) => {
            const cardNarratives = payload?.card_narratives || {};
            const narrativeDiagnostics = payload?.diagnostics || {};
            updateProgrammeNarrativeContext(context, cardNarratives, narrativeDiagnostics);
            hydrateNarratives(context);
            renderNarrativeDiagnostics(context);
        })
        .catch(() => {});
};
