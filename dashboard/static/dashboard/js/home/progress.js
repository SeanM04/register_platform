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
import { cancelOverviewDrillDownRequests, openOverviewDrillDown } from "./drilldown.js?v=20260601-drilldown-numeric-align01";
import { showDrillDownModal } from "./drilldown_modal.js?v=20260601-drilldown-numeric-align01";
import { initialiseProgressNarrative } from "./narratives.js?v=20260408-home-ai02";

const PROGRESS_COLORS = {
    proceed: buildGradient("#276f80", "#5bc192"),
    retake: buildGradient("#d48837", "#f0c367"),
    pending: buildGradient("#8da2b8", "#bfd1df"),
    exit: buildGradient("#c6525b", "#ea8a74"),
    other: buildGradient(HOME_COLORS.navy, HOME_COLORS.sky),
};

/**
 * Build the registration-decision chart and sync its narrative surfaces.
 */
export const initialiseProgressSection = (context) => {
    const rows = context.data.progressRows || [];
    const { progressChart } = context.elements;

    if (!progressChart) {
        return createEmptyController();
    }

    initialiseProgressNarrative(context.elements, rows, context.data.cardNarratives, context.flags);

    if (!echartsLib || !rows.length) {
        setChartFallback(progressChart, "Progress status data will appear once registration decisions are available.");
        return createEmptyController();
    }

    const chart = echartsLib.init(progressChart);
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
                    return buildTooltipMarkup(row?.label || "Status", [
                        { label: "Registrations", value: formatCount(row?.count) },
                        { label: "Share", value: `${row?.share_pct || 0}%` },
                    ]);
                },
            },
            grid: {
                top: 20,
                left: 8,
                right: 12,
                bottom: 52,
                containLabel: true,
            },
            xAxis: {
                type: "category",
                data: rows.map((row) => wrapAxisLabel(row.label, { maxLineLength: 12, maxLines: 2 })),
                axisLine: {
                    lineStyle: {
                        color: "rgba(18, 57, 95, 0.12)",
                    },
                },
                axisTick: { show: false },
                axisLabel: {
                    color: HOME_COLORS.ink,
                    fontWeight: 700,
                    margin: 14,
                    lineHeight: 16,
                },
            },
            yAxis: {
                type: "value",
                splitNumber: 4,
                axisLine: { show: false },
                axisTick: { show: false },
                axisLabel: {
                    color: "#607488",
                    fontWeight: 600,
                },
                splitLine: {
                    lineStyle: {
                        color: "rgba(19, 57, 95, 0.08)",
                        type: "dashed",
                    },
                },
            },
            series: [
                {
                    type: "bar",
                    data: rows.map((row) => ({
                        value: row.count,
                        itemStyle: {
                            color: PROGRESS_COLORS[row.key] || HOME_COLORS.sky,
                            borderRadius: [6, 6, 0, 0],
                        },
                        drilldown: {
                            name: row.label,
                            items: [
                                { label: "Registrations", value: formatCount(row.count) },
                                { label: "Percentage", value: `${row.share_pct || 0}%` },
                                { label: "Status", value: row.label },
                                { label: "Total Decisions", value: formatCount(row.total || 0) }
                            ]
                        }
                    })),
                    barMaxWidth: 28,
                    label: {
                        show: true,
                        position: "top",
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
        const row = rows[params.dataIndex];
        if (row && row.key) {
            openOverviewDrillDown(context, {
                chartKey: "progress",
                bucketKey: row.key,
                label: row.label,
            });
        }
    });

    return {
        getChart: () => chart,
        resize: () => chart.resize(),
    };
};
