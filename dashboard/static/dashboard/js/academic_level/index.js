import { createAcademicLevelContext, updateAcademicLevelContext } from "./context.js";
import { initialiseFullscreenControls } from "./fullscreen.js";
import { initialiseGenderSection } from "./gender.js";
import { renderStoryBanner } from "./narratives.js";
import { initialisePassTrendSection } from "./pass_trend.js";
import { initialiseAcademicLevelSearch } from "./search.js";
import { initialiseTopProgrammeSection } from "./top_programme.js";
import { escapeTooltipHtml } from "./shared.js";

// Pagination state - make it globally accessible
const paginationState = {
    allRows: [],
    currentPage: 1,
    pageSize: 10,
    totalPages: 1,
};

// Store the initial table data globally so we can render it anytime
let initialTableData = null;

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

// Pagination helper functions
const calculatePagination = (totalItems, pageSize, currentPage) => {
    const totalPages = Math.ceil(totalItems / pageSize) || 1;
    const currentPageClamped = Math.min(Math.max(1, currentPage), totalPages);
    const start = (currentPageClamped - 1) * pageSize;
    const end = Math.min(start + pageSize, totalItems);
    
    return {
        totalPages,
        currentPage: currentPageClamped,
        start,
        end,
        totalItems,
    };
};

const renderPaginationControls = () => {
    const { totalPages, currentPage, totalItems, start, end } = calculatePagination(
        paginationState.allRows.length,
        paginationState.pageSize,
        paginationState.currentPage
    );

    const paginationText = document.getElementById("level-pagination-text");
    const firstBtn = document.getElementById("level-page-first");
    const prevBtn = document.getElementById("level-page-prev");
    const nextBtn = document.getElementById("level-page-next");
    const lastBtn = document.getElementById("level-page-last");
    const pagesContainer = document.getElementById("level-pagination-pages");
    const pageSizeSelect = document.getElementById("level-page-size");

    if (!paginationText || !firstBtn || !prevBtn || !nextBtn || !lastBtn || !pagesContainer) {
        return;
    }

    // Update info text
    if (totalItems === 0) {
        paginationText.textContent = "No records to display";
    } else {
        paginationText.textContent = `Showing ${start + 1} to ${end} of ${totalItems} records`;
    }

    // Update button states
    firstBtn.disabled = currentPage === 1;
    prevBtn.disabled = currentPage === 1;
    nextBtn.disabled = currentPage === totalPages;
    lastBtn.disabled = currentPage === totalPages;

    // Render page numbers (show max 5 pages)
    pagesContainer.innerHTML = "";
    const maxVisiblePages = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
    
    if (endPage - startPage < maxVisiblePages - 1) {
        startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }

    for (let page = startPage; page <= endPage; page++) {
        const pageBtn = document.createElement("button");
        pageBtn.className = `level-pagination-btn${page === currentPage ? " is-active" : ""}`;
        pageBtn.textContent = page;
        pageBtn.addEventListener("click", () => goToPage(page));
        pagesContainer.appendChild(pageBtn);
    }

    // Update page size select
    if (pageSizeSelect) {
        pageSizeSelect.value = paginationState.pageSize;
    }
};

const goToPage = (page) => {
    const { totalPages } = calculatePagination(
        paginationState.allRows.length,
        paginationState.pageSize,
        page
    );

    paginationState.currentPage = Math.min(Math.max(1, page), totalPages);
    renderPaginatedTable();
    renderPaginationControls();
};

const changePageSize = (newSize) => {
    paginationState.pageSize = parseInt(newSize, 10) || 10;
    paginationState.currentPage = 1;
    renderPaginatedTable();
    renderPaginationControls();
};

const renderPaginatedTable = () => {
    console.log('[Academic Level] renderPaginatedTable called');
    
    // Wait a bit to ensure DOM is ready after accordion animation
    setTimeout(() => {
        const { start, end } = calculatePagination(
            paginationState.allRows.length,
            paginationState.pageSize,
            paginationState.currentPage
        );

        const paginatedRows = paginationState.allRows.slice(start, end);
        
        console.log('[Academic Level] About to render', paginatedRows.length, 'rows');
        
        // Get fresh context with current DOM references
        const context = createAcademicLevelContext();
        
        console.log('[Academic Level] Fresh context created, tableBody exists:', !!context.elements.levelTableBody);
        
        renderLevelTable({
            ...context,
            data: {
                ...context.data,
                levelRows: paginatedRows,
            },
        });
        
        renderPaginationControls();
    }, 50);
};

