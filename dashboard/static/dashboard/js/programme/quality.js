import {
    PROGRAMME_COLORS,
    buildGradient,
    buildTooltipBase,
    buildTooltipMarkup,
    createEmptyController,
    echartsLib,
    escapeTooltipHtml,
    formatCount,
    formatProgrammeName,
    setChartFallback,
    wrapAxisLabel,
} from "./shared.js?v=20260414-msc-support01";
import { initialiseQualityNarrative } from "./narratives.js?v=20260405-programmes-progressive01";
import { openProgrammeDrillDown } from "./drilldown.js?v=20260430-unified-spinner01";

export const initialiseQualitySection = (context) => {
    initialiseQualityNarrative(context.elements, context.data.lowPassRows, context.data.cardNarratives, context.flags);

    const element = context.elements.qualityChart;
    const rows = context.data.lowPassRows;

    if (!element) {
        return createEmptyController();
    }
    if (!echartsLib) {
        setChartFallback(element, "ECharts could not load. The programme register is still available.");
        return createEmptyController();
    }
    if (!rows.length) {
        setChartFallback(element, "No pass-rate quality data is available for the current filters.");
        return createEmptyController();
    }

    element.classList.remove("is-empty");
    element.textContent = "";

    const chart = echartsLib.init(element);
    const sortedRows = [...rows].sort((left, right) => left.pass_rate_value - right.pass_rate_value || right.registrations - left.registrations || left.name.localeCompare(right.name));

    chart.setOption({
        animationDuration: 650,
        animationDurationUpdate: 250,
        grid: {
            containLabel: true,
            left: 82,
            right: 68,
            top: 18,
            bottom: 40,
        },
        tooltip: {
            ...buildTooltipBase("item"),
            formatter: (params) => {
                const row = sortedRows[params.dataIndex];
                return buildTooltipMarkup(formatProgrammeName(row.name), [
                    { label: "Pass rate", value: row.pass_rate },
                    { label: "Registrations", value: formatCount(row.registrations) },
                    { label: "Marked results", value: formatCount(row.marked_results) },
                    { label: "Faculty", value: row.faculty },
                ]);
            },
        },
        xAxis: {
            type: "value",
            min: 0,
            max: 100,
            name: "Pass rate %",
            nameLocation: "middle",
            nameGap: 28,
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: {
                color: "#5c718f",
                fontSize: 11,
                formatter: (value) => `${value}%`,
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
            data: sortedRows.map((row) => formatProgrammeName(row.name)),
        },
        series: [
            {
                type: "bar",
                data: sortedRows.map((row) => row.pass_rate_value),
                barWidth: 22,
                label: {
                    show: true,
                    position: "right",
                    color: PROGRAMME_COLORS.ink,
                    fontSize: 10,
                    fontWeight: 700,
                    formatter: (params) => {
                        const row = sortedRows[params.dataIndex];
                        return `${row.pass_rate} (${formatCount(row.registrations)})`;
                    },
                },
                itemStyle: {
                    borderRadius: 0,
                    color: buildGradient(PROGRAMME_COLORS.navy, PROGRAMME_COLORS.sky, "horizontal"),
                },
            },
        ],
    });

    // Add drill-down click handler
    chart.on("click", (params) => {
        const row = sortedRows[params.dataIndex];
        if (row && row.name) {
            openProgrammeDrillDown(context, {
                chartKey: "low_pass",
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
