import {
    PROGRAMME_COLORS,
    buildGradient,
    buildTooltipBase,
    buildTooltipMarkup,
    createEmptyController,
    echartsLib,
    formatCount,
    setChartFallback,
} from "./shared.js?v=20260405-programmes-progressive01";
import { initialiseDepartmentNarrative } from "./narratives.js?v=20260405-programmes-progressive01";

export const initialiseDepartmentSection = (context) => {
    initialiseDepartmentNarrative(context.elements, context.data.departmentRows, context.data.cardNarratives, context.flags);

    const element = context.elements.departmentsChart;
    const rows = context.data.departmentRows;

    if (!element) {
        return createEmptyController();
    }
    if (!echartsLib) {
        setChartFallback(element, "ECharts could not load. The programme register is still available.");
        return createEmptyController();
    }
    if (!rows.length) {
        setChartFallback(element, "No department concentration data is available for the current filters.");
        return createEmptyController();
    }

    element.classList.remove("is-empty");
    element.textContent = "";

    const chart = echartsLib.init(element);
    const sortedRows = [...rows].sort((left, right) => right.registrations - left.registrations || left.department.localeCompare(right.department));

    chart.setOption({
        animationDuration: 650,
        animationDurationUpdate: 250,
        grid: {
            containLabel: true,
            left: 84,
            right: 96,
            top: 20,
            bottom: 58,
        },
        tooltip: {
            ...buildTooltipBase("item"),
            formatter: (params) => {
                const row = sortedRows[params.dataIndex];
                return buildTooltipMarkup(row.department, [
                    { label: "Faculty", value: row.faculty },
                    { label: "Registrations", value: formatCount(row.registrations) },
                    { label: "Programmes", value: formatCount(row.programme_count) },
                    { label: "Pass rate", value: row.pass_rate },
                ]);
            },
        },
        xAxis: {
            type: "value",
            name: "Registrations",
            nameLocation: "middle",
            nameGap: 36,
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: {
                color: "#5c718f",
                fontSize: 11,
            },
            nameTextStyle: {
                color: "#5c718f",
                fontSize: 12,
                fontWeight: 700,
                padding: [12, 0, 0, 0],
            },
            splitLine: {
                lineStyle: {
                    color: "rgba(140, 168, 194, 0.2)",
                    type: "dashed",
                },
            },
        },
        yAxis: {
            type: "category",
            inverse: true,
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: {
                color: "#1c4573",
                fontSize: 11.5,
                fontWeight: 700,
                margin: 12,
            },
            data: sortedRows.map((row) => row.axis_label || row.department),
        },
        series: [
            {
                type: "bar",
                data: sortedRows.map((row) => row.registrations),
                barWidth: 22,
                label: {
                    show: true,
                    position: "right",
                    color: PROGRAMME_COLORS.ink,
                    fontSize: 10,
                    fontWeight: 700,
                    formatter: (params) => {
                        const row = sortedRows[params.dataIndex];
                        return `${row.programme_count} programmes`;
                    },
                },
                itemStyle: {
                    borderRadius: 0,
                    color: buildGradient(PROGRAMME_COLORS.teal, PROGRAMME_COLORS.mint, "horizontal"),
                },
            },
        ],
    });

    return {
        getChart: () => chart,
        resize: () => chart.resize(),
    };
};
