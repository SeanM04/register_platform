import { createRiskContext, updateRiskContext } from "./context.js?v=20260414-risk-shell03";
import { initialiseDistributionSection } from "./distribution.js?v=20260601-drilldown-click-reliability01";
import { initialiseDriversSection } from "./drivers.js?v=20260601-drilldown-click-reliability01";
import { initialiseFullscreenControls } from "./fullscreen.js?v=20260601-drilldown-numeric-align01";
import { initialiseLevelsSection } from "./levels.js?v=20260601-drilldown-click-reliability01";
import { renderStoryBanner } from "./narratives.js?v=20260403-risk-storyflow10";
import { initialiseProgrammesSection } from "./programmes.js?v=20260601-drilldown-click-reliability01";
import { initialiseRiskSearch } from "./search.js?v=20260403-risk-storyflow10";
import { escapeTooltipHtml } from "./shared.js?v=20260403-risk-storyflow10";

const buildRequestUrl = (endpoint, page = null) => {
    const requestUrl = new URL(endpoint, window.location.origin);
    const currentUrl = new URL(window.location.href);

    currentUrl.searchParams.forEach((value, key) => {
        requestUrl.searchParams.set(key, value);
    });

    if (page) {
        requestUrl.searchParams.set("page", page);
    }

    return requestUrl;
};

