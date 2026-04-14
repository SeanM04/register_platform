import { initialiseDriversNarrative } from "./narratives.js";
import {
    buildAnimationConfig,
    buildGradient,
    buildTooltipBase,
    buildTooltipMarkup,
    buildVerticalCategoryZoom,
    formatChartLabel,
    initialiseChart,
} from "./shared.js";

const buildAxisMax = (value) => {
    const maxValue = Number(value?.max || 0);
    if (!maxValue) {
        return 1;
    }

    return Math.max(Math.ceil(maxValue * 1.16), maxValue + 2);
};

const buildDriversOption = (rows) => ({
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
                { label: "Flagged students", value: row.count },
                { label: "Share of watchlist", value: `${row.share_pct}%` },
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
            barMaxWidth: 28,
            data: rows.map((row) => ({
                value: row.count,
                raw: row,
                itemStyle: {
                    color: buildGradient("#0b4c6d", "#5fb7dc"),
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

export const initialiseDriversSection = (context) => {
    const { data, elements, flags } = context;
    initialiseDriversNarrative(elements, data.driverRows, data.cardNarratives, flags);

    const chart = initialiseChart(
        "risk-drivers-chart",
        data.driverRows,
        buildDriversOption,
        "No shared driver pattern is available for the current filters.",
        (rows) => rows.some((row) => Number(row.count || 0) > 0),
    );

    // Add click event handler for drill-down
    if (chart) {
        chart.on('click', (params) => {
            const row = params.data.raw;
            if (row && row.key) {
                const currentUrl = new URL(window.location.href);
                currentUrl.searchParams.set('risk_driver', row.key);
                window.location.href = `/risk/driver/${row.key}/?${currentUrl.searchParams.toString()}`;
            }
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