const initialisePagination = () => {
    const firstBtn = document.getElementById("level-page-first");
    const prevBtn = document.getElementById("level-page-prev");
    const nextBtn = document.getElementById("level-page-next");
    const lastBtn = document.getElementById("level-page-last");
    const pageSizeSelect = document.getElementById("level-page-size");

    if (firstBtn) {
        firstBtn.addEventListener("click", () => goToPage(1));
    }
    if (prevBtn) {
        prevBtn.addEventListener("click", () => goToPage(paginationState.currentPage - 1));
    }
    if (nextBtn) {
        nextBtn.addEventListener("click", () => goToPage(paginationState.currentPage + 1));
    }
    if (lastBtn) {
        lastBtn.addEventListener("click", () => {
            const { totalPages } = calculatePagination(
                paginationState.allRows.length,
                paginationState.pageSize,
                paginationState.currentPage
            );
            goToPage(totalPages);
        });
    }
    if (pageSizeSelect) {
        pageSizeSelect.addEventListener("change", (e) => changePageSize(e.target.value));
    }
};

// NEW: Render table immediately without any delays or context dependencies
const renderTableImmediately = (rows) => {
    const tableBody = document.querySelector('.level-table tbody');
    if (!tableBody) {
        console.error('[Academic Level] CRITICAL: Table tbody not found in DOM!');
        return;
    }

    if (!rows || rows.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td class="level-empty" colspan="6">No academic level data matched the current filters.</td>
            </tr>
        `.trim();
        console.log('[Academic Level] Rendered empty state');
        return;
    }

    const { start, end } = calculatePagination(
        rows.length,
        paginationState.pageSize,
        paginationState.currentPage
    );

    const paginatedRows = rows.slice(start, end);
    
    tableBody.innerHTML = paginatedRows.map((row) => `
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

    console.log(`[Academic Level] Table rendered immediately with ${paginatedRows.length} rows (page ${paginationState.currentPage})`);
};

// Simplified re-render for accordion expand - just call immediate render
const handleAccordionExpand = () => {
    console.log('[Academic Level] Accordion expanded, refreshing table display');
    if (initialTableData && initialTableData.length > 0) {
        renderTableImmediately(initialTableData);
        renderPaginationControls();
    }
};

const renderLevelTable = (context) => {
    // Always query the DOM directly to ensure we get the current element
    const tableBody = document.querySelector('.level-table tbody');
    
    if (!tableBody) {
        console.warn('[Academic Level] Table body element not found in DOM');
        return;
    }

    console.log('[Academic Level] Found tableBody element:', tableBody);

    const rows = context.data.levelRows || [];
    if (!rows.length) {
        console.log('[Academic Level] No rows to render');
        tableBody.innerHTML = `
            <tr>
                <td class="level-empty" colspan="6">No academic level data matched the current filters.</td>
            </tr>
        `.trim();
        return;
    }

    console.log('[Academic Level] Rendering table with', rows.length, 'rows into tbody');
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
    
    console.log('[Academic Level] Table rendered successfully, tbody innerHTML length:', tableBody.innerHTML.length);
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
                console.error('[Academic Level] Empty payload response');
                setAcademicLevelShellErrorState(shellContext);
                return;
            }

            console.log('[Academic Level] Payload received:', {
                hasLevelRows: !!payloadResponse?.level_rows,
                levelRowsCount: payloadResponse?.level_rows?.length || 0,
                hasMetrics: !!payloadResponse?.metrics,
                levelRows: payloadResponse?.level_rows
            });

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
            
            // Store all rows for pagination - ALWAYS keep this data
            const allLevelRows = payloadResponse?.level_rows || [];
            paginationState.allRows = allLevelRows;
            paginationState.currentPage = 1;
            paginationState.pageSize = 10;
            
            // Store globally for immediate access
            initialTableData = allLevelRows;
            
            console.log('[Academic Level] Storing table data:', {
                totalRows: allLevelRows.length,
                stored: !!initialTableData
            });
            
            // Render table IMMEDIATELY - don't wait for anything
            renderTableImmediately(allLevelRows);
            
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

            // Simple event listener - just re-render when accordion opens
            document.addEventListener('academic-level:table-visibility-changed', () => {
                console.log('[Academic Level] Table visibility changed - refreshing display');
                handleAccordionExpand();
            });
        })
        .catch((error) => {
            console.error('[Academic Level] Failed to load payload:', error);
            setAcademicLevelShellErrorState(shellContext);
        });
};
