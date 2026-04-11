import {
    isDrillDownModalOpen,
    showDrillDownErrorModal,
    showLoadingDrillDownModal,
    showDrillDownModal,
} from "./drilldown_modal.js?v=20260411-home-drilldown01";

const DEFAULT_DRILLDOWN_PAGE_SIZE = 100;
let activeOverviewDrillDownToken = 0;

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

export const cancelOverviewDrillDownRequests = () => {
    activeOverviewDrillDownToken += 1;
};

export const openOverviewDrillDown = async (context, { chartKey, bucketKey, label }) => {
    cancelOverviewDrillDownRequests();

    let currentPageSize = DEFAULT_DRILLDOWN_PAGE_SIZE;
    const requestToken = activeOverviewDrillDownToken;
    const safeLabel = String(label || "Selected").trim() || "Selected";
    const title = `${safeLabel} Students`;
    const subtitle = `Loading the students in the ${safeLabel.toLowerCase()} selection.`;
    const endpoint = context?.config?.drilldownUrl;

    if (!endpoint || !chartKey || !bucketKey) {
        showDrillDownErrorModal(title, "This chart drill-down is not available right now.");
        return;
    }

    showLoadingDrillDownModal(title, subtitle);

    const loadPage = async (page, pageSize = currentPageSize) => {
        currentPageSize = pageSize || DEFAULT_DRILLDOWN_PAGE_SIZE;
        showLoadingDrillDownModal(title, subtitle);

        try {
            const payload = await fetchDrillDownPayload(endpoint, {
                chart: chartKey,
                bucket: bucketKey,
                page,
                page_size: currentPageSize,
            });

            if (requestToken !== activeOverviewDrillDownToken || !isDrillDownModalOpen()) {
                return;
            }

            showDrillDownModal(payload, [], {
                onPageChange: loadPage,
                onPageSizeChange: (newPageSize) => loadPage(1, newPageSize),
            });
        } catch (error) {
            if (requestToken !== activeOverviewDrillDownToken || !isDrillDownModalOpen()) {
                return;
            }

            showDrillDownErrorModal(title, `The students in the ${safeLabel.toLowerCase()} selection could not be loaded right now.`);
        }
    };

    try {
        await loadPage(1, currentPageSize);
    } catch (error) {
        if (requestToken !== activeOverviewDrillDownToken || !isDrillDownModalOpen()) {
            return;
        }

        showDrillDownErrorModal(title, `The students in the ${safeLabel.toLowerCase()} selection could not be loaded right now.`);
    }
};
