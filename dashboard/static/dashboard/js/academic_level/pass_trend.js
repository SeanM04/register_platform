import {
    PASS_RATE_TARGET,
    buildAnimationConfig,
    buildAxisPointerConfig,
    buildGradient,
    buildHiddenAxisPointerStyle,
    buildHorizontalCategoryZoom,
    buildProgrammeAxisLabels,
    buildTooltipBase,
    buildTooltipMarkup,
    createDefaultPassSeriesSelection,
    echartsLib,
    formatTooltipTitle,
    getTooltipDataIndex,
    initialiseChart,
    setChartClickability,
} from "./shared.js";
import {
    buildPassDetailNarrative,
    buildPassOverviewNarrative,
    getOverviewCardNarrative,
    setActionText,
    setElementText,
    setPassTrendHints,
} from "./narratives.js";

const clearHighlightedLevelRow = (levelTableRows) => {
    levelTableRows.forEach((row) => {
        row.classList.remove("is-emphasized");
    });
};

const getLevelTableRows = () => Array.from(document.querySelectorAll("[data-level-row]"));

const getLevelTableRow = (levelName) => (
    getLevelTableRows().find((row) => row.dataset.levelRow === levelName) || null
);

const highlightLevelRow = (levelName) => {
    clearHighlightedLevelRow(getLevelTableRows());
    const tableRow = getLevelTableRow(levelName);
    if (tableRow) {
        tableRow.classList.add("is-emphasized");
    }
    return tableRow;
};

const jumpToLevelRow = (elements, levelName) => {
    const tableRow = highlightLevelRow(levelName);
    if (!tableRow) {
        return;
    }

    tableRow.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
    const tableWrap = document.querySelector(".level-table-wrap[data-scroll-region]")
        || document.querySelector("[data-scroll-region]")
        || elements.levelTableWrap;
    if (tableWrap && typeof tableWrap.focus === "function") {
        window.setTimeout(() => {
            try {
                tableWrap.focus({ preventScroll: true });
            } catch (error) {
                tableWrap.focus();
            }
        }, 180);
    }
};

const buildPassTrendSeriesData = (rows) => rows.map((row) => {
    const isBelowTarget = Number(row.pass_rate_value || 0) < PASS_RATE_TARGET;
    return {
        value: row.pass_rate_value,
        itemStyle: isBelowTarget ? {
            color: "#f59e0b",
            borderColor: "#fff7ed",
            borderWidth: 2,
        } : undefined,
        label: isBelowTarget ? {
            color: "#9a3412",
        } : undefined,
    };
});

const buildPassChartOption = (rows) => ({
    ...buildAnimationConfig(rows),
    axisPointer: buildHiddenAxisPointerStyle(),
    grid: { top: 28, right: 28, bottom: rows.length > 8 ? 100 : 72, left: 52, containLabel: true },
    dataZoom: buildHorizontalCategoryZoom(rows),
    tooltip: {
        ...buildTooltipBase("axis"),
        axisPointer: buildAxisPointerConfig("line"),
        formatter: (params) => {
            const row = rows[params[0].dataIndex];
            return buildTooltipMarkup(row.level, [
                { label: "Pass rate", value: row.pass_rate },
                { label: "Average mark", value: row.average_mark },
                { label: "Registrations", value: row.registrations },
                { label: "Students", value: row.students },
                { label: "Top programme", value: formatTooltipTitle(row.top_programme, 42) },
                { label: "Target status", value: row.pass_rate_value < PASS_RATE_TARGET ? `Below ${PASS_RATE_TARGET}% target` : `At or above ${PASS_RATE_TARGET}% target` },
            ]);
        },
    },
    xAxis: {
        type: "category",
        triggerEvent: true,
        data: rows.map((row) => row.level),
        axisPointer: buildHiddenAxisPointerStyle(),
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "#cbd5e1" } },
        axisLabel: {
            color: "#082340",
            fontWeight: 600,
            interval: 0,
            rotate: rows.length > 3 ? 35 : 0,
            margin: 16,
        },
    },
    yAxis: {
        type: "value",
        axisPointer: buildHiddenAxisPointerStyle(),
        min: 0,
        max: 100,
        axisLabel: { formatter: "{value}%" },
        splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    series: [
        {
            type: "line",
            smooth: rows.length > 2,
            triggerLineEvent: true,
            symbol: "circle",
            symbolSize: 10,
            label: {
                show: rows.length <= 8,
                position: "top",
                color: "#082340",
                fontWeight: 700,
                formatter: ({ value }) => `${value}%`,
            },
            itemStyle: {
                color: buildGradient("#082340", "#4fb0d1"),
            },
            lineStyle: {
                width: 4,
                color: "#0d325d",
            },
            markLine: {
                symbol: "none",
                silent: true,
                lineStyle: {
                    color: "#f59e0b",
                    width: 1.5,
                    type: "dashed",
                    opacity: 0.72,
                },
                label: {
                    show: true,
                    formatter: `Target ${PASS_RATE_TARGET}%`,
                    color: "#9a3412",
                    backgroundColor: "rgba(255, 247, 237, 0.96)",
                    padding: [4, 7],
                    borderRadius: 999,
                },
                data: [{ yAxis: PASS_RATE_TARGET }],
            },
            areaStyle: {
                color: new echartsLib.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: "rgba(79, 176, 209, 0.34)" },
                    { offset: 1, color: "rgba(79, 176, 209, 0.04)" },
                ]),
            },
            progressive: 400,
            data: buildPassTrendSeriesData(rows),
        },
    ],
});

