import {
    isRiskDrillDownModalOpen,
    showRiskDrillDownErrorModal,
    showRiskDrillDownLoadingModal,
    showRiskDrillDownModal,
} from "./drilldown_modal.js?v=20260414-risk-drilldown01";

const DEFAULT_DRILLDOWN_PAGE_SIZE = 10;
let activeRiskDrillDownToken = 0;

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

export const cancelRiskDrillDownRequests = () => {
    activeRiskDrillDownToken += 1;
};

export const openRiskDrillDown = async (context, { chartKey, bucketKey, label }) => {
    cancelRiskDrillDownRequests();

    const endpoint = context?.config?.drilldownUrl;
    const safeLabel = String(label || "Selected").trim() || "Selected";
    const requestToken = activeRiskDrillDownToken;
    let currentPageSize = DEFAULT_DRILLDOWN_PAGE_SIZE;

    if (!endpoint || !chartKey || !bucketKey) {
        showRiskDrillDownErrorModal(`${safeLabel} Students`, "This chart drill-down is not available right now.");
        return;
    }

    const subtitle = `Loading the students behind ${safeLabel.toLowerCase()}.`;
    showRiskDrillDownLoadingModal(`${safeLabel} Students`, subtitle);

    const loadPage = async (page, pageSize = currentPageSize) => {
        currentPageSize = pageSize || DEFAULT_DRILLDOWN_PAGE_SIZE;
        showRiskDrillDownLoadingModal(`${safeLabel} Students`, subtitle);

        try {
            const payload = await fetchDrillDownPayload(endpoint, {
                chart: chartKey,
                bucket: bucketKey,
                page,
                page_size: currentPageSize,
            });

            if (requestToken !== activeRiskDrillDownToken || !isRiskDrillDownModalOpen()) {
                return;
            }

            showRiskDrillDownModal(payload, {
                onPageChange: loadPage,
            });
        } catch (error) {
            if (requestToken !== activeRiskDrillDownToken || !isRiskDrillDownModalOpen()) {
                return;
            }

            showRiskDrillDownErrorModal(
                `${safeLabel} Students`,
                `The students behind ${safeLabel.toLowerCase()} could not be loaded right now.`,
            );
        }
    };

    await loadPage(1, currentPageSize);
};
