import {
    buildAnimationConfig,
    buildAxisPointerConfig,
    buildGradient,
    buildHiddenAxisPointerStyle,
    buildTooltipBase,
    buildTooltipMarkup,
    formatAcademicLevelTick,
    formatChartLabel,
    formatLegendProgrammeName,
    formatWholePercentage,
    initialiseChart,
    setChartClickability,
    toTitleCase,
    hasMeaningfulRows,
} from "./shared.js";
import {
    buildTopProgrammeDetailNarrative,
    buildTopProgrammeOverviewNarrative,
    getOverviewCardNarrative,
    setActionText,
    setElementText,
    setTopProgrammeHints,
} from "./narratives.js";
import { openAcademicLevelDrillDown } from "./drilldown.js";

const buildTopProgrammeChartOption = (rows, selectedProgramme, chartWidth = 0) => {
    const isCompact = chartWidth > 0 ? chartWidth < 640 : false;
    const isNarrow = chartWidth > 0 ? chartWidth < 500 : false;
    const useLegendFirstLayout = isNarrow;
    const visibleProgrammeCount = rows.length;
    const programmeLabel = visibleProgrammeCount === 1 ? "programme" : "programmes";
    const registrationLabel = rows.reduce((total, row) => total + row.registrations, 0).toLocaleString();

    return ({
        ...buildAnimationConfig(rows),
       color: ["#4b66c1", "#78c8e8", "#9A60B4", "#6B7280", "#8B5CF6"],
        title: {
            text: registrationLabel,
            subtext: `top ${visibleProgrammeCount} ${programmeLabel}`,
            left: "center",
            top: isNarrow ? "34%" : "40%",
            textStyle: {
                color: "#082340",
                fontSize: isNarrow ? 20 : 24,
                fontWeight: 800,
            },
            subtextStyle: {
                color: "#4b5563",
                fontSize: isNarrow ? 11 : 12,
                fontWeight: 600,
            },
        },
        legend: useLegendFirstLayout ? {
            type: "scroll",
            bottom: 8,
            left: "center",
            width: "90%",
            itemWidth: 10,
            itemHeight: 10,
            itemGap: 10,
            pageIconColor: "#4fb0d1",
            pageTextStyle: { color: "#64748b", fontSize: 10 },
            textStyle: { color: "#4b5563", fontSize: 10, lineHeight: 14 },
            formatter: (name) => formatChartLabel(toTitleCase(formatLegendProgrammeName(name) || name), 18),
            data: rows.map((row) => row.programme),
        } : undefined,
        tooltip: {
            ...buildTooltipBase("item"),
            formatter: (params) => {
                const row = rows[params.dataIndex];
                return buildTooltipMarkup(row.programme, [
                    { label: "Registrations", value: row.registrations },
                    { label: "Students", value: row.students },
                    { label: "Pass rate", value: row.pass_rate },
                    { label: "Average mark", value: row.average_mark_display },
                    { label: `Top ${visibleProgrammeCount} share`, value: formatWholePercentage(params.percent) },
                ]);
            },
        },
        series: [
            {
                name: "Enrolment Share",
                type: "pie",
                radius: isNarrow ? ["42%", "66%"] : isCompact ? ["46%", "70%"] : ["48%", "74%"],
                center: ["50%", isNarrow ? "42%" : "50%"],
                selectedMode: false,
                selectedOffset: 0,
                avoidLabelOverlap: true,
                stillShowZeroSum: false,
                padAngle: 0,
                hoverAnimation: false,
                minAngle: 6,
                minShowLabelAngle: 4,
                labelLayout: {
                    moveOverlap: "shiftY",
                    hideOverlap: false,
                },
                itemStyle: {
                    borderColor: "transparent",
                    borderWidth: 0,
                    borderRadius: 0,
                    shadowBlur: 0,
                    shadowColor: "transparent",
                },
                label: useLegendFirstLayout ? {
                    show: true,
                    position: "inside",
                    color: "#ffffff",
                    fontWeight: 800,
                    fontSize: 11,
                    formatter: ({ percent }) => (percent >= 15 ? formatWholePercentage(percent) : ""),
                } : {
                    position: "outside",
                    alignTo: "edge",
                    edgeDistance: 12,
                    bleedMargin: 8,
                    width: isCompact ? 112 : 132,
                    color: "#082340",
                    fontWeight: 700,
                    lineHeight: 18,
                    formatter: ({ data, percent }) => `${formatChartLabel(data.name, isCompact ? 18 : 22)}\n${formatWholePercentage(percent)}`,
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
                        shadowColor: "transparent",
                    },
                },
                data: rows.map((row) => ({
                    name: row.programme,
                    value: row.registrations,
                    selected: row.programme === selectedProgramme,
                    itemStyle: {
                        color: row.programme === selectedProgramme
                            ? buildGradient("#082340", "#4fb0d1")
                            : undefined,
                    },
                })),
            },
        ],
    });
};