export const fetchJson = async (endpoint, page = null) => {
    if (!endpoint) {
        return null;
    }

    const response = await fetch(buildRequestUrl(endpoint, page), {
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

const hydrateSummaryCards = (context, metrics = {}, summaryCards = []) => {
    context.elements.metricValues.forEach((element) => {
        const metricKey = element.dataset.metricKey;
        if (!metricKey || !Object.prototype.hasOwnProperty.call(metrics, metricKey)) {
            return;
        }

        element.textContent = metrics[metricKey];
        element.classList.remove("is-loading");
    });

    if (!summaryCards.length || !context.elements.metricNotes?.length) {
        return;
    }

    summaryCards.forEach((card) => {
        const note = context.elements.metricNotes.find((node) => node.dataset.metricKey === card.key);
        if (note) {
            note.textContent = card.note || "";
        }
    });
};

const renderRiskRegister = (context, register = {}, cohortTotalStudents = 0) => {
    const body = context.elements.registerBody;
    const resultsMeta = context.elements.resultsMeta;
    const pagination = context.elements.pagination;

    if (!body || !resultsMeta || !pagination) {
        return;
    }

    const rows = register.rows || [];
    if (!rows.length) {
        body.innerHTML = `
            <tr>
                <td class="risk-empty" colspan="8">No at-risk students matched the current filters.</td>
            </tr>
        `.trim();
    } else {
        body.innerHTML = rows.map((row) => `
            <tr>
                <td class="risk-td-student">
                    <a class="risk-student-link" href="/students/${encodeURIComponent(row.detail_slug)}/" aria-label="View ${escapeTooltipHtml(row.name)} profile">
                        <span class="risk-student-name">${escapeTooltipHtml(row.name)}</span>
                    </a>
                </td>
                <td>${escapeTooltipHtml(row.programme)}</td>
                <td>${escapeTooltipHtml(row.academic_level)}</td>
                <td>${escapeTooltipHtml(row.average_mark)}%</td>
                <td>${escapeTooltipHtml(row.failed_courses)}</td>
                <td>${escapeTooltipHtml(row.carrying)}</td>
                <td>${escapeTooltipHtml(row.decision)}</td>
                <td class="risk-td-status">
                    <span class="risk-status-badge risk-status-${escapeTooltipHtml(row.risk_level_key)}">${escapeTooltipHtml(row.risk_level)}</span>
                    <span class="risk-status-copy">${escapeTooltipHtml(row.risk_drivers_display)}</span>
                </td>
            </tr>
        `).join("").trim();
    }

    resultsMeta.textContent = register.total_count
        ? `Showing ${register.start_index}-${register.end_index} of ${register.total_count} at-risk students${cohortTotalStudents ? ` across ${cohortTotalStudents} visible students` : ""}`
        : "No at-risk students matched the current filters.";

    const pageLinks = [];
    if (register.has_previous) {
        pageLinks.push(`<a class="risk-page-link risk-page-arrow" href="#" data-risk-page="${register.previous_page}">Prev</a>`);
    } else {
        pageLinks.push('<span class="risk-page-link risk-page-arrow is-disabled">Prev</span>');
    }

    (register.page_numbers || []).forEach((pageNumber) => {
        if (pageNumber === register.page) {
            pageLinks.push(`<span class="risk-page-link is-current">${pageNumber}</span>`);
            return;
        }
        pageLinks.push(`<a class="risk-page-link" href="#" data-risk-page="${pageNumber}">${pageNumber}</a>`);
    });

    if (register.has_next) {
        pageLinks.push(`<a class="risk-page-link risk-page-arrow" href="#" data-risk-page="${register.next_page}">Next</a>`);
    } else {
        pageLinks.push('<span class="risk-page-link risk-page-arrow is-disabled">Next</span>');
    }

    pagination.innerHTML = pageLinks.join("").trim();
};

const setRiskShellErrorState = (context) => {
    if (context.elements.storyBanner) {
        context.elements.storyBanner.innerHTML = `
            <p class="risk-banner-loading">The page shell loaded, but the risk dataset could not be retrieved. Try refreshing this workspace.</p>
        `.trim();
        context.elements.storyBanner.hidden = false;
    }
};

export const initialiseRiskPage = async (metricsPromise = null, payloadPromise = null) => {
    const shellContext = createRiskContext();
    const { elements } = shellContext;
    const payloadUrl = elements.root?.dataset.payloadUrl;

    if (!payloadUrl) {
        setRiskShellErrorState(shellContext);
        return;
    }

    // Hydrate KPI cards as soon as metrics resolve (may arrive before payload)
    const resolvedMetricsPromise = metricsPromise || Promise.resolve(null);
    resolvedMetricsPromise.then((metricsResponse) => {
        if (metricsResponse?.metrics || metricsResponse?.summary_cards) {
            hydrateSummaryCards(shellContext, metricsResponse.metrics || {}, metricsResponse.summary_cards || []);
        }
    }).catch(() => {});

    let payloadResponse = null;
    try {
        payloadResponse = await (payloadPromise || fetchJson(payloadUrl));
    } catch (error) {
        setRiskShellErrorState(shellContext);
        return;
    }

    const context = updateRiskContext(shellContext, {
        chartPayload: {
            distributionRows: payloadResponse?.risk_distribution_rows || [],
            driverRows: payloadResponse?.risk_driver_rows || [],
            levelRows: payloadResponse?.risk_level_rows || [],
            programmeRows: payloadResponse?.risk_programme_rows || [],
        },
        cardNarratives: payloadResponse?.risk_card_narratives || {},
    });
    const { data, elements: hydratedElements } = context;

    hydrateSummaryCards(context, payloadResponse?.metrics || {}, payloadResponse?.summary_cards || []);
    renderRiskRegister(context, payloadResponse?.register || {}, payloadResponse?.cohort_total_students || 0);

    renderStoryBanner(
        hydratedElements.storyBanner,
        data.distributionRows,
        data.driverRows,
        data.levelRows,
        data.programmeRows,
    );

    const controllers = [
        initialiseDistributionSection(context),
        initialiseDriversSection(context),
        initialiseLevelsSection(context),
        initialiseProgrammesSection(context),
    ];
    const resizeCharts = () => {
        controllers.forEach((controller) => {
            controller.resize();
        });
    };

    initialiseRiskSearch(hydratedElements.searchForm, hydratedElements.searchInput);
    initialiseChartResizeHandling(controllers, resizeCharts);
    initialiseFullscreenControls(hydratedElements.fullscreenButtons, resizeCharts);

    if (hydratedElements.pagination) {
        hydratedElements.pagination.addEventListener("click", async (event) => {
            const link = event.target.closest("[data-risk-page]");
            if (!link) {
                return;
            }

            event.preventDefault();
            const page = link.dataset.riskPage;
            const pagePayload = await fetchJson(payloadUrl, page).catch(() => null);
            if (!pagePayload) {
                return;
            }

            renderRiskRegister(context, pagePayload?.register || {}, pagePayload?.cohort_total_students || 0);
            const currentUrl = new URL(window.location.href);
            currentUrl.searchParams.set("page", String(page));
            window.history.replaceState({}, "", currentUrl);
        });
    }
};
