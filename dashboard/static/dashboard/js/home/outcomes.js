import {
    HOME_COLORS,
    buildGradient,
    buildTooltipBase,
    buildTooltipMarkup,
    createEmptyController,
    echartsLib,
    formatCount,
    setChartFallback,
} from "./shared.js?v=20260403-home-story04";
import { initialiseOutcomeNarrative } from "./narratives.js?v=20260408-home-ai02";

const OUTCOME_COLORS = {
    passed: buildGradient(HOME_COLORS.mint, "#2a8d71"),
    failed: buildGradient(HOME_COLORS.rose, "#c6535b"),
    awaiting: buildGradient("#b9cad9", "#8da3b8"),
};

/**
 * Build the assessment-outcomes chart and sync its narrative surfaces.
 */
export const initialiseOutcomeSection = (context) => {
    const rows = context.data.outcomeRows || [];
    const { outcomesChart } = context.elements;

    if (!outcomesChart) {
        return createEmptyController();
    }

    initialiseOutcomeNarrative(context.elements, rows, context.data.cardNarratives, context.flags);

    if (!echartsLib || !rows.length) {
        setChartFallback(outcomesChart, "Assessment outcome data will appear once results are available.");
        return createEmptyController();
    }

    const chart = echartsLib.init(outcomesChart);
    chart.setOption(
        {
            animationDuration: 700,
            animationDurationUpdate: 300,
            tooltip: {
                ...buildTooltipBase("item"),
                formatter: (params) => buildTooltipMarkup(params.name, [
                    { label: "Results", value: formatCount(params.value) },
                    { label: "Share", value: `${Math.round(params.percent)}%` },
                ]),
            },
            legend: {
                bottom: 0,
                left: "center",
                itemWidth: 14,
                itemHeight: 14,
                textStyle: {
                    color: HOME_COLORS.ink,
                    fontWeight: 700,
                    fontSize: 12,
                },
            },
            series: [
                {
                    type: "pie",
                    radius: "65%",
                    center: ["50%", "44%"],
                    minAngle: 8,
                    avoidLabelOverlap: true,
                    itemStyle: {
                        borderColor: "#ffffff",
                        borderWidth: 4,
                    },
                    label: {
                        show: false,
                    },
                    labelLine: {
                        length: 12,
                        length2: 10,
                    },
                    data: rows.map((row) => ({
                        name: row.label,
                        value: row.count,
                        itemStyle: {
                            color: OUTCOME_COLORS[row.key] || HOME_COLORS.sky,
                        },
                        drilldown: {
                            name: row.label,
                            items: [
                                { label: "Results", value: formatCount(row.count) },
                                { label: "Percentage", value: `${Math.round((row.count / rows.reduce((sum, r) => sum + r.count, 0)) * 100)}%` },
                                { label: "Status", value: row.label },
                                { label: "Total Results", value: formatCount(rows.reduce((sum, r) => sum + r.count, 0)) }
                            ]
                        }
                    })),
                },
            ],
        }
    );

    // Add drill-down click handler
    chart.on('click', function(params) {
        if (params.data && params.data.drilldown) {
            const drilldown = params.data.drilldown;
            showDrillDownModal(drilldown.name, drilldown.items);
        }
    });

    return {
        getChart: () => chart,
        resize: () => chart.resize(),
    };
};
