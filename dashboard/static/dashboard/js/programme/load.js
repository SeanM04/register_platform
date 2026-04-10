import {
    PROGRAMME_COLORS,
    buildGradient,
    buildTooltipBase,
    buildTooltipMarkup,
    createEmptyController,
    echartsLib,
    formatCount,
    setChartFallback,
    wrapAxisLabel,
} from "./shared.js?v=20260405-programmes-progressive01";
import { initialiseLoadNarrative } from "./narratives.js?v=20260405-programmes-progressive01";

export const initialiseLoadSection = (context) => {
    initialiseLoadNarrative(context.elements, context.data.topLoadRows, context.data.cardNarratives, context.flags);

    const element = context.elements.loadChart;
    const rows = context.data.topLoadRows;

    if (!element) {
        return createEmptyController();
    }
    if (!echartsLib) {
        setChartFallback(element, "ECharts could not load. The programme register is still available.");
        return createEmptyController();
    }
    if (!rows.length) {
        setChartFallback(element, "No visible programme load data is available for the current filters.");
        return createEmptyController();
    }

    element.classList.remove("is-empty");
    element.textContent = "";

    const chart = echartsLib.init(element);
    const sortedRows = [...rows].sort((left, right) => right.registrations - left.registrations || left.name.localeCompare(right.name));

    chart.setOption({
        animationDuration: 650,
        animationDurationUpdate: 250,
        grid: {
            left: 210,
            right: 88,
            top: 20,
            bottom: 36,
        },
        tooltip: {
            ...buildTooltipBase("item"),
            formatter: (params) => {
                const row = sortedRows[params.dataIndex];
                return buildTooltipMarkup(row.name, [
                    { label: "Registrations", value: formatCount(row.registrations) },
                    { label: "Share", value: row.share },
                    { label: "Students", value: formatCount(row.students) },
                    { label: "Pass rate", value: row.pass_rate },
                    { label: "Department", value: row.department },
                ]);
            },
        },
        xAxis: {
            type: "value",
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
            type: "category",
            inverse: true,
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: {
                color: "#1c4573",
                fontSize: 10.5,
                fontWeight: 700,
                margin: 14,
                formatter: (value) => wrapAxisLabel(value, { maxLineLength: 18, maxLines: 2 }),
            },
            data: sortedRows.map((row) => row.name),
        },
        series: [
            {
                type: "bar",
                data: sortedRows.map((row) => row.registrations),
                barWidth: 18,
                label: {
                    show: true,
                    position: "right",
                    color: PROGRAMME_COLORS.ink,
                    fontSize: 9,
                    fontWeight: 700,
                    formatter: (params) => {
                        const row = sortedRows[params.dataIndex];
                        return `${row.share} (${row.pass_rate})`;
                    },
                },
                itemStyle: {
                    borderRadius: [0, 12, 12, 0],
                    color: buildGradient(PROGRAMME_COLORS.navy, PROGRAMME_COLORS.sky, "horizontal"),
                },
            },
        ],
    });

    return {
        getChart: () => chart,
        resize: () => chart.resize(),
    };
};
