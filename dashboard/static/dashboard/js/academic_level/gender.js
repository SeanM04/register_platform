import {
    buildAnimationConfig,
    buildGradient,
    buildTooltipBase,
    buildTooltipMarkup,
    formatChartLabel,
    hasMeaningfulRows,
    initialiseChart,
} from "./shared.js";
import {
    buildGenderNarrative,
    getOverviewCardNarrative,
    setActionText,
    setElementText,
    setGenderHints,
} from "./AI_INSIGHTS_ENABLED=TGOOGLE_API_KEY=your-key
OPENAI_API_KEY=your-key";

const buildGenderChartOption = (rows, chartWidth = 0) => {
    const visibleRows = rows.filter((row) => Number(row.students) > 0);
    const isCompact = chartWidth > 0 ? chartWidth < 640 : false;
    const isNarrow = chartWidth > 0 ? chartWidth < 460 : false;
    const useLegendFirstLayout = isNarrow;
    const labelWidth = isNarrow ? 60 : isCompact ? 74 : 92;
    const legendFontSize = isNarrow ? 10 : 12;
    const outerRadius = isNarrow ? "40%" : isCompact ? "50%" : "54%";
    const innerRadius = isNarrow ? 14 : isCompact ? 16 : 20;
    const centerY = isNarrow ? "31%" : isCompact ? "36%" : "38%";
    const shareByLabel = Object.fromEntries(visibleRows.map((row) => [row.label, row.student_share]));

    return ({
        ...buildAnimationConfig(visibleRows),
        legend: {
            bottom: 8,
            left: "center",
            width: useLegendFirstLayout ? "92%" : undefined,
            itemWidth: isNarrow ? 10 : 12,
            itemHeight: isNarrow ? 10 : 12,
            itemGap: isNarrow ? 10 : 16,
            textStyle: { color: "#4b5563", fontSize: legendFontSize },
            formatter: (name) => useLegendFirstLayout
                ? `${formatChartLabel(name, 14)} ${shareByLabel[name] || ""}`.trim()
                : name,
            data: visibleRows.map((row) => row.label),
        },
        tooltip: {
            ...buildTooltipBase("item"),
            formatter: (params) => {
                const row = visibleRows[params.dataIndex];
                return buildTooltipMarkup(row.label, [
                    { label: "Students", value: row.students },
                    { label: "Share", value: row.student_share },
                    { label: "Pass rate", value: row.pass_rate },
                    { label: "Average mark", value: row.average_mark_display },
                    { label: "Results", value: row.results },
                ], { maxWidth: 220 });
            },
        },
        series: [
            {
                name: "Students",
                type: "pie",
                roseType: "radius",
                radius: [innerRadius, outerRadius],
                center: ["50%", centerY],
                startAngle: 90,
                minAngle: 15,
                avoidLabelOverlap: true,
                stillShowZeroSum: false,
                padAngle: 0,
                hoverAnimation: false,
                labelLayout: {
                    moveOverlap: "shiftY",
                    hideOverlap: false,
                },
                itemStyle: {
                    borderColor: "transparent",
                    borderWidth: 0,
                    borderRadius: 0,
                    shadowBlur: 0,
                    color: (params) => {
                        const row = visibleRows[params.dataIndex];
                        if (row.key === "male") {
                            return buildGradient("#082340", "#1f4f88");
                        }
                        if (row.key === "female") {
                            return buildGradient("#2b7ea2", "#4fb0d1");
                        }
                        return buildGradient("#7b8ea6", "#b0bdcb");
                    },
                },
                label: {
                    show: !useLegendFirstLayout,
                    position: "outside",
                    color: "#082340",
                    fontWeight: 700,
                    fontSize: isCompact ? 11 : 12,
                    lineHeight: isCompact ? 16 : 18,
                    width: labelWidth,
                    overflow: "break",
                    formatter: ({ data }) => `${data.name}\n${data.share}`,
                },
                labelLine: {
                    show: false,
                },
                emphasis: {
                    scale: false,
                    itemStyle: {
                        borderColor: "transparent",
                        borderWidth: 0,
                        shadowBlur: 0,
                    },
                },
                data: visibleRows.map((row) => ({
                    value: row.students,
                    name: row.label,
                    share: row.student_share,
                })),
            },
        ],
    });
};

export const initialiseGenderSection = (context) => {
    const { cardNarratives, genderRows } = context.data;
    const { overviewNarrativeSource, overviewNarrativesAreAi } = context.flags;
    const { genderCopy, genderHints, genderNote } = context.elements;

    const initialNarrative = getOverviewCardNarrative(cardNarratives, "gender", buildGenderNarrative(genderRows));
    setElementText(genderCopy, initialNarrative.insight);
    setGenderHints(genderHints);
    setActionText(genderNote, initialNarrative.action, {
        showAiBadge: overviewNarrativesAreAi,
        source: overviewNarrativeSource,
        severity: initialNarrative.severity,
        confidence: initialNarrative.confidence,
    });

    const chart = initialiseChart(
        "academic-level-gender-chart",
        genderRows,
        buildGenderChartOption,
        "No gender split data matched the current filters.",
        (rows) => hasMeaningfulRows(rows, "students"),
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