const buildTopProgrammeDetailOption = (programme, chartWidth = 0) => {
    const isCompact = chartWidth > 0 ? chartWidth < 760 : programme.level_breakdown.length > 5;

    return ({
        ...buildAnimationConfig(programme.level_breakdown),
        axisPointer: buildHiddenAxisPointerStyle(),
        grid: {
            top: 20,
            right: isCompact ? 44 : 52,
            bottom: isCompact ? 112 : 96,
            left: isCompact ? 42 : 50,
            containLabel: true,
        },
        tooltip: {
            ...buildTooltipBase("axis"),
            axisPointer: buildAxisPointerConfig("cross"),
            formatter: (params) => {
                const row = programme.level_breakdown[params[0].dataIndex];
                return buildTooltipMarkup(row.level, [
                    { label: "Registrations", value: row.registrations },
                    { label: "Students", value: row.students },
                    { label: "Pass rate", value: row.pass_rate },
                    { label: "Average mark", value: row.average_mark_display },
                ], { maxWidth: 220 });
            },
        },
        xAxis: {
            type: "category",
            data: programme.level_breakdown.map((row) => row.level),
            axisPointer: buildHiddenAxisPointerStyle(),
            axisTick: { show: false },
            axisLine: { lineStyle: { color: "#cbd5e1" } },
            axisLabel: {
                color: "#082340",
                fontWeight: 600,
                fontSize: isCompact ? 11 : 12,
                lineHeight: isCompact ? 14 : 16,
                margin: 14,
                interval: 0,
                rotate: 35,
                formatter: (value) => formatAcademicLevelTick(value, isCompact),
            },
        },
        yAxis: [
            {
                type: "value",
                axisPointer: buildHiddenAxisPointerStyle(),
                minInterval: 1,
                axisLabel: {
                    color: "#4b5563",
                },
                splitLine: { lineStyle: { color: "#e2e8f0" } },
            },
            {
                type: "value",
                axisPointer: buildHiddenAxisPointerStyle(),
                min: 0,
                max: 100,
                axisLabel: {
                    formatter: "{value}%",
                    color: "#4b5563",
                },
                splitLine: { show: false },
            },
        ],
        series: [
            {
                name: "Registrations",
                type: "bar",
                barWidth: isCompact ? 18 : 22,
                itemStyle: {
                    borderRadius: [6, 6, 0, 0],
                    color: buildGradient("#d3e9f4", "#4fb0d1"),
                },
                data: programme.level_breakdown.map((row) => row.registrations),
            },
            {
                name: "Pass Rate",
                type: "line",
                yAxisIndex: 1,
                smooth: programme.level_breakdown.length > 2,
                symbol: "circle",
                symbolSize: isCompact ? 7 : 8,
                lineStyle: {
                    width: 3,
                    color: "#082340",
                },
                itemStyle: {
                    color: "#082340",
                },
                data: programme.level_breakdown.map((row) => row.pass_rate_value),
            },
        ],
    });
};

