import { initialiseFacultyLoadNarrative } from "./narratives.js?v=20260403-insights-story02";
import {
    buildAnimationConfig,
    buildGradient,
    buildTooltipBase,
    buildTooltipMarkup,
    buildVerticalCategoryZoom,
    formatChartLabel,
    initialiseChart,
} from "./shared.js?v=20260403-insights-story02";

const buildAxisMax = (value) => {
    const maxValue = Number(value?.max || 0);
    if (!maxValue) {
        return 1;
    }

    return Math.max(Math.ceil(maxValue * 1.16), maxValue + 2);
};

const buildFacultyLoadOption = (rows) => ({
    ...buildAnimationConfig(rows),
    grid: {
        top: 12,
        right: 72,
        bottom: 34,
        left: 136,
        containLabel: false,
    },
    tooltip: {
        ...buildTooltipBase("item"),
        formatter: (params) => {
            const row = params.data.raw;
            return buildTooltipMarkup(row.label, [
                { label: "Registrations", value: row.registrations },
                { label: "Share of scope", value: `${row.share_pct}%` },
            ]);
        },
    },
    xAxis: {
        type: "value",
        minInterval: 1,
        max: buildAxisMax,
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
        data: rows.map((row) => formatChartLabel(row.label, 18)),
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
    series: [
        {
            type: "bar",
            clip: false,
            barWidth: 18,
            data: rows.map((row) => ({
                value: row.registrations,
                raw: row,
                itemStyle: {
                    color: buildGradient("#082340", "#5fb7dc"),
                    borderRadius: [0, 10, 10, 0],
                },
            })),
            label: {
                show: true,
                position: "right",
                distance: 8,
                color: "#163a63",
                fontSize: 12,
                fontWeight: 800,
                formatter: (params) => params.data.value,
            },
        },
    ],
});

export const initialiseFacultyLoadSection = (context) => {
    const { data, elements, flags } = context;
    initialiseFacultyLoadNarrative(elements, data.facultyLoadRows, data.cardNarratives, flags);

    const chart = initialiseChart(
        "insight-faculty-load-chart",
        data.facultyLoadRows,
        buildFacultyLoadOption,
        "No faculty load concentration is available for the current filters.",
        (rows) => rows.some((row) => Number(row.registrations || 0) > 0),
    );

    return {
        getChart: () => chart,
        resize: () => {
            if (chart) {
                chart.resize();
            }
        },
    };
};
