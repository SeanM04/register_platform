import { initialiseDistributionNarrative } from "./narratives.js";
import {
    buildAnimationConfig,
    buildGradient,
    buildTooltipBase,
    buildTooltipMarkup,
    initialiseChart,
} from "./shared.js";

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
        bottom: width < 720 ? 52 : 30,
        left: 20,
        containLabel: true,
    },
    tooltip: {
        ...buildTooltipBase("item"),
        formatter: (params) => {
            const row = params.data.raw;
            return buildTooltipMarkup(row.label, [
                { label: "Students", value: row.count },
                { label: "Share of visible cohort", value: `${row.share_pct}%` },
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
            rotate: width < 720 ? 16 : 0,
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
        "risk-distribution-chart",
        data.distributionRows,
        buildDistributionOption,
        "No risk distribution is available for the current filters.",
        (rows) => rows.some((row) => Number(row.count || 0) > 0),
    );

    // Add click event handler for drill-down
    if (chart) {
        chart.on('click', (params) => {
            const row = params.data.raw;
            if (row && row.key) {
                const currentUrl = new URL(window.location.href);
                currentUrl.searchParams.set('risk_band', row.key);
                window.location.href = `/risk/band/${row.key}/?${currentUrl.searchParams.toString()}`;
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