const buildPassLevelDetailOption = (
    levelRow,
    chartWidth = 0,
    seriesSelection = createDefaultPassSeriesSelection(),
) => {
    const rows = levelRow.programme_breakdown || [];
    const isCompact = chartWidth > 0 ? chartWidth < 760 : rows.length > 5;
    const isNarrow = chartWidth > 0 ? chartWidth < 480 : false;
    const axisLabels = buildProgrammeAxisLabels(rows, isCompact, isNarrow);

    return ({
        ...buildAnimationConfig(rows),
        axisPointer: buildHiddenAxisPointerStyle(),
        grid: {
            top: 28,
            right: isCompact ? 34 : 40,
            bottom: rows.length > 6 ? 128 : 108,
            left: 52,
            containLabel: true,
        },
        dataZoom: buildHorizontalCategoryZoom(rows),
        tooltip: {
            ...buildTooltipBase("item"),
            formatter: (params) => {
                const row = rows[getTooltipDataIndex(params)];
                if (!row) {
                    return "";
                }
                return buildTooltipMarkup(row.programme, [
                    { label: "Enrolment count", value: row.registrations },
                    { label: "Average mark", value: row.average_mark_display },
                    { label: "Pass rate", value: row.pass_rate },
                    { label: "Students", value: row.students },
                    { label: "Results", value: row.results },
                ]);
            },
        },
        xAxis: {
            type: "category",
            data: rows.map((row) => row.programme),
            axisPointer: buildHiddenAxisPointerStyle(),
            axisTick: { show: false },
            axisLine: { lineStyle: { color: "#cbd5e1" } },
            axisLabel: {
                color: "#082340",
                fontWeight: 600,
                fontSize: isNarrow ? 10 : isCompact ? 11 : 12,
                lineHeight: isNarrow ? 13 : isCompact ? 14 : 16,
                margin: 14,
                interval: 0,
                hideOverlap: false,
                rotate: 35,
                formatter: (_value, index) => axisLabels[index] || "",
            },
        },
        yAxis: [
            {
                type: "value",
                axisPointer: buildHiddenAxisPointerStyle(),
                show: seriesSelection.enrolment,
                minInterval: 1,
                axisLabel: {
                    color: "#4b5563",
                },
                splitLine: { lineStyle: { color: "#e2e8f0" } },
            },
            {
                type: "value",
                axisPointer: buildHiddenAxisPointerStyle(),
                show: seriesSelection.average_mark,
                min: 0,
                max: 100,
                axisLabel: {
                    formatter: "{value}",
                    color: "#4b5563",
                },
                splitLine: { show: false },
            },
        ],
        series: [
            ...(seriesSelection.enrolment ? [{
                name: "Enrolment Count",
                type: "bar",
                barMaxWidth: isCompact ? 18 : 22,
                itemStyle: {
                    borderRadius: [0, 0, 0, 0],
                    color: buildGradient("#d3e9f4", "#4fb0d1"),
                },
                data: rows.map((row) => row.registrations),
            }] : []),
            ...(seriesSelection.average_mark ? [{
                name: "Average Mark",
                type: "bar",
                yAxisIndex: 1,
                barMaxWidth: isCompact ? 18 : 22,
                itemStyle: {
                    borderRadius: [0, 0, 0, 0],
                    color: buildGradient("#0d325d", "#1f4f88"),
                },
                data: rows.map((row) => row.average_mark),
            }] : []),
        ],
    });
};

