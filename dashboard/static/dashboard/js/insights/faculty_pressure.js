import { initialiseFacultyPressureNarrative } from "./narratives.js?v=20260403-insights-story02";
import {
    buildAnimationConfig,
    buildGradient,
    buildHiddenAxisPointerStyle,
    buildTooltipBase,
    buildTooltipMarkup,
    buildVerticalCategoryZoom,
    initialiseChart,
} from "./shared.js?v=20260403-insights-story02";

const HIGH_RISK = "High Risk";
const MEDIUM_RISK = "Medium Risk";

const isSeriesVisible = (selectedState, seriesName) => selectedState?.[seriesName] !== false;

const getVisibleTotal = (row, selectedState) => {
    const highRisk = isSeriesVisible(selectedState, HIGH_RISK) ? Number(row.high_risk || 0) : 0;
    const mediumRisk = isSeriesVisible(selectedState, MEDIUM_RISK) ? Number(row.medium_risk || 0) : 0;
    return highRisk + mediumRisk;
};

const buildAxisMax = (maxValue) => {
    if (!maxValue) {
        return 1;
    }

    return Math.max(Math.ceil(maxValue * 1.16), maxValue + 2);
};

const buildSelectedAxisMax = (rows, selectedState) => buildAxisMax(
    rows.reduce((maxValue, row) => Math.max(maxValue, getVisibleTotal(row, selectedState)), 0),
);

const buildTotalLabel = (selectedState, seriesName) => {
    const highRiskVisible = isSeriesVisible(selectedState, HIGH_RISK);
    const mediumRiskVisible = isSeriesVisible(selectedState, MEDIUM_RISK);
    const showLabel = seriesName === MEDIUM_RISK
        ? mediumRiskVisible
        : highRiskVisible && !mediumRiskVisible;

    return {
        show: showLabel,
        position: "right",
        distance: 8,
        color: "#163a63",
        fontSize: 12,
        fontWeight: 800,
        formatter: (params) => {
            const visibleTotal = getVisibleTotal(params.data.raw, selectedState);
            return visibleTotal ? visibleTotal : "";
        },
    };
};

const buildTooltipFormatter = (selectedState) => (params) => {
    const row = params.find((entry) => entry?.data?.raw)?.data?.raw;
    if (!row) {
        return "";
    }

    const highRiskVisible = isSeriesVisible(selectedState, HIGH_RISK);
    const mediumRiskVisible = isSeriesVisible(selectedState, MEDIUM_RISK);

    return buildTooltipMarkup(row.label, [
        ...(highRiskVisible ? [{ label: HIGH_RISK, value: row.high_risk }] : []),
        ...(mediumRiskVisible ? [{ label: MEDIUM_RISK, value: row.medium_risk }] : []),
        {
            label: highRiskVisible && mediumRiskVisible ? "Flagged total" : "Visible total",
            value: getVisibleTotal(row, selectedState),
        },
        { label: "Share of watchlist", value: `${row.share_pct}%` },
    ]);
};

const buildHighRiskBorderRadius = (row, selectedState) => {
    const mediumRiskVisible = isSeriesVisible(selectedState, MEDIUM_RISK);
    return mediumRiskVisible && Number(row.medium_risk || 0) > 0
        ? [10, 0, 0, 10]
        : [10, 10, 10, 10];
};

const buildMediumRiskBorderRadius = (row, selectedState) => {
    const highRiskVisible = isSeriesVisible(selectedState, HIGH_RISK);
    return highRiskVisible && Number(row.high_risk || 0) > 0
        ? [0, 10, 10, 0]
        : [10, 10, 10, 10];
};

