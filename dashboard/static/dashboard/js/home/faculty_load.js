import {
    HOME_COLORS,
    buildGradient,
    buildTooltipBase,
    buildTooltipMarkup,
    createEmptyController,
    echartsLib,
    formatCount,
    setChartFallback,
    wrapAxisLabel,
} from "./shared.js?v=20260403-home-story04";
import { cancelOverviewDrillDownRequests } from "./drilldown.js?v=20260411-home-drilldown01";
import { showDrillDownModal } from "./drilldown_modal.js?v=20260411-home-drilldown01";
import { initialiseFacultyNarrative } from "./narratives.js?v=20260408-home-ai02";

/**
 * Build the faculty-load chart and sync its narrative surfaces.
 */
export const initialiseFacultyLoadSection = (context) => {
    const rows = context.data.facultyLoadRows || [];
    const { facultyChart } = context.elements;

    if (!facultyChart) {
        return createEmptyController();
    }

    initialiseFacultyNarrative(context.elements, rows, context.data.cardNarratives, context.flags);

    if (!echartsLib || !rows.length) {
        setChartFallback(facultyChart, "Faculty load data will appear once registrations are available.");
        return createEmptyController();
    }

    const chart = echartsLib.init(facultyChart);
    chart.setOption(
        {
            animationDuration: 700,
            animationDurationUpdate: 300,
            tooltip: {
                ...buildTooltipBase("axis"),
                axisPointer: {
                    type: "shadow",
                    shadowStyle: {
                        opacity: 0.06,
                        color: HOME_COLORS.sky,
                    },
                },
                formatter: (params) => {
                    const row = rows[params[0]?.dataIndex || 0];
                    return buildTooltipMarkup(row?.label || "Faculty", [
                        { label: "Registrations", value: formatCount(row?.registrations) },
                        { label: "Share", value: `${row?.share_pct || 0}%` },
                    ]);
                },
            },
            grid: {
                top: 16,
                left: 140,
                right: 56,
                bottom: 34,
                containLabel: false,
            },
            xAxis: {
                type: "value",
                splitNumber: 4,
                axisLine: { show: false },
                axisTick: { show: false },
                axisLabel: {
                    color: "#607488",
                    fontWeight: 600,
                    margin: 14,
                },
                splitLine: {
                    lineStyle: {
                        color: "rgba(19, 57, 95, 0.08)",
                        type: "dashed",
                    },
                },
            },
            yAxis: {
                type: "category",
                data: rows.map((row) => wrapAxisLabel(row.label, { maxLineLength: 18, maxLines: 2 })),
                axisLine: { show: false },
                axisTick: { show: false },
                axisLabel: {
                    color: HOME_COLORS.ink,
                    fontWeight: 700,
                    margin: 14,
                    width: 132,
                    overflow: "break",
                },
            },
            series: [
                {
                    type: "bar",
                    data: rows.map((row) => ({
                        value: row.registrations,
                        itemStyle: {
                            color: buildGradient(HOME_COLORS.navy, HOME_COLORS.sky, "horizontal"),
                        },
                        drilldown: {
                            name: row.label,
                            items: [
                                { label: "Registrations", value: formatCount(row.registrations) },
                                { label: "Percentage", value: `${row.share_pct || 0}%` },
                                { label: "Faculty", value: row.label },
                                { label: "Total Registrations", value: formatCount(row.total || 0) }
                            ]
                        }
                    })),
                    barMaxWidth: 28,
                    label: {
                        show: true,
                        position: "right",
                        color: HOME_COLORS.ink,
                        fontWeight: 800,
                        fontSize: 12,
                        formatter: ({ value }) => formatCount(value),
                    },
                },
            ],
        }
    );

    chart.on("click", (params) => {
        if (params.data && params.data.drilldown) {
            cancelOverviewDrillDownRequests();
            const drilldown = params.data.drilldown;
            showDrillDownModal(drilldown.name, drilldown.items);
        }
    });

    return {
        getChart: () => chart,
        resize: () => chart.resize(),
    };
};
