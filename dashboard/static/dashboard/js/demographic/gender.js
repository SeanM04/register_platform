import { buildAnimationConfig, buildGradient, buildTooltipBase, buildTooltipMarkup, initialiseChart } from "./shared.js";
import { initialiseGenderNarrative } from "./narratives.js";

const buildGenderChartOption = (rows, chartWidth = 0) => {
    const visibleRows = rows.filter((row) => Number(row.count || 0) > 0);
    const isCompact = chartWidth > 0 ? chartWidth < 640 : false;
    const isNarrow = chartWidth > 0 ? chartWidth < 480 : false;
    const outerRadius = isNarrow ? "58%" : isCompact ? "63%" : "68%";

    return {
        ...buildAnimationConfig(visibleRows),
        legend: {
            bottom: 4,
            left: "center",
            itemWidth: isNarrow ? 10 : 12,
            itemHeight: isNarrow ? 10 : 12,
            itemGap: isNarrow ? 10 : 16,
            textStyle: { color: "#4b5563", fontSize: isNarrow ? 10 : 12 },
            data: visibleRows.map((row) => row.label),
        },
        tooltip: {
            ...buildTooltipBase("item"),
            formatter: (params) => {
                const row = visibleRows[params.dataIndex];
                return buildTooltipMarkup(row.label, [
                    { label: "Students", value: row.count },
                    { label: "Share", value: row.share },
                ], { maxWidth: 220 });
            },
        },
        series: [
            {
                name: "Students",
                type: "pie",
                radius: outerRadius,
                center: ["50%", isNarrow ? "42%" : "46%"],
                startAngle: 90,
                avoidLabelOverlap: true,
                hoverAnimation: false,
                itemStyle: {
                    borderColor: "#ffffff",
                    borderWidth: 3,
                    color: (params) => {
                        const row = visibleRows[params.dataIndex];
                        if (row.label === "Male") {
                            return buildGradient("#082340", "#1f4f88");
                        }
                        if (row.label === "Female") {
                            return buildGradient("#2b7ea2", "#4fb0d1");
                        }
                        return buildGradient("#7b8ea6", "#b0bdcb");
                    },
                },
                label: {
                    show: false,
                },
                data: visibleRows.map((row) => ({
                    value: row.count,
                    name: row.label,
                    share: row.share,
                })),
            },
        ],
    };
};

export const initialiseGenderSection = (context) => {
    const { cardNarratives, genderRows } = context.data;
    initialiseGenderNarrative(context.elements, genderRows, cardNarratives, context.flags);

    const chart = initialiseChart(
        "demographic-gender-chart",
        genderRows,
        buildGenderChartOption,
        "No gender distribution data matched the current filters.",
        (rows) => rows.some((row) => Number(row.count || 0) > 0),
        { renderer: "svg" },
    );

    return {
        getChart: () => chart,
        resize: () => {
            if (!chart) {
                return;
            }
            chart.resize();
            chart.setOption(buildGenderChartOption(genderRows, chart.getWidth()), true);
        },
    };
};
