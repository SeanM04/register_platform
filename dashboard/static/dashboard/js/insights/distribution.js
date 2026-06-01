import { initialiseDistributionNarrative } from "./narratives.js?v=20260403-insights-story02";
import { openInsightsDrillDown } from "./drilldown.js?v=20260601-drilldown-numeric-align01";
import {
    buildAnimationConfig,
    buildGradient,
    buildTooltipBase,
    buildTooltipMarkup,
    initialiseChart,
} from "./shared.js?v=20260403-insights-story02";

const TONE_GRADIENTS = {
    critical: ["#dc2626", "#ef4444"],
    high: ["#ea580c", "#f97316"],
    moderate: ["#facc15", "#fde047"],
    low: ["#16a34a", "#22c55e"],
};

const buildDistributionOption = (rows, width) => ({
    ...buildAnimationConfig(rows),
    grid: {
        top: 32,
        right: 16,
        bottom: width < 720 ? 56 : 34,
        left: 20,
        containLabel: true,
    },
    tooltip: {
        ...buildTooltipBase("item"),
        formatter: (params) => {
            const row = params.data.raw;
            return buildTooltipMarkup(row.label, [
                { label: "Students", value: row.count },
                { label: "Share of active cohort", value: `${row.percent}%` },
            ]);
        },
    },
    xAxis: {
        type: "category",
        data: rows.map((row) => row.label),
        axisTick: {
            show: false,
        },
        axisLine: {
            lineStyle: {
                color: "#d6e3ef",
            },
        },
        axisLabel: {
            color: "#52677c",
            fontSize: width < 720 ? 10 : 11,
            interval: 0,
            rotate: 0,
        },
    },
    yAxis: {
        type: "value",
        minInterval: 1,
        axisLine: {
            show: false,
        },
        axisTick: {
            show: false,
        },
        axisLabel: {
            color: "#64748b",
            fontSize: 11,
        },
        splitLine: {
            lineStyle: {
                color: "rgba(148, 163, 184, 0.18)",
                type: "dashed",
            },
        },
    },
    series: [
        {
            type: "bar",
            barMaxWidth: 28,
            data: rows.map((row) => {
                const [startColor, endColor] = TONE_GRADIENTS[row.tone] || TONE_GRADIENTS.moderate;
                return {
                    value: row.count,
                    raw: row,
                    itemStyle: {
                        borderRadius: [6, 6, 0, 0],
                        color: buildGradient(startColor, endColor, "vertical"),
                    },
                };
            }),
            label: {
                show: true,
                position: "top",
                color: "#163a63",
                fontSize: 12,
                fontWeight: 800,
                formatter: (params) => params.data.value,
            },
        },
    ],
});

export const initialiseDistributionSection = (context) => {
    const { data, elements, flags } = context;
    initialiseDistributionNarrative(elements, data.distributionRows, data.cardNarratives, flags);

    const chart = initialiseChart(
        "insight-distribution-chart",
        data.distributionRows,
        buildDistributionOption,
        "No institutional risk distribution is available for the current filters.",
        (rows) => rows.some((row) => Number(row.count || 0) > 0),
    );

    // Add drilldown click handler
    if (chart) {
        chart.on("click", (params) => {
            const row = params.data?.raw || data.distributionRows[params.dataIndex];
            if (row && row.key) {
                openInsightsDrillDown(context, {
                    chartKey: "risk_distribution",
                    bucketKey: row.key,
                    label: row.label,
                });
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
