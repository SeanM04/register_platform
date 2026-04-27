import {
    PROGRAMME_COLORS,
    buildTooltipBase,
    buildTooltipMarkup,
    createEmptyController,
    echartsLib,
    formatCount,
    formatProgrammeName,
    setChartFallback,
} from "./shared.js?v=20260414-msc-support01";
import { initialisePerformanceNarrative } from "./narratives.js?v=20260405-programmes-progressive01";
import { openProgrammeDrillDown } from "./drilldown.js?v=20260416-programme-drilldown19";

const buildSymbolSize = (students, maxStudents) => {
    if (!maxStudents) {
        return 18;
    }
    return 12 + ((Number(students || 0) / maxStudents) * 24);
};

export const initialisePerformanceSection = (context) => {
    initialisePerformanceNarrative(context.elements, context.data.performanceRows, context.data.cardNarratives, context.flags);

    const element = context.elements.performanceChart;
    const rows = context.data.performanceRows;

    if (!element) {
        return createEmptyController();
    }
    if (!echartsLib) {
        setChartFallback(element, "ECharts could not load. The programme register is still available.");
        return createEmptyController();
    }
    if (!rows.length) {
        setChartFallback(element, "No scale-versus-pass-rate data is available for the current filters.");
        return createEmptyController();
    }

    element.classList.remove("is-empty");
    element.textContent = "";

    const chart = echartsLib.init(element);
    const maxRegistrations = Math.max(...rows.map((row) => Number(row.registrations || 0)));
    const maxStudents = Math.max(...rows.map((row) => Number(row.students || 0)));

    chart.setOption({
        animationDuration: 650,
        animationDurationUpdate: 250,
        grid: {
            containLabel: true,
            left: 64,
            right: 26,
            top: 22,
            bottom: 46,
        },
        tooltip: {
            ...buildTooltipBase("item"),
            formatter: (params) => {
                const row = params.data.row;
                return buildTooltipMarkup(formatProgrammeName(row.name), [
                    { label: "Registrations", value: formatCount(row.registrations) },
                    { label: "Share", value: row.share },
                    { label: "Students", value: formatCount(row.students) },
                    { label: "Pass rate", value: row.pass_rate },
                    { label: "Average mark", value: formatCount(row.average_mark) },
                ]);
            },
        },
        xAxis: {
            type: "value",
            min: 0,
            max: Math.max(Math.round(maxRegistrations * 1.15), 10),
            name: "Registrations",
            nameLocation: "middle",
            nameGap: 28,
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: {
                color: "#5c718f",
                fontSize: 11,
            },
            splitLine: {
                lineStyle: {
                    color: "rgba(140, 168, 194, 0.2)",
                    type: "dashed",
                },
            },
        },
        yAxis: {
            type: "value",
            min: 0,
            max: 100,
            name: "Pass rate %",
            nameGap: 30,
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: {
                color: "#5c718f",
                fontSize: 11,
                formatter: (value) => `${value}%`,
            },
            splitLine: {
                lineStyle: {
                    color: "rgba(140, 168, 194, 0.16)",
                    type: "dashed",
                },
            },
        },
        series: [
            {
                type: "scatter",
                data: rows.map((row) => ({
                    value: [row.registrations, row.pass_rate_value],
                    row,
                    symbolSize: buildSymbolSize(row.students, maxStudents),
                })),
                itemStyle: {
                    color: PROGRAMME_COLORS.teal,
                    borderColor: "#ffffff",
                    borderWidth: 2,
                    shadowBlur: 16,
                    shadowColor: "rgba(47, 128, 172, 0.28)",
                },
                emphasis: {
                    scale: 1.06,
                    itemStyle: {
                        color: PROGRAMME_COLORS.navy,
                    },
                },
                label: {
                    show: true,
                    position: "top",
                    color: PROGRAMME_COLORS.ink,
                    fontSize: 9,
                    fontWeight: 700,
                    formatter: (params) => params.data.row.share,
                    distance: 5,
                },
            },
        ],
    });

    // Add drill-down click handler
    chart.on("click", (params) => {
        const row = params.data.row;
        if (row && row.name) {
            openProgrammeDrillDown(context, {
                chartKey: "programme_load",
                bucketKey: row.name,
                label: formatProgrammeName(row.name),
            });
        }
    });

    return {
        getChart: () => chart,
        resize: () => chart.resize(),
    };
};
