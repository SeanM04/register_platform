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
import { initialiseOutcomeNarrative } from "./narratives.js?v=20260403-home-story04";

const OUTCOME_COLORS = {
    passed: buildGradient(HOME_COLORS.mint, "#2a8d71"),
    failed: buildGradient(HOME_COLORS.rose, "#c6535b"),
    awaiting: buildGradient("#b9cad9", "#8da3b8"),
};

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
                    { label: "Share", value: `${params.percent}%` },
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
                    radius: ["46%", "72%"],
                    center: ["50%", "44%"],
                    minAngle: 8,
                    avoidLabelOverlap: true,
                    itemStyle: {
                        borderColor: "#ffffff",
                        borderWidth: 4,
                    },
                    label: {
                        color: HOME_COLORS.ink,
                        fontWeight: 700,
                        fontSize: 12,
                        formatter: ({ name, percent }) => `${name}\n${percent}%`,
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
                    })),
                },
            ],
        }
    );

    return {
        getChart: () => chart,
        resize: () => chart.resize(),
    };
};
