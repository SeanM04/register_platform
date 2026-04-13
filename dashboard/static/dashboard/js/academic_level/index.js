import { createAcademicLevelContext, updateAcademicLevelContext } from "./context.js";
import { initialiseFullscreenControls } from "./fullscreen.js";
import { initialiseGenderSection } from "./gender.js";
import { renderStoryBanner } from "./narratives.js";
import { initialisePassTrendSection } from "./pass_trend.js";
import { initialiseAcademicLevelSearch } from "./search.js";
import { initialiseTopProgrammeSection } from "./top_programme.js";
import { escapeTooltipHtml } from "./shared.js";

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

const renderNarrativeDiagnostics = (context) => {
    const diagnostics = context.data.narrativeDiagnostics || {};
    const statusElement = context.elements.narrativeStatus;

    if (!statusElement) {
        return;
    }

    const message = String(diagnostics.message || "").trim();
    if (!message) {
        statusElement.hidden = true;
        statusElement.textContent = "";
        statusElement.className = "level-narrative-status";
        return;
    }

    statusElement.hidden = false;
    statusElement.textContent = message;
    statusElement.className = `level-narrative-status is-${diagnostics.status || "rules"}`;

    if (diagnostics.fallback_detail) {
        statusElement.title = diagnostics.fallback_detail;
    } else {
        statusElement.removeAttribute("title");
    }

    if (window.console?.info) {
        window.console.info("[Academic level narratives diagnostics]", diagnostics);
    }
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

const hydrateSummaryCards = (context, metrics = {}) => {
    context.elements.metricValues.forEach((element) => {
        const metricKey = element.dataset.metricKey;
        if (!metricKey || !Object.prototype.hasOwnProperty.call(metrics, metricKey)) {
            return;
        }

        element.textContent = metrics[metricKey];
        element.classList.remove("is-loading");
    });
};

const renderLevelTable = (context) => {
    const tableBody = context.elements.levelTableBody;
    if (!tableBody) {
        return;
    }

    const rows = context.data.levelRows || [];
    if (!rows.length) {
        tableBody.innerHTML = `
            <tr>
                <td class="level-empty" colspan="6">No academic level data matched the current filters.</td>
            </tr>
        `.trim();
        context.elements.levelTableRows = [];
        return;
    }

    tableBody.innerHTML = rows.map((row) => `
        <tr data-level-row="${escapeTooltipHtml(row.level)}">
            <td class="level-td-key">${escapeTooltipHtml(row.level)}</td>
            <td>${escapeTooltipHtml(row.students)}</td>
            <td>${escapeTooltipHtml(row.registrations)}</td>
            <td>${escapeTooltipHtml(row.average_mark)}</td>
            <td class="level-td-pass">
                <span class="level-pass-pill${row.below_target ? " is-below-target" : ""}">${escapeTooltipHtml(row.pass_rate)}</span>
                ${row.below_target ? '<span class="level-pass-flag">Below 85% target</span>' : ""}
            </td>
            <td class="level-td-programme">${escapeTooltipHtml(row.top_programme || "")}</td>
        </tr>
    `).join("").trim();
    context.elements.levelTableRows = Array.from(tableBody.querySelectorAll("[data-level-row]"));
};

const setAcademicLevelShellErrorState = (context) => {
    if (context.elements.storyBanner) {
        context.elements.storyBanner.hidden = false;
        context.elements.storyBanner.innerHTML = `
            <div class="level-story-main">
                <h2 class="level-story-title">The academic-level shell loaded, but the live dataset could not be retrieved.</h2>
                <p class="level-story-copy">Refresh this workspace to try the academic-level analytics again.</p>
            </div>
        `.trim();
    }
};

export const initialiseAcademicLevelPage = () => {
    const shellContext = createAcademicLevelContext();
    const { elements } = shellContext;
    let storyBannerHydrated = false;

    initialiseAcademicLevelSearch(elements);

    const metricsUrl = elements.root?.dataset.metricsUrl;
    const payloadUrl = elements.root?.dataset.payloadUrl;
    if (!payloadUrl || !metricsUrl) {
        setAcademicLevelShellErrorState(shellContext);
        return;
    }

    fetchJson(metricsUrl)
        .then((metricsResponse) => {
            if (!metricsResponse) {
                return;
            }

            hydrateSummaryCards(shellContext, metricsResponse?.metrics || {});
            const storyPayload = metricsResponse?.story_payload || {};
            const storyLevelRows = storyPayload.level_rows || [];
            renderStoryBanner(
                shellContext.elements.storyBanner,
                storyLevelRows,
                storyPayload.gender_rows || [],
                storyPayload.programme_rows || [],
            );
            storyBannerHydrated = storyLevelRows.length > 0;
        })
        .catch(() => {});

    fetchJson(payloadUrl)
        .then((payloadResponse) => {
            if (!payloadResponse) {
                setAcademicLevelShellErrorState(shellContext);
                return;
            }

            const context = updateAcademicLevelContext(shellContext, {
                chartPayload: {
                    levelRows: payloadResponse?.level_chart_rows || [],
                    genderRows: payloadResponse?.gender_performance_rows || [],
                    programmeRows: payloadResponse?.programme_performance_rows || [],
                },
                cardNarratives: payloadResponse?.card_narratives || {},
                narrativeDiagnostics: payloadResponse?.diagnostics || {},
            });

            hydrateSummaryCards(context, payloadResponse?.metrics || {});
            renderLevelTable({
                ...context,
                data: {
                    ...context.data,
                    levelRows: payloadResponse?.level_rows || [],
                },
            });
            context.data.levelRows = payloadResponse?.level_chart_rows || [];

            if (!storyBannerHydrated) {
                renderStoryBanner(
                    context.elements.storyBanner,
                    context.data.levelRows,
                    context.data.genderRows,
                    context.data.programmeRows,
                );
            }
            renderNarrativeDiagnostics(context);

            const controllers = [
                initialiseGenderSection(context),
                initialisePassTrendSection(context),
                initialiseTopProgrammeSection(context),
            ];
            const resizeCharts = () => {
                controllers.forEach((controller) => {
                    controller.resize();
                });
            };

            initialiseChartResizeHandling(controllers, resizeCharts);
            initialiseFullscreenControls(context.elements.fullscreenButtons, resizeCharts);
        })
        .catch(() => {
            setAcademicLevelShellErrorState(shellContext);
        });
};
