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
import { initialiseProgrammeGenderNarrative } from "./narratives.js";

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

const buildProgrammeGenderOption = (rows, chartWidth = 0) => {
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
                return buildTooltipMarkup(row.programme, [
                    { label: "Code", value: row.programme_code },
                    { label: "Male", value: `${row.male} (${row.male_share})` },
                    { label: "Female", value: `${row.female} (${row.female_share})` },
                    { label: "Total", value: row.total },
                ]);
            },
        },
        xAxis: {
            type: "category",
            data: rows.map((row) => row.programme_code),
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
                    borderRadius: [0, 0, 6, 6],
                    color: buildGradient("#082340", "#1f4f88"),
                },
                emphasis: {
                    itemStyle: {
                        borderRadius: [0, 0, 6, 6],
                        color: buildGradient("#082340", "#2d8db6"),
                    },
                },
                label: {
                    show: true,
                    position: "inside",
                    color: "#ffffff",
                    fontWeight: 700,
                    fontSize: 10,
                    formatter: ({ dataIndex, value }) => {
                        const share = rows[dataIndex]?.male_share ?? "";
                        const total = rows[dataIndex]?.male ?? 0;
                        // Show label even for small values
                        return total > 0 ? share : "";
                    },
                    distance: 2,
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
                label: {
                    show: true,
                    position: "inside",
                    color: "#ffffff",
                    fontWeight: 700,
                    fontSize: 10,
                    formatter: ({ dataIndex, value }) => {
                        const share = rows[dataIndex]?.female_share ?? "";
                        const total = rows[dataIndex]?.female ?? 0;
                        // Show label even for small values
                        return total > 0 ? share : "";
                    },
                    distance: 2,
                },
                data: rows.map((row) => row.female),
            },
        ],
    };
};

const updateOverviewNarrative = (elements, rows, cardNarratives, flags) => {
    initialiseProgrammeGenderNarrative(elements, rows, cardNarratives, flags);
};

export const initialiseProgrammeGenderSection = (context) => {
    const { cardNarratives, programmeGenderRows } = context.data;
    const { elements, flags } = context;
    initialiseProgrammeGenderNarrative(elements, programmeGenderRows, cardNarratives, flags);

    const chart = initialiseChart(
        "demographic-programme-gender-chart",
        programmeGenderRows,
        buildProgrammeGenderOption,
        "No programme gender distribution data matched the current filters.",
        (rows) => rows.some((row) => Number(row.total || 0) > 0),
    );

    updateOverviewNarrative(elements, programmeGenderRows, cardNarratives, flags);

    return {
        getChart: () => chart,
        resize: () => {
            if (!chart) {
                return;
            }
            chart.resize();
            chart.setOption(buildProgrammeGenderOption(programmeGenderRows, chart.getWidth()), true);
        },
    };
};