export const initialisePassTrendSection = (context) => {
    const { cardNarratives, levelRows } = context.data;
    const { overviewNarrativeSource, overviewNarrativesAreAi } = context.flags;
    const {
        passLegendButtons,
        passTrendCard,
        passTrendContext,
        passTrendCopy,
        passTrendHints,
        passTrendJump,
        passTrendReset,
        passTrendStatus,
        passTrendTitle,
    } = context.elements;

    const chart = initialiseChart(
        "academic-level-pass-chart",
        levelRows,
        buildPassChartOption,
        "No academic pass data matched the current filters.",
    );

    let passTrendMode = "overview";
    let activePassLevel = null;
    let passTrendSeriesSelection = createDefaultPassSeriesSelection();

    const syncPassLegendState = () => {
        passLegendButtons.forEach((button) => {
            const seriesKey = button.dataset.passSeries;
            const isActive = Boolean(passTrendSeriesSelection[seriesKey]);
            button.classList.toggle("is-inactive", !isActive);
            button.setAttribute("aria-pressed", String(isActive));
        });
    };

    const setPassTrendDetailState = (isDetail) => {
        if (passTrendCard) {
            passTrendCard.classList.toggle("is-detail", isDetail);
        }
        if (passTrendContext) {
            passTrendContext.classList.toggle("is-hidden", !isDetail);
        }
        setPassTrendHints(passTrendHints, isDetail);
    };

    const setPassTrendContext = (levelRow = null) => {
        if (!passTrendTitle) {
            return;
        }

        passTrendTitle.textContent = levelRow ? `${levelRow.level} by programme` : "";
    };

    const setPassTrendStatus = (message, isDetail, severity = "stable", confidence = "medium") => {
        setActionText(passTrendStatus, message, {
            showAiBadge: !isDetail && overviewNarrativesAreAi,
            source: overviewNarrativeSource,
            severity,
            confidence,
        });
        if (passTrendJump) {
            passTrendJump.classList.toggle("is-hidden", !isDetail);
        }
        if (passTrendReset) {
            passTrendReset.classList.toggle("is-hidden", !isDetail);
        }
    };

    const setPassTrendNarrative = (levelRow = null) => {
        const narrative = levelRow
            ? buildPassDetailNarrative(levelRow)
            : getOverviewCardNarrative(cardNarratives, "pass_trend", buildPassOverviewNarrative(levelRows));
        setElementText(passTrendCopy, narrative.insight);
        setPassTrendStatus(narrative.action, Boolean(levelRow), narrative.severity, narrative.confidence);
    };

    const showPassTrendOverview = () => {
        if (!chart) {
            return;
        }

        passTrendMode = "overview";
        activePassLevel = null;
        passTrendSeriesSelection = createDefaultPassSeriesSelection();
        setPassTrendDetailState(false);
        setChartClickability(chart, true);
        chart.setOption(buildPassChartOption(levelRows), true);
        setPassTrendContext(null);
        clearHighlightedLevelRow(getLevelTableRows());
        syncPassLegendState();
        setPassTrendNarrative(null);
        window.requestAnimationFrame(() => {
            chart.resize();
        });
    };

    const showPassTrendDetail = (levelName) => {
        if (!chart) {
            return;
        }

        const levelRow = levelRows.find((row) => row.level === levelName);
        if (!levelRow || !levelRow.programme_breakdown?.length) {
            return;
        }

        passTrendMode = "detail";
        activePassLevel = levelRow.level;
        passTrendSeriesSelection = createDefaultPassSeriesSelection();
        setPassTrendDetailState(true);
        setChartClickability(chart, false);
        setPassTrendContext(levelRow);
        highlightLevelRow(levelRow.level);
        syncPassLegendState();
        chart.setOption(buildPassLevelDetailOption(levelRow, chart.getWidth(), passTrendSeriesSelection), true);
        setPassTrendNarrative(levelRow);
        window.requestAnimationFrame(() => {
            chart.resize();
            chart.setOption(buildPassLevelDetailOption(levelRow, chart.getWidth(), passTrendSeriesSelection), true);
        });
    };

    if (chart && levelRows.length) {
        showPassTrendOverview();
        chart.on("click", (params) => {
            if (passTrendMode !== "overview") {
                return;
            }

            const selectedLevel = [params.name, params.axisValueLabel, params.axisValue, params.value]
                .find((value) => typeof value === "string" && value)
                || (typeof params.value === "number" ? levelRows[params.value]?.level : "");
            if (!selectedLevel) {
                return;
            }

            showPassTrendDetail(selectedLevel);
        });
    }

    if (passTrendReset) {
        passTrendReset.addEventListener("click", () => {
            showPassTrendOverview();
        });
    }

    if (passTrendJump) {
        passTrendJump.addEventListener("click", () => {
            if (!activePassLevel) {
                return;
            }
            jumpToLevelRow(context.elements, activePassLevel);
        });
    }

    if (passLegendButtons.length) {
        passLegendButtons.forEach((button) => {
            button.addEventListener("click", () => {
                if (passTrendMode !== "detail" || !activePassLevel || !chart) {
                    return;
                }

                const seriesKey = button.dataset.passSeries;
                if (!seriesKey || !(seriesKey in passTrendSeriesSelection)) {
                    return;
                }

                passTrendSeriesSelection = {
                    ...passTrendSeriesSelection,
                    [seriesKey]: !passTrendSeriesSelection[seriesKey],
                };
                syncPassLegendState();

                const levelRow = levelRows.find((row) => row.level === activePassLevel);
                if (!levelRow) {
                    return;
                }

                chart.setOption(
                    buildPassLevelDetailOption(levelRow, chart.getWidth(), passTrendSeriesSelection),
                    true,
                );
            });
        });
    }

    return {
        getChart: () => chart,
        resize: () => {
            if (!chart) {
                return;
            }

            chart.resize();

            if (passTrendMode === "detail" && activePassLevel) {
                const levelRow = levelRows.find((row) => row.level === activePassLevel);
                if (levelRow) {
                    chart.setOption(
                        buildPassLevelDetailOption(levelRow, chart.getWidth(), passTrendSeriesSelection),
                        true,
                    );
                }
                return;
            }

            chart.setOption(buildPassChartOption(levelRows), true);
        },
    };
};
