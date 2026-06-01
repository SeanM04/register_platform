import {
    isInsightsDrillDownModalOpen,
    showInsightsDrillDownErrorModal,
    showInsightsDrillDownLoadingModal,
    showInsightsDrillDownModal,
} from "./drilldown_modal.js?v=20260601-drilldown-numeric-align01";

const DEFAULT_DRILLDOWN_PAGE_SIZE = 10;
let activeInsightsDrillDownToken = 0;

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

export const cancelInsightsDrillDownRequests = () => {
    activeInsightsDrillDownToken += 1;
};

export const openInsightsDrillDown = async (context, { chartKey, bucketKey, label, drilldownType = "students" }) => {
    cancelInsightsDrillDownRequests();

    const endpoint = context?.config?.drilldownUrl;
    const safeLabel = String(label || "Selected").trim() || "Selected";
    const requestToken = activeInsightsDrillDownToken;
    let currentPageSize = DEFAULT_DRILLDOWN_PAGE_SIZE;

    if (!endpoint || !chartKey || !bucketKey) {
        showInsightsDrillDownErrorModal(`${safeLabel}`, "This chart drill-down is not available right now.");
        return;
    }

    const getSubtitle = () => {
        switch (drilldownType) {
            case "departments": return `Loading departments within ${safeLabel.toLowerCase()}...`;
            case "programmes": return `Loading programmes within ${safeLabel.toLowerCase()}...`;
            default: return `Loading the students behind ${safeLabel.toLowerCase()}.`;
        }
    };

    const subtitle = getSubtitle();
    showInsightsDrillDownLoadingModal(`${safeLabel}`, subtitle);

    const loadPage = async (page, pageSize = currentPageSize) => {
        currentPageSize = pageSize || DEFAULT_DRILLDOWN_PAGE_SIZE;
        showInsightsDrillDownLoadingModal(`${safeLabel}`, subtitle);

        try {
            const params = {
                chart: chartKey,
                bucket: bucketKey,
                type: drilldownType,
            };
            
            if (drilldownType === "students") {
                params.page = page;
                params.page_size = currentPageSize;
            }

            const payload = await fetchDrillDownPayload(endpoint, params);

            if (requestToken !== activeInsightsDrillDownToken || !isInsightsDrillDownModalOpen()) {
                return;
            }

            showInsightsDrillDownModal(payload, {
                onPageChange: drilldownType === "students" ? loadPage : null,
                onNavigate: handleHierarchicalNavigation,
            });
        } catch (error) {
            if (requestToken !== activeInsightsDrillDownToken || !isInsightsDrillDownModalOpen()) {
                return;
            }

            showInsightsDrillDownErrorModal(
                `${safeLabel}`,
                `The data for ${safeLabel.toLowerCase()} could not be loaded right now.`,
            );
        }
    };

    const handleHierarchicalNavigation = (item, type) => {
        let nextChartKey, nextBucketKey, nextLabel, nextType;
        
        if (type === "departments") {
            // Navigate to programmes
            nextChartKey = "faculty_department";
            nextBucketKey = `${bucketKey}|${item.label}`;
            nextLabel = item.label;
            nextType = "programmes";
        } else if (type === "programmes") {
            // Navigate to students
            // Use the same chart type as the original for consistency
            nextChartKey = chartKey === "faculty_pressure" ? "faculty_pressure" : "faculty_programme";
            nextBucketKey = item.label;
            nextLabel = item.label;
            nextType = "students";
        }
        
        if (nextChartKey && nextBucketKey) {
            openInsightsDrillDown(context, {
                chartKey: nextChartKey,
                bucketKey: nextBucketKey,
                label: nextLabel,
                drilldownType: nextType,
            });
        }
    };

    await loadPage(1, currentPageSize);
};
