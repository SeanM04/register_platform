import { initialiseProgrammesNarrative } from "./narratives.js";
import {
    buildAnimationConfig,
    buildGradient,
    buildHiddenAxisPointerStyle,
    buildTooltipBase,
    buildTooltipMarkup,
    formatChartLabel,
    initialiseChart,
} from "./shared.js";

const HIGH_RISK = "High Risk";
const MEDIUM_RISK = "Medium Risk";

const isSeriesVisible = (selectedState, seriesName) => selectedState?.[seriesName] !== false;

const getVisibleProgrammeTotal = (row, selectedState) => {
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
    rows.reduce((maxValue, row) => Math.max(maxValue, getVisibleProgrammeTotal(row, selectedState)), 0),
);

const buildTotalLabel = (selectedState, seriesName) => {
    const highRiskVisible = isSeriesVisible(selectedState, HIGH_RISK);
    const mediumRiskVisible = isSeriesVisible(selectedState, MEDIUM_RISK);
    const showLabel = seriesName === MEDIUM_RISK
        ? mediumRiskVisible
        : highRiskVisible && !mediumRiskVisible;

    return {
        show: showLabel,
        position: "top",
        distance: 10,
        color: "#163a63",
        fontSize: 12,
        fontWeight: 800,
        formatter: (params) => {
            const visibleTotal = getVisibleProgrammeTotal(params.data.raw, selectedState);
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

    return buildTooltipMarkup(row.programme, [
        ...(highRiskVisible ? [{ label: HIGH_RISK, value: row.high_risk }] : []),
        ...(mediumRiskVisible ? [{ label: MEDIUM_RISK, value: row.medium_risk }] : []),
        {
            label: highRiskVisible && mediumRiskVisible ? "Watchlist total" : "Visible total",
            value: getVisibleProgrammeTotal(row, selectedState),
        },
        { label: "Share of watchlist", value: `${row.share_pct}%` },
        { label: "Faculty", value: row.faculty },
    ]);
};

const buildHighRiskBorderRadius = (row, selectedState) => {
    const mediumRiskVisible = isSeriesVisible(selectedState, MEDIUM_RISK);
    return mediumRiskVisible && Number(row.medium_risk || 0) > 0
        ? [0, 0, 10, 10]
        : [10, 10, 10, 10];
};

const buildMediumRiskBorderRadius = (row, selectedState) => {
    const highRiskVisible = isSeriesVisible(selectedState, HIGH_RISK);
    return highRiskVisible && Number(row.high_risk || 0) > 0
        ? [10, 10, 0, 0]
        : [10, 10, 10, 10];
};

const buildProgrammeSeries = (rows, selectedState) => {
    const series = [];
    const hasHighRisk = rows.some((row) => Number(row.high_risk || 0) > 0);
    const hasMediumRisk = rows.some((row) => Number(row.medium_risk || 0) > 0);

    if (hasHighRisk) {
        series.push({
            name: HIGH_RISK,
            type: "bar",
            stack: "risk-programme",
            clip: false,
            barMaxWidth: 56,
            data: rows.map((row) => ({
                value: row.high_risk,
                raw: row,
                itemStyle: {
                    color: buildGradient("#082340", "#1c4e80"),
                    borderRadius: buildHighRiskBorderRadius(row, selectedState),
                },
            })),
            label: buildTotalLabel(selectedState, HIGH_RISK),
        });
    }

    if (hasMediumRisk) {
        series.push({
            name: MEDIUM_RISK,
            type: "bar",
            stack: "risk-programme",
            clip: false,
            barMaxWidth: 56,
            data: rows.map((row) => ({
                value: row.medium_risk,
                raw: row,
                itemStyle: {
                    color: buildGradient("#1f78b4", "#67c3e5"),
                    borderRadius: buildMediumRiskBorderRadius(row, selectedState),
                },
            })),
            label: buildTotalLabel(selectedState, MEDIUM_RISK),
        });
    }

    return series;
};

const buildProgrammesOption = (rows, selectedState = null) => {
    const hasHighRisk = rows.some((row) => Number(row.high_risk || 0) > 0);
    const hasMediumRisk = rows.some((row) => Number(row.medium_risk || 0) > 0);

    return {
        ...buildAnimationConfig(rows),
        color: ["#163a63", "#67c3e5"],
        grid: {
            top: 40,
            right: 24,
            bottom: 90,
            left: 52,
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
            type: "category",
            data: rows.map((row) => formatChartLabel(row.programme, 18)),
            axisLine: {
                lineStyle: {
                    color: "rgba(148, 163, 184, 0.34)",
                },
            },
            axisTick: {
                show: false,
            },
            axisLabel: {
                color: "#64748b",
                fontSize: 10,
                margin: 16,
                interval: 0,
                rotate: 20,
            },
        },
        yAxis: {
            type: "value",
            minInterval: 1,
            max: buildSelectedAxisMax(rows, selectedState),
            axisTick: {
                show: false,
            },
            axisLine: {
                show: false,
            },
            axisLabel: {
                color: "#64748b",
                fontSize: 11,
                fontWeight: 600,
                margin: 12,
            },
            splitLine: {
                lineStyle: {
                    color: "rgba(148, 163, 184, 0.18)",
                    type: "dashed",
                },
            },
        },
        series: buildProgrammeSeries(rows, selectedState),
    };
};

const buildProgrammesLegendPatch = (rows, selectedState) => ({
    tooltip: {
        formatter: buildTooltipFormatter(selectedState),
    },
    yAxis: {
        max: buildSelectedAxisMax(rows, selectedState),
    },
    series: buildProgrammeSeries(rows, selectedState).map((series) => ({
        name: series.name,
        label: series.label,
        data: series.data,
    })),
});

export const initialiseProgrammesSection = (context) => {
    const { data, elements, flags } = context;
    initialiseProgrammesNarrative(elements, data.programmeRows, data.cardNarratives, flags);

    const chart = initialiseChart(
        "risk-programmes-chart",
        data.programmeRows,
        buildProgrammesOption,
        "No programme concentration is available for the current filters.",
        (rows) => rows.some((row) => Number(row.total || 0) > 0),
    );

    if (chart) {
        chart.on("legendselectchanged", (event) => {
            chart.setOption(buildProgrammesLegendPatch(data.programmeRows, event.selected), {
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
