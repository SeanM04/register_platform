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

import { openOverviewDrillDown } from "./drilldown.js?v=20260601-drilldown-numeric-align01";
import { initialiseRiskNarrative } from "./narratives.js?v=20260408-home-ai02";

const RISK_COLORS = {
    critical: buildGradient("#d1535d", "#e88473"),
    high: buildGradient("#e27a5e", "#f2ba67"),
    moderate: buildGradient("#dfbf54", "#f3d77d"),
    stable: buildGradient("#4fae82", "#79d6af"),
};

/**
 * Build the risk-distribution chart and sync its narrative surfaces.
 */
export const initialiseRiskDistributionSection = (context) => {
    const rows = context.data.riskDistributionRows || [];
    const { riskChart } = context.elements;

    if (!riskChart) {
        return createEmptyController();
    }

    initialiseRiskNarrative(
        context.elements,
        rows,
        context.data.cardNarratives,
        context.flags,
    );

    if (!echartsLib || !rows.length) {
        setChartFallback(
            riskChart,
            "Risk distribution will appear once student profiles are available.",
        );

        return createEmptyController();
    }

    const chart = echartsLib.init(riskChart);

    chart.setOption({
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

                return buildTooltipMarkup(
                    row?.label || "Risk band",
                    [
                        {
                            label: "Students",
                            value: formatCount(row?.count),
                        },
                        {
                            label: "Share",
                            value: `${row?.percent || 0}%`,
                        },
                    ],
                );
            },
        },

        grid: {
            top: 32,
            left: 20,
            right: 16,
            bottom: 52,
            containLabel: true,
        },

        xAxis: {
            type: "category",

            data: rows.map((row) =>
                wrapAxisLabel(row.label, {
                    maxLineLength: 12,
                    maxLines: 2,
                }),
            ),

            axisLine: {
                lineStyle: {
                    color: "rgba(18, 57, 95, 0.12)",
                },
            },

            axisTick: {
                show: false,
            },

            axisLabel: {
                color: HOME_COLORS.ink,
                fontWeight: 700,
                fontSize: 11,

                // FORCE ALL LABELS TO SHOW
                interval: 0,

                rotate: 0,
                margin: 14,
                lineHeight: 16,

                // PREVENT ECHARTS FROM HIDING LABELS
                hideOverlap: false,
            },
        },

        yAxis: {
            type: "value",
            splitNumber: 4,

            axisLine: {
                show: false,
            },

            axisTick: {
                show: false,
            },

            axisLabel: {
                color: "#5f7388",
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

                barMaxWidth: 40,

                data: rows.map((row) => ({
                    value: row.count,

                    itemStyle: {
                        color: RISK_COLORS[row.key] || HOME_COLORS.sky,
                        borderRadius: [6, 6, 0, 0],
                    },

                    drilldownKey: row.key,
                })),

                label: {
                    show: true,
                    position: "top",
                    color: HOME_COLORS.ink,
                    fontSize: 12,
                    fontWeight: 800,

                    // PREVENT VALUE LABELS FROM DISAPPEARING
                    hideOverlap: false,

                    formatter: ({ value }) => formatCount(value),
                },
            },
        ],
    });

    chart.on("click", (params) => {
        const row = rows[params.dataIndex];

        const bucketKey =
            row?.key || params.data?.drilldownKey;

        if (bucketKey) {
            openOverviewDrillDown(context, {
                chartKey: "risk_distribution",
                bucketKey,
                label: row?.label || params.name,
            });
        }
    });

    return {
        getChart: () => chart,

        resize: () => {
            chart.resize();
        },
    };
};
