import {
    buildAnimationConfig,
    buildAxisPointerConfig,
    buildGradient,
    buildHiddenAxisPointerStyle,
    buildTooltipBase,
    buildTooltipMarkup,
    formatChartLabel,
    initialiseChart,
} from "./shared.js";
import { openDemographicDrillDown } from "./drilldown.js?v=20260601-drilldown-click-reliability01";
import { initialiseLocationNarrative, setActionText } from "./narratives.js";

const DETAIL_DIMENSIONS = [
    {
        key: "male",
        label: "Male",
        color: () => buildGradient("#082340", "#1f4f88"),
    },
    {
        key: "female",
        label: "Female",
        color: () => buildGradient("#2b7ea2", "#4fb0d1"),
    },
    {
        key: "unspecified",
        label: "Unspecified",
        color: () => buildGradient("#7b8ea6", "#b0bdcb"),
    },
];

const setHintMarkup = (element, hints) => {
    if (!element) {
        return;
    }

    element.innerHTML = hints.map((hint) => `
        <span class="demographic-chart-hint${hint.kind ? ` is-${hint.kind}` : ""}">
            ${hint.label}
        </span>
    `).join("").trim();
};

const formatPercentage = (count, total) => `${Math.round((Number(count || 0) / Math.max(Number(total || 0), 1)) * 100)}%`;

const getDetailRows = (locationRow) => DETAIL_DIMENSIONS
    .filter((dimension) => Number(locationRow?.[dimension.key] || 0) > 0)
    .map((dimension) => ({
        key: dimension.key,
        label: dimension.label,
        count: Number(locationRow[dimension.key] || 0),
        share: formatPercentage(locationRow[dimension.key], locationRow.total),
        color: dimension.color(),
    }));

const getLeadDetailIndex = (detailRows) => {
    if (!detailRows.length) {
        return -1;
    }

    return detailRows.reduce(
        (bestIndex, row, index, rows) => (row.count > rows[bestIndex].count ? index : bestIndex),
        0,
    );
};

const buildOverviewOption = (rows, chartWidth = 0) => {
    const isCompact = chartWidth > 0 ? chartWidth < 1080 : false;
    const isNarrow = chartWidth > 0 ? chartWidth < 860 : false;

    return {
        ...buildAnimationConfig(rows),
        axisPointer: buildHiddenAxisPointerStyle(),
        grid: {
            top: 22,
            right: 16,
            bottom: isNarrow ? 84 : isCompact ? 72 : 58,
            left: 20,
            containLabel: true,
        },
        tooltip: {
            ...buildTooltipBase("axis"),
            axisPointer: buildAxisPointerConfig("shadow"),
            formatter: (params) => {
                const row = rows[params[0].dataIndex];
                return buildTooltipMarkup(row.place, [
                    { label: "Students", value: row.count },
                    { label: "Share", value: row.share },
                ]);
            },
        },
        xAxis: {
            type: "category",
            data: rows.map((row) => row.place),
            axisPointer: buildHiddenAxisPointerStyle(),
            axisTick: { show: false },
            axisLine: { show: false },
            axisLabel: {
                interval: 0,
                rotate: isNarrow ? 32 : isCompact ? 20 : 0,
                color: "#082340",
                fontWeight: 600,
                fontSize: isNarrow ? 10 : 11,
                formatter: (value) => formatChartLabel(value, isNarrow ? 10 : 14),
            },
        },
        yAxis: {
            type: "value",
            axisPointer: buildHiddenAxisPointerStyle(),
            minInterval: 1,
            splitLine: { lineStyle: { color: "#e2e8f0" } },
        },
        series: [
            {
                name: "Students",
                type: "bar",
                barWidth: isNarrow ? 20 : isCompact ? 26 : 34,
                itemStyle: {
                    borderRadius: [6, 6, 0, 0],
                    color: buildGradient("#0d325d", "#4fb0d1"),
                },
                emphasis: {
                    itemStyle: {
                        borderRadius: [6, 6, 0, 0],
                        color: buildGradient("#082340", "#2d8db6"),
                    },
                },
                label: {
                    show: true,
                    position: "top",
                    color: "#082340",
                    fontWeight: 700,
                    formatter: ({ dataIndex }) => rows[dataIndex]?.count ?? "",
                },
                data: rows.map((row) => row.count),
            },
        ],
    };
};

const buildDetailOption = (locationRow, chartWidth = 0) => {
    const detailRows = getDetailRows(locationRow);
    const isCompact = chartWidth > 0 ? chartWidth < 900 : false;
    const isNarrow = chartWidth > 0 ? chartWidth < 680 : false;

    return {
        ...buildAnimationConfig(detailRows),
        axisPointer: buildHiddenAxisPointerStyle(),
        grid: {
            top: 24,
            right: 16,
            bottom: isNarrow ? 68 : 52,
            left: 20,
            containLabel: true,
        },
        tooltip: {
            ...buildTooltipBase("item"),
            alwaysShowContent: true,
            formatter: (params) => {
                const row = detailRows[params.dataIndex];
                return buildTooltipMarkup(`${locationRow.place} | ${row.label}`, [
                    { label: "Students", value: row.count },
                    { label: "Share of location", value: row.share },
                    { label: "Location total", value: locationRow.total },
                ], { maxWidth: 224 });
            },
        },
        xAxis: {
            type: "category",
            data: detailRows.map((row) => row.label),
            axisPointer: buildHiddenAxisPointerStyle(),
            axisTick: { show: false },
            axisLine: { show: false },
            axisLabel: {
                color: "#082340",
                fontWeight: 700,
                fontSize: isCompact ? 11 : 12,
            },
        },
        yAxis: {
            type: "value",
            axisPointer: buildHiddenAxisPointerStyle(),
            minInterval: 1,
            splitLine: { lineStyle: { color: "#e2e8f0" } },
        },
        series: [
            {
                name: "Students",
                type: "bar",
                barWidth: isNarrow ? 26 : isCompact ? 34 : 44,
                itemStyle: {
                    borderRadius: [6, 6, 0, 0],
                    color: ({ dataIndex }) => detailRows[dataIndex]?.color,
                },
                label: {
                    show: true,
                    position: "top",
                    color: "#082340",
                    fontWeight: 700,
                    formatter: ({ dataIndex }) => detailRows[dataIndex]?.count ?? "",
                },
                data: detailRows.map((row) => row.count),
            },
        ],
    };
};

