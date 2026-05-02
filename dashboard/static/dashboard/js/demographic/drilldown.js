/**
 * Drilldown functionality for demographic charts.
 */

import {
    isDrillDownModalOpen,
    showDrillDownErrorModal,
    showLoadingDrillDownModal,
    showDrillDownModal,
} from "./drilldown_modal.js?v=20260501-demographic-drilldown01";

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

            if (requestToken !== activeDemographicDrillDownToken || !isDrillDownModalOpen()) {
                return;
            }

            showDrillDownModal(payload, [], {
                onPageChange: (newPage) => loadPage(newPage, currentPageSize),
                onPageSizeChange: (newPageSize) => loadPage(1, newPageSize),
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

    // Location chart handler
    const locationChartElement = context.elements.locationChart;
    if (locationChartElement) {
        const locationChart = getEChartsInstance(locationChartElement);
        if (locationChart) {
            locationChart.on('click', (params) => {
                console.log('Location chart clicked:', params);
                // For location charts, use params.name or params.data.place
                const location = params.name || (params.data && params.data.place) || '';
                
                if (location) {
                    openDemographicDrillDown(context, {
                        chartKey: "locations",
                        bucketKey: location,
                        label: `Students from ${location}`,
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
                console.log('Year distribution chart clicked:', params);
                const year = params.seriesName.replace("Year ", "");
                
                openDemographicDrillDown(context, {
                    chartKey: "year_distribution",
                    bucketKey: year,
                    label: `Year ${year} Students`,
                });
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
                console.log('Programme chart clicked:', params);
                console.log('Programme chart params data:', params.data);
                console.log('Programme chart params name:', params.name);
                
                // For programme charts, try multiple sources for the programme name
                let programme = '';
                if (params.name && params.name !== 'ENGP') {
                    programme = params.name;
                } else if (params.data && params.data.programme) {
                    programme = params.data.programme;
                } else if (params.data && params.data.name) {
                    programme = params.data.name;
                } else if (params.seriesName && params.seriesName !== 'ENGP') {
                    programme = params.seriesName;
                }
                
                console.log('Extracted programme:', programme);
                
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
                console.log('Location mix chart clicked:', params);
                // For location mix, we need to extract location and gender from the data
                const data = params.data;
                if (data && data.location && data.gender) {
                    const bucketKey = `${data.location}|${data.gender}`;
                    const label = `${data.gender.charAt(0).toUpperCase() + data.gender.slice(1)} Students from ${data.location}`;
                    
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
                // For programme gender, we need to extract programme and gender from the data
                const data = params.data;
                if (data && data.programme && data.gender) {
                    const bucketKey = `${data.programme}|${data.gender}`;
                    const label = `${data.gender.charAt(0).toUpperCase() + data.gender.slice(1)} Students in ${data.programme}`;
                    
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