export const initialiseTopProgrammeSection = (context) => {
    const { cardNarratives, programmeRows, topProgrammeRows } = context.data;
    const { overviewNarrativeSource, overviewNarrativesAreAi } = context.flags;
    const {
        programmeTopContext,
        programmeTopReset,
        programmeTopStatus,
        programmeTopTitle,
        topProgrammeCard,
        topProgrammeCopy,
        topProgrammeHints,
    } = context.elements;

    const chart = initialiseChart(
        "academic-level-programme-top-chart",
        topProgrammeRows,
        (rows, chartWidth) => buildTopProgrammeChartOption(rows, null, chartWidth),
        "No top programme enrolment data matched the current filters.",
        (rows) => hasMeaningfulRows(rows, "registrations"),
        { renderer: "svg" },
    );

    let topProgrammeMode = "overview";
    let activeTopProgrammeName = null;

    const setTopProgrammeDetailState = (isDetail) => {
        if (topProgrammeCard) {
            topProgrammeCard.classList.toggle("is-detail", isDetail);
        }
        if (programmeTopContext) {
            programmeTopContext.classList.toggle("is-hidden", !isDetail);
        }
        setTopProgrammeHints(topProgrammeHints, isDetail);
    };

    const setTopProgrammeContext = (programme = null) => {
        if (!programmeTopTitle) {
            return;
        }

        programmeTopTitle.textContent = programme ? `${programme.programme} by academic level` : "";
    };

    const setTopProgrammeStatus = (message, isDetail, severity = "stable", confidence = "medium") => {
        setActionText(programmeTopStatus, message, {
            showAiBadge: !isDetail && overviewNarrativesAreAi,
            source: overviewNarrativeSource,
            severity,
            confidence,
        });
        if (programmeTopReset) {
            programmeTopReset.classList.toggle("is-hidden", !isDetail);
        }
    };

    const setTopProgrammeNarrative = (programme = null) => {
        const narrative = programme
            ? buildTopProgrammeDetailNarrative(programme)
            : getOverviewCardNarrative(cardNarratives, "top_enrolment", buildTopProgrammeOverviewNarrative(topProgrammeRows));
        setElementText(topProgrammeCopy, narrative.insight);
        setTopProgrammeStatus(narrative.action, Boolean(programme), narrative.severity, narrative.confidence);
    };

    const showTopProgrammeOverview = () => {
        if (!chart) {
            return;
        }

        topProgrammeMode = "overview";
        activeTopProgrammeName = null;
        setTopProgrammeDetailState(false);
        setChartClickability(chart, true);
        chart.setOption(buildTopProgrammeChartOption(topProgrammeRows, null, chart.getWidth()), true);
        if (programmeTopReset) {
            programmeTopReset.textContent = "Back to overview";
        }
        setTopProgrammeContext(null);
        setTopProgrammeNarrative(null);
        window.requestAnimationFrame(() => {
            chart.resize();
        });
    };

    const showTopProgrammeDetail = (programmeName) => {
        if (!chart) {
            return;
        }

        const programme = programmeRows.find((row) => row.programme === programmeName);
        if (!programme || !programme.level_breakdown.length) {
            return;
        }

        topProgrammeMode = "detail";
        activeTopProgrammeName = programme.programme;
        setTopProgrammeDetailState(true);
        setChartClickability(chart, true);
        setTopProgrammeContext(programme);
        chart.setOption(buildTopProgrammeDetailOption(programme, chart.getWidth()), true);
        setTopProgrammeNarrative(programme);
        window.requestAnimationFrame(() => {
            chart.resize();
            chart.setOption(buildTopProgrammeDetailOption(programme, chart.getWidth()), true);
        });
    };

    if (chart && topProgrammeRows.length) {
        showTopProgrammeOverview();
        chart.on("click", (params) => {
            if (topProgrammeMode === "detail" && activeTopProgrammeName) {
                if (params.seriesType !== "bar") {
                    return;
                }

                const programme = programmeRows.find((row) => row.programme === activeTopProgrammeName);
                const level = programme?.level_breakdown?.[params.dataIndex]?.level;
                if (level) {
                    openAcademicLevelDrillDown(context, {
                        chartKey: "programme_level",
                        bucketKey: `${activeTopProgrammeName}|${level}`,
                        label: `${activeTopProgrammeName} in ${level}`,
                    });
                }
                return;
            }

            const selectedProgramme = topProgrammeRows[params.dataIndex];
            if (!selectedProgramme) {
                return;
            }
            showTopProgrammeDetail(selectedProgramme.programme);
        });
    }

    if (programmeTopReset) {
        programmeTopReset.addEventListener("click", () => {
            showTopProgrammeOverview();
        });
    }

    return {
        getChart: () => chart,
        resize: () => {
            if (!chart) {
                return;
            }

            chart.resize();

            if (topProgrammeMode === "detail" && activeTopProgrammeName) {
                const programme = programmeRows.find((row) => row.programme === activeTopProgrammeName);
                if (programme) {
                    chart.setOption(buildTopProgrammeDetailOption(programme, chart.getWidth()), true);
                }
                return;
            }

            chart.setOption(buildTopProgrammeChartOption(topProgrammeRows, null, chart.getWidth()), true);
        },
    };
};
