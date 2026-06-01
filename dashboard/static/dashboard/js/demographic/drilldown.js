/**
 * Drilldown functionality for demographic charts.
 */

import {
    isDrillDownModalOpen,
    showDrillDownErrorModal,
    showLoadingDrillDownModal,
    showDrillDownModal,
} from "./drilldown_modal.js?v=20260601-drilldown-numeric-align01";

const DEFAULT_DRILLDOWN_PAGE_SIZE = 10;
let activeDemographicDrillDownToken = 0;

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

export const cancelDemographicDrillDownRequests = () => {
    activeDemographicDrillDownToken += 1;
};

export const openDemographicDrillDown = async (context, { chartKey, bucketKey, label }) => {
    cancelDemographicDrillDownRequests();

    let currentPageSize = DEFAULT_DRILLDOWN_PAGE_SIZE;
    const requestToken = activeDemographicDrillDownToken;
    const safeLabel = String(label || "Selected").trim() || "Selected";
    const title = `${safeLabel} Students`;
    const subtitle = `Loading students in ${safeLabel.toLowerCase()} selection.`;
    const endpoint = context?.config?.drilldownUrl;

    if (!endpoint || !chartKey || !bucketKey) {
        showDrillDownErrorModal(title, "This chart drill-down is not available right now.");
        return;
    }

    showLoadingDrillDownModal(title, subtitle);

    const loadPage = async (page, pageSize = currentPageSize, nextChartKey = chartKey, nextBucketKey = bucketKey) => {
        currentPageSize = pageSize || DEFAULT_DRILLDOWN_PAGE_SIZE;
        showLoadingDrillDownModal(title, subtitle);

        try {
            const payload = await fetchDrillDownPayload(endpoint, {
                chart: nextChartKey,
                bucket: nextBucketKey,
                page,
                page_size: currentPageSize,
            });

            if (requestToken !== activeDemographicDrillDownToken || !isDrillDownModalOpen()) {
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
            if (requestToken !== activeDemographicDrillDownToken || !isDrillDownModalOpen()) {
                return;
            }

            console.error("Demographic drilldown error:", error);
            showDrillDownErrorModal(title, "Failed to load drilldown data. Please try again.");
        }
    };

    loadPage(1, currentPageSize);
};

// Chart click handlers
export const addDemographicDrilldownHandlers = (context) => {
    // Helper function to get ECharts instance from DOM element
    const getEChartsInstance = (element) => {
        if (!element) return null;
        return window.echarts?.getInstanceByDom(element);
    };

    // Gender chart handler
    const genderChartElement = context.elements.genderChart;
    if (genderChartElement) {
        const genderChart = getEChartsInstance(genderChartElement);
        if (genderChart) {
            genderChart.on('click', (params) => {
                console.log('Gender chart clicked:', params);
                // For gender charts, use params.name or params.seriesName
                const gender = params.name || params.seriesName || '';
                const genderLower = gender.toLowerCase();
                const label = `${gender.charAt(0).toUpperCase() + gender.slice(1)} Students`;
                
                if (gender) {
                    openDemographicDrillDown(context, {
                        chartKey: "gender",
                        bucketKey: genderLower,
                        label: label,
                    });
                }
            });
        }
    }

    // Year distribution chart handler
    const yearDistributionChartElement = context.elements.yearDistributionChart;
    if (yearDistributionChartElement) {
        const yearDistributionChart = getEChartsInstance(yearDistributionChartElement);
        if (yearDistributionChart) {
            yearDistributionChart.on('click', (params) => {
                const year = String(params.name ?? '').trim();
                if (year && /^\d+$/.test(year)) {
                    openDemographicDrillDown(context, {
                        chartKey: "year_distribution",
                        bucketKey: year,
                        label: `Year ${year} students`,
                    });
                }
            });
        }
    }

    // Age distribution chart handler
    const ageDistributionChartElement = context.elements.ageDistributionChart;
    if (ageDistributionChartElement) {
        const ageDistributionChart = getEChartsInstance(ageDistributionChartElement);
        if (ageDistributionChart) {
            ageDistributionChart.on('click', (params) => {
                console.log('Age distribution chart clicked:', params);
                // For age distribution charts, use params.name or params.data.age_group
                const ageGroup = params.name || (params.data && params.data.age_group) || '';
                
                if (ageGroup) {
                    openDemographicDrillDown(context, {
                        chartKey: "age_distribution",
                        bucketKey: ageGroup,
                        label: `Students in ${ageGroup} Age Group`,
                    });
                }
            });
        }
    }

    // Programme chart handler
    const programmeChartElement = context.elements.programmeChart;
    if (programmeChartElement) {
        const programmeChart = getEChartsInstance(programmeChartElement);
        if (programmeChart) {
            programmeChart.on('click', (params) => {
                const rows = context?.data?.programmeRows || [];
                const programmeRow = rows[params.dataIndex] || null;
                const programme = String(
                    programmeRow?.programme
                    || params.data?.programme
                    || params.data?.name
                    || params.name
                    || "",
                ).trim();
                
                if (programme) {
                    openDemographicDrillDown(context, {
                        chartKey: "programme",
                        bucketKey: programme,
                        label: `Students in ${programme}`,
                    });
                }
            });
        }
    }

    // Location mix chart handler
    const locationMixChartElement = context.elements.locationMixChart;
    if (locationMixChartElement) {
        const locationMixChart = getEChartsInstance(locationMixChartElement);
        if (locationMixChart) {
            locationMixChart.on('click', (params) => {
                const data = params.data;
                const location = String(data?.location || data?.place || "").trim();
                const gender = String(data?.gender || data?.genderLabel || "").trim().toLowerCase();

                if (location && gender) {
                    const bucketKey = `${location}|${gender}`;
                    const label = `${gender.charAt(0).toUpperCase() + gender.slice(1)} Students from ${location}`;
                    
                    openDemographicDrillDown(context, {
                        chartKey: "location_mix",
                        bucketKey: bucketKey,
                        label: label,
                    });
                }
            });
        }
    }

    // Programme gender chart handler
    const programmeGenderChartElement = context.elements.programmeGenderChart;
    if (programmeGenderChartElement) {
        const programmeGenderChart = getEChartsInstance(programmeGenderChartElement);
        if (programmeGenderChart) {
            programmeGenderChart.on('click', (params) => {
                console.log('Programme gender chart clicked:', params);
                const rows = context?.data?.programmeGenderRows || [];
                const programmeRow = rows[params.dataIndex] || null;
                const programme = String(programmeRow?.programme || params.name || '').trim();
                const gender = String(params.seriesName || '').trim().toLowerCase();

                if (programme && (gender === "male" || gender === "female")) {
                    const bucketKey = `${programme}|${gender}`;
                    const label = `${gender.charAt(0).toUpperCase() + gender.slice(1)} Students in ${programme}`;

                    openDemographicDrillDown(context, {
                        chartKey: "programme_gender",
                        bucketKey: bucketKey,
                        label: label,
                    });
                }
            });
        }
    }
};
