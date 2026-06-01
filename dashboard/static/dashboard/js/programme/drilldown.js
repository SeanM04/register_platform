/* Programme Drill-down Module */

import {
    closeDrillDownModal,
    showDrillDownErrorModal,
    showDrillDownModal,
    showLoadingDrillDownModal,
} from "../home/drilldown_modal.js?v=20260601-drilldown-numeric-align01";

const DEFAULT_DRILLDOWN_PAGE_SIZE = 10;
let activeProgrammeDrillDownToken = 0;

export const cancelProgrammeDrillDownRequests = () => {
    activeProgrammeDrillDownToken += 1;
};

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
        method: "GET",
        headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
    });

    if (!response.ok) {
        throw new Error(`Drill-down request failed: ${response.status}`);
    }

    return response.json();
};

export const openProgrammeDrillDown = async (context, { chartKey, bucketKey, label }) => {
    cancelProgrammeDrillDownRequests();

    const endpoint = context?.config?.drilldownUrl;
    const safeLabel = String(label || "Selected").trim() || "Selected";
    const requestToken = activeProgrammeDrillDownToken;
    let currentPageSize = DEFAULT_DRILLDOWN_PAGE_SIZE;

    if (!endpoint || !chartKey || !bucketKey) {
        showDrillDownErrorModal(`${safeLabel} Students`, "This chart drill-down is not available right now.");
        return;
    }

    const loadPage = async (
        page,
        pageSize = currentPageSize,
        nextChartKey = chartKey,
        nextBucketKey = bucketKey,
        nextLabel = safeLabel,
    ) => {
        currentPageSize = pageSize || DEFAULT_DRILLDOWN_PAGE_SIZE;
        const subtitle = `Loading the students behind ${String(nextLabel).toLowerCase()}.`;
        showLoadingDrillDownModal(`${nextLabel} Students`, subtitle);

        try {
            const payload = await fetchDrillDownPayload(endpoint, {
                chart: nextChartKey,
                bucket: nextBucketKey,
                page,
                page_size: currentPageSize,
            });

            if (requestToken !== activeProgrammeDrillDownToken) {
                return;
            }

            closeDrillDownModal();
            showDrillDownModal(payload, [], {
                onPageChange: (newPage) => loadPage(newPage, currentPageSize, nextChartKey, nextBucketKey, nextLabel),
                onNavigate: (target) => {
                    if (!target?.chart || !target?.bucket) {
                        return;
                    }
                    loadPage(1, currentPageSize, target.chart, target.bucket, target.label || target.value || nextLabel);
                },
            });
        } catch (error) {
            if (requestToken !== activeProgrammeDrillDownToken) {
                return;
            }

            showDrillDownErrorModal(
                `${safeLabel} Students`,
                `The students behind ${safeLabel.toLowerCase()} could not be loaded right now.`,
            );
        }
    };

    await loadPage(1, currentPageSize, chartKey, bucketKey, safeLabel);
};
