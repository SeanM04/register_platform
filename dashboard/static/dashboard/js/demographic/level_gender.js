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
import { initialiseYearDistributionNarrative } from "./narratives.js";

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

const buildYearDistributionOption = (rows, chartWidth = 0) => {
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
            trigger: "item",
            backgroundColor: "rgba(255, 255, 255, 0.95)",
            borderWidth: 1,
            borderColor: "#ccc",
            padding: [8, 12],
            textStyle: {
                color: "#000000",
                fontSize: 12,
                fontWeight: 600,
            },
            formatter: (params) => {
                const dataIndex = params.dataIndex;
                const row = rows[dataIndex];
                if (!row) return '';
                
                const seriesName = params.seriesName;
                if (seriesName === 'Male') {
                    return `Male: ${row.male} (${row.male_share})`;
                } else if (seriesName === 'Female') {
                    return `Female: ${row.female} (${row.female_share})`;
                }
                return '';
            },
        },
        xAxis: {
            type: "category",
            data: rows.map((row) => row.year),
            axisPointer: buildHiddenAxisPointerStyle(),
            axisTick: { show: false },
            axisLine: { show: false },
            axisLabel: {
                interval: 0,
                rotate: isNarrow ? 32 : isCompact ? 20 : 0,
                color: "#082340",
                fontWeight: 600,
                fontSize: isNarrow ? 10 : 11,
                formatter: (value) => {
                    const raw = String(value ?? "").trim();
                    if (/^\d+$/.test(raw)) {
                        return `Year ${raw}`;
                    }
                    return formatChartLabel(value, isNarrow ? 10 : 14);
                },
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
                name: "Male",
                type: "bar",
                stack: "gender",
                barWidth: isNarrow ? 20 : isCompact ? 26 : 34,
                itemStyle: {
                    color: buildGradient("#082340", "#1f4f88"),
                },
                emphasis: {
                    itemStyle: {
                        color: buildGradient("#082340", "#2d8db6"),
                    },
                },
                                data: rows.map((row) => row.male),
            },
            {
                name: "Female",
                type: "bar",
                stack: "gender",
                barWidth: isNarrow ? 20 : isCompact ? 26 : 34,
                itemStyle: {
                    borderRadius: [6, 6, 0, 0],
                    color: buildGradient("#2b7ea2", "#4fb0d1"),
                },
                emphasis: {
                    itemStyle: {
                        borderRadius: [6, 6, 0, 0],
                        color: buildGradient("#2b7ea2", "#6fc3e3"),
                    },
                },
                                data: rows.map((row) => row.female),
            },
        ],
    };
};

const updateOverviewNarrative = (elements, rows, cardNarratives, flags) => {
    initialiseYearDistributionNarrative(elements, rows, cardNarratives, flags);
};

export const initialiseYearDistributionSection = (context) => {
    const { cardNarratives, yearDistributionRows } = context.data;
    const { elements, flags } = context;
    initialiseYearDistributionNarrative(elements, yearDistributionRows, cardNarratives, flags);

    const chart = initialiseChart(
        "demographic-year-distribution-chart",
        yearDistributionRows,
        buildYearDistributionOption,
        "No year distribution data matched the current filters.",
        (rows) => Boolean(rows && rows.length),
    );

    updateOverviewNarrative(elements, yearDistributionRows, cardNarratives, flags);

    return {
        getChart: () => chart,
        resize: () => {
            if (!chart) {
                return;
            }
            chart.resize();
            chart.setOption(buildYearDistributionOption(yearDistributionRows, chart.getWidth()), true);
        },
    };
};
