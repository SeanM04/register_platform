import {
    isDrillDownModalOpen,
    showDrillDownErrorModal,
    showLoadingDrillDownModal,
    showDrillDownModal,
} from "../home/drilldown_modal.js?v=20260601-drilldown-numeric-align01";

const DEFAULT_DRILLDOWN_PAGE_SIZE = 10;
let activeAcademicLevelDrillDownToken = 0;

const buildRequestUrl = (endpoint, params = {}) => {
    const requestUrl = new URL(endpoint, window.location.origin);
    const currentUrl = new URL(window.location.href);

    currentUrl.searchParams.forEach((value, key) => {
        requestUrl.searchParams.set(key, value);
    });

    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && String(value).trim()) {
            requestUrl.searchParams.set(key, String(value).trim());
        }
    });

    return requestUrl;
};

const fetchDrillDownPayload = async (endpoint, params = {}) => {
    const response = await fetch(buildRequestUrl(endpoint, params), {
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

export const cancelAcademicLevelDrillDownRequests = () => {
    activeAcademicLevelDrillDownToken += 1;
};

export const openAcademicLevelDrillDown = async (context, { chartKey, bucketKey, label }) => {
    cancelAcademicLevelDrillDownRequests();

    let currentPageSize = DEFAULT_DRILLDOWN_PAGE_SIZE;
    const requestToken = activeAcademicLevelDrillDownToken;
    const endpoint = context?.config?.drilldownUrl;
    const safeLabel = String(label || "Selected").trim() || "Selected";
    const loadingTitle = `${safeLabel} Drill-Down`;
    const loadingSubtitle = `Loading records for ${safeLabel.toLowerCase()}.`;

    if (!endpoint || !chartKey || !bucketKey) {
        showDrillDownErrorModal(loadingTitle, "This chart drill-down is not available right now.");
        return;
    }

    const loadPage = async (page, pageSize = currentPageSize, nextChartKey = chartKey, nextBucketKey = bucketKey) => {
        currentPageSize = pageSize || DEFAULT_DRILLDOWN_PAGE_SIZE;
        showLoadingDrillDownModal(loadingTitle, loadingSubtitle);

        try {
            const payload = await fetchDrillDownPayload(endpoint, {
                chart: nextChartKey,
                bucket: nextBucketKey,
                page,
                page_size: currentPageSize,
            });

            if (requestToken !== activeAcademicLevelDrillDownToken || !isDrillDownModalOpen()) {
                return;
            }

            showDrillDownModal(payload, [], {
                onPageChange: (newPage) => loadPage(newPage, currentPageSize, nextChartKey, nextBucketKey),
                onPageSizeChange: (newPageSize) => loadPage(1, newPageSize, nextChartKey, nextBucketKey),
                onNavigate: (target) => {
                    if (!target?.chart || !target?.bucket) {
                        return;
                    }
                    loadPage(1, currentPageSize, target.chart, target.bucket);
                },
            });
        } catch (error) {
            if (requestToken !== activeAcademicLevelDrillDownToken || !isDrillDownModalOpen()) {
                return;
            }

            showDrillDownErrorModal(loadingTitle, "The selected records could not be loaded right now.");
        }
    };

    await loadPage(1, currentPageSize);
};