const updateOverviewNarrative = (elements, rows, cardNarratives, flags) => {
    initialiseLocationNarrative(elements, rows, cardNarratives, flags);
    if (elements.locationReset) {
        elements.locationReset.classList.add("is-hidden");
    }
};

const updateDetailNarrative = (elements, locationRow) => {
    const detailRows = getDetailRows(locationRow);
    const leadRow = [...detailRows].sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))[0] || null;
    const secondRow = [...detailRows].sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))[1] || null;

    if (elements.locationCopy) {
        elements.locationCopy.textContent = leadRow && secondRow
            ? `${locationRow.place} now shows its internal gender split, with ${leadRow.label} leading at ${leadRow.share} and ${secondRow.label} following at ${secondRow.share}.`
            : leadRow
                ? `${locationRow.place} now shows its internal gender split, led by ${leadRow.label} at ${leadRow.share}.`
                : `No gender split is available for ${locationRow.place}.`;
    }
setHintMarkup(elements.locationHints, []);

    setActionText(
        elements.locationNote,
        `Showing the gender split for ${locationRow.place}. Use Back to locations to return to the ranked birth-location view.`,
    );

    if (elements.locationReset) {
        elements.locationReset.classList.remove("is-hidden");
    }
};

export const initialiseLocationSection = (context) => {
    const { cardNarratives, locationRows, locationMixRows } = context.data;
    const { elements, flags } = context;
    initialiseLocationNarrative(elements, locationRows, cardNarratives, flags);

    const chart = initialiseChart(
        "demographic-location-chart",
        locationRows,
        buildOverviewOption,
        "No birth-location data matched the current filters.",
        (rows) => rows.some((row) => Number(row.count || 0) > 0),
    );

    const locationMixByPlace = new Map(locationMixRows.map((row) => [row.place, row]));
    let selectedLocationPlace = "";

    const showDetailTooltip = (locationRow, dataIndex = -1) => {
        if (!chart || !locationRow) {
            return;
        }

        const detailRows = getDetailRows(locationRow);
        const tooltipIndex = dataIndex >= 0 ? dataIndex : getLeadDetailIndex(detailRows);
        if (tooltipIndex < 0) {
            return;
        }

        window.setTimeout(() => {
            chart.dispatchAction({
                type: "showTip",
                seriesIndex: 0,
                dataIndex: tooltipIndex,
            });
        }, 60);
    };

    const renderChart = () => {
        if (!chart) {
            return;
        }

        if (selectedLocationPlace) {
            const detailRow = locationMixByPlace.get(selectedLocationPlace);
            if (detailRow) {
                chart.setOption(buildDetailOption(detailRow, chart.getWidth()), true);
                chart.getDom().style.cursor = "pointer";
                return;
            }
        }

        chart.setOption(buildOverviewOption(locationRows, chart.getWidth()), true);
        chart.getDom().style.cursor = "pointer";
    };

    const resetLocationDrilldown = () => {
        selectedLocationPlace = "";
        renderChart();
        if (chart) {
            chart.dispatchAction({ type: "hideTip" });
        }
        updateOverviewNarrative(elements, locationRows, cardNarratives, flags);
    };

    if (chart) {
        chart.on("click", (params) => {
            if (selectedLocationPlace) {
                const detailRow = locationMixByPlace.get(selectedLocationPlace);
                if (!detailRow || params.componentType !== "series") {
                    return;
                }

                const genderRows = getDetailRows(detailRow);
                const genderRow = genderRows[params.dataIndex];
                if (!genderRow) {
                    showDetailTooltip(detailRow, params.dataIndex);
                    return;
                }

                openDemographicDrillDown(context, {
                    chartKey: "location_mix",
                    bucketKey: `${detailRow.place}|${genderRow.key}`,
                    label: `${genderRow.label} Students from ${detailRow.place}`,
                });
                return;
            }

            const clickedRow = locationRows[params.dataIndex];
            const detailRow = clickedRow ? locationMixByPlace.get(clickedRow.place) : null;
            if (!detailRow) {
                return;
            }

            selectedLocationPlace = detailRow.place;
            renderChart();
            updateDetailNarrative(elements, detailRow);
            showDetailTooltip(detailRow);
        });

        chart.on("mouseover", (params) => {
            if (!selectedLocationPlace || params.componentType !== "series") {
                return;
            }

            const detailRow = locationMixByPlace.get(selectedLocationPlace);
            if (!detailRow) {
                return;
            }

            showDetailTooltip(detailRow, params.dataIndex);
        });
    }

    if (elements.locationReset) {
        elements.locationReset.addEventListener("click", () => {
            resetLocationDrilldown();
        });
    }

    return {
        getChart: () => chart,
        resize: () => {
            if (!chart) {
                return;
            }
            chart.resize();
            renderChart();
        },
    };
};
