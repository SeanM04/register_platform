import {
    buildAnimationConfig,
    buildGradient,
    buildHiddenAxisPointerStyle,
    buildTooltipBase,
    buildTooltipMarkup,
    formatChartLabel,
    initialiseChart,
} from "./shared.js";
import { initialiseProgrammeNarrative } from "./narratives.js";

const SERIES_DEFINITIONS = [
    {
        key: "male",
        name: "Male",
        color: () => buildGradient("#082340", "#1f4f88"),
    },
    {
        key: "female",
        name: "Female",
        color: () => buildGradient("#2b7ea2", "#4fb0d1"),
    },
    {
        key: "unspecified",
        name: "Unspecified",
        color: () => buildGradient("#7b8ea6", "#b0bdcb"),
    },
];

const getVisibleSeriesDefinitions = (rows) => SERIES_DEFINITIONS.filter(
    (definition) => rows.some((row) => Number(row[definition.key] || 0) > 0),
);

const buildProgrammeMixDataZoom = (rows) => {
    const visibleCount = 8;
    if (rows.length <= visibleCount) {
        return [];
    }

    return [
        {
            type: "inside",
            yAxisIndex: 0,
            startValue: 0,
            endValue: visibleCount - 1,
            filterMode: "weakFilter",
        },
    ];
};

const buildProgrammeMixSeries = (rows, visibleSeriesDefinitions) => {
    const lastSeriesKey = visibleSeriesDefinitions[visibleSeriesDefinitions.length - 1]?.key;

    return visibleSeriesDefinitions.map((definition, index) => ({
        name: definition.name,
        type: "bar",
        stack: "cohort",
        barWidth: 18,
        itemStyle: {
            color: definition.color(),
            borderWidth: 0,
            borderColor: "transparent",
        },
        label: definition.key === lastSeriesKey ? {
            show: true,
            position: "right",
            color: "#082340",
            fontWeight: 700,
            formatter: ({ dataIndex }) => rows[dataIndex]?.total ?? "",
        } : undefined,
        emphasis: {
            focus: "series",
            itemStyle: {
                borderWidth: 0,
                borderColor: "transparent",
            },
        },
        data: rows.map((row) => row[definition.key]),
    }));
};

const buildProgrammeMixChartOption = (rows, chartWidth = 0) => {
    const visibleSeriesDefinitions = getVisibleSeriesDefinitions(rows);
    const isCompact = chartWidth > 0 ? chartWidth < 1080 : false;
    const isNarrow = chartWidth > 0 ? chartWidth < 860 : false;

    return {
        ...buildAnimationConfig(rows),
        axisPointer: buildHiddenAxisPointerStyle(),
        grid: { top: 16, right: rows.length > 8 ? 30 : 20, bottom: 18, left: 170, containLabel: true },
        dataZoom: buildProgrammeMixDataZoom(rows),
        legend: {
            top: 0,
            left: "center",
            textStyle: { color: "#4b5563", fontSize: 12 },
            data: visibleSeriesDefinitions.map((definition) => definition.name),
        },
        tooltip: {
            ...buildTooltipBase("item"),
            formatter: (params) => {
                const row = rows[params.dataIndex];
                return buildTooltipMarkup(row.programme, [
                    { label: "Male", value: row.male },
                    { label: "Female", value: row.female },
                    ...(visibleSeriesDefinitions.some((definition) => definition.key === "unspecified")
                        ? [{ label: "Unspecified", value: row.unspecified }]
                        : []),
                    { label: "Total", value: row.total },
                ], { maxWidth: 240 });
            },
        },
        xAxis: {
            type: "value",
            axisPointer: buildHiddenAxisPointerStyle(),
            minInterval: 1,
            splitLine: { show: false },
        },
        yAxis: {
            type: "category",
            data: rows.map((row) => row.programme_code || row.programme),
            axisPointer: buildHiddenAxisPointerStyle(),
            axisTick: { show: false },
            axisLine: { show: false },
            axisLabel: {
                color: "#082340",
                fontWeight: 600,
                width: 160,
                overflow: "truncate",
                formatter: (value) => formatChartLabel(value, isNarrow ? 12 : isCompact ? 14 : 16),
            },
        },
        series: buildProgrammeMixSeries(rows, visibleSeriesDefinitions),
    };
};

export const initialiseProgrammeMixSection = (context) => {
    const { cardNarratives, programmeRows } = context.data;
    initialiseProgrammeNarrative(context.elements, programmeRows, cardNarratives, context.flags);

    const chart = initialiseChart(
        "demographic-programme-chart",
        programmeRows,
        (rows) => buildProgrammeMixChartOption(rows, 0),
        "No programme demographic data matched the current filters.",
        (rows) => rows.some((row) => Number(row.total || 0) > 0),
    );

    return {
        getChart: () => chart,
        resize: () => {
            if (!chart) {
                return;
            }
            chart.resize();
            chart.setOption(buildProgrammeMixChartOption(programmeRows, chart.getWidth()), true);
        },
    };
};