const buildPressureSeries = (rows, selectedState) => {
    const series = [];
    const hasHighRisk = rows.some((row) => Number(row.high_risk || 0) > 0);
    const hasMediumRisk = rows.some((row) => Number(row.medium_risk || 0) > 0);

    if (hasHighRisk) {
        series.push({
            name: HIGH_RISK,
            type: "bar",
            stack: "faculty-pressure",
            clip: false,
            barMaxWidth: 28,
            data: rows.map((row) => ({
                value: row.high_risk,
                raw: row,
                itemStyle: {
                    color: buildGradient("#082340", "#1c4e80"),
                },
            })),
            label: buildTotalLabel(selectedState, HIGH_RISK),
        });
    }

    if (hasMediumRisk) {
        series.push({
            name: MEDIUM_RISK,
            type: "bar",
            stack: "faculty-pressure",
            clip: false,
            barMaxWidth: 28,
            data: rows.map((row) => ({
                value: row.medium_risk,
                raw: row,
                itemStyle: {
                    color: buildGradient("#1f78b4", "#67c3e5"),
                },
            })),
            label: buildTotalLabel(selectedState, MEDIUM_RISK),
        });
    }

    return series;
};

const buildFacultyPressureOption = (rows, selectedState = null) => {
    const hasHighRisk = rows.some((row) => Number(row.high_risk || 0) > 0);
    const hasMediumRisk = rows.some((row) => Number(row.medium_risk || 0) > 0);

    return {
        ...buildAnimationConfig(rows),
        color: ["#163a63", "#67c3e5"],
        grid: {
            top: 40,
            right: 72,
            bottom: 34,
            left: 136,
            containLabel: false,
        },
        legend: {
            data: [
                hasHighRisk ? HIGH_RISK : null,
                hasMediumRisk ? MEDIUM_RISK : null,
            ].filter(Boolean),
            top: 4,
            left: "center",
            textStyle: {
                color: "#52677c",
                fontSize: 11,
                fontWeight: 700,
            },
            itemWidth: 12,
            itemHeight: 12,
        },
        tooltip: {
            ...buildTooltipBase("axis"),
            axisPointer: buildHiddenAxisPointerStyle(),
            formatter: buildTooltipFormatter(selectedState),
        },
        xAxis: {
            type: "value",
            minInterval: 1,
            max: buildSelectedAxisMax(rows, selectedState),
            axisLine: {
                show: false,
            },
            axisTick: {
                show: false,
            },
            axisLabel: {
                color: "#64748b",
                fontSize: 11,
                margin: 12,
            },
            splitLine: {
                lineStyle: {
                    color: "rgba(148, 163, 184, 0.18)",
                    type: "dashed",
                },
            },
        },
        yAxis: {
            type: "category",
            inverse: true,
            data: rows.map((row) => row.label),
            axisTick: {
                show: false,
            },
            axisLine: {
                show: false,
            },
            axisLabel: {
                color: "#193a62",
                fontSize: 11,
                fontWeight: 700,
            },
        },
        dataZoom: buildVerticalCategoryZoom(rows, { visibleCount: 6 }),
        series: buildPressureSeries(rows, selectedState),
    };
};

const buildPressureLegendPatch = (rows, selectedState) => ({
    tooltip: {
        formatter: buildTooltipFormatter(selectedState),
    },
    xAxis: {
        max: buildSelectedAxisMax(rows, selectedState),
    },
    series: buildPressureSeries(rows, selectedState).map((series) => ({
        name: series.name,
        label: series.label,
        data: series.data,
    })),
});

export const initialiseFacultyPressureSection = (context) => {
    const { data, elements, flags } = context;
    initialiseFacultyPressureNarrative(elements, data.facultyPressureRows, data.cardNarratives, flags);

    const chart = initialiseChart(
        "insight-faculty-pressure-chart",
        data.facultyPressureRows,
        buildFacultyPressureOption,
        "No faculty pressure cluster is available for the current filters.",
        (rows) => rows.some((row) => Number(row.total || 0) > 0),
    );

    if (chart) {
        chart.on("legendselectchanged", (event) => {
            chart.setOption(buildPressureLegendPatch(data.facultyPressureRows, event.selected), {
                silent: true,
            });
        });
    }

    return {
        getChart: () => chart,
        resize: () => {
            if (chart) {
                chart.resize();
            }
        },
    };
};
