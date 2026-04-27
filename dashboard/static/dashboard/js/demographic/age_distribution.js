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
import { initialiseAgeDistributionNarrative } from "./narratives.js";

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

const buildAgeDistributionOption = (rows, chartWidth = 0) => {
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
                console.log('Age tooltip triggered:', params);
                const dataIndex = params.dataIndex;
                const row = rows[dataIndex];
                console.log('Selected age row:', row);
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
            data: rows.map((row) => row.age_group),
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
                    color: buildGradient("#2b7ea2", "#4fb0d1"),
                },
                emphasis: {
                    itemStyle: {
                        color: buildGradient("#2b7ea2", "#6fc3e3"),
                    },
                },
                                data: rows.map((row) => row.female),
            },
        ],
    };
};

const updateOverviewNarrative = (elements, rows, cardNarratives, flags) => {
    initialiseAgeDistributionNarrative(elements, rows, cardNarratives, flags);
};

export const initialiseAgeDistributionSection = (context) => {
    const { cardNarratives, ageDistributionRows } = context.data;
    const { elements, flags } = context;
    initialiseAgeDistributionNarrative(elements, ageDistributionRows, cardNarratives, flags);

    const chart = initialiseChart(
        "demographic-age-distribution-chart",
        ageDistributionRows,
        buildAgeDistributionOption,
        "No age distribution data matched the current filters.",
        (rows) => rows.some((row) => Number(row.total || 0) > 0),
    );

    updateOverviewNarrative(elements, ageDistributionRows, cardNarratives, flags);

    return {
        getChart: () => chart,
        resize: () => {
            if (!chart) {
                return;
            }
            chart.resize();
            chart.setOption(buildAgeDistributionOption(ageDistributionRows, chart.getWidth()), true);
        },
    };
};
