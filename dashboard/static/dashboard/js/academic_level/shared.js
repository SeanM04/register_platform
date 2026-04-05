export const echartsLib = window.echarts;
export const PASS_RATE_TARGET = 85;
export const numberFormatter = new Intl.NumberFormat();
export const VALID_CARD_SEVERITIES = new Set(["stable", "medium", "high"]);
export const VALID_CARD_CONFIDENCES = new Set(["low", "medium", "high"]);

export const parseJsonScript = (id, fallback = []) => {
    const element = document.getElementById(id);
    if (!element) {
        return fallback;
    }

    try {
        const parsedValue = JSON.parse(element.textContent);
        return parsedValue ?? fallback;
    } catch (error) {
        return fallback;
    }
};

export const setChartFallback = (element, message) => {
    if (!element) {
        return;
    }

    element.classList.add("is-empty");
    element.textContent = message;
};

export const createDefaultPassSeriesSelection = () => ({
    enrolment: true,
    average_mark: true,
});

export const buildGradient = (startColor, endColor) => (
    new echartsLib.graphic.LinearGradient(0, 0, 1, 0, [
        { offset: 0, color: startColor },
        { offset: 1, color: endColor },
    ])
);

export const formatChartLabel = (value, maxLength = 26) => {
    const text = String(value || "");
    return text.length > maxLength ? `${text.slice(0, Math.max(maxLength - 3, 1))}...` : text;
};

export const formatTooltipTitle = (value, maxLength = 40) => (
    value ? formatChartLabel(value, maxLength) : "Not recorded"
);

export const escapeTooltipHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

export const formatAcademicLevelTick = (value, compact = false) => {
    const match = String(value || "").match(/^Year\s+(\d+),\s*Semester\s+(\d+)$/i);
    if (match) {
        return compact ? `Y${match[1]}\nS${match[2]}` : `Year ${match[1]}\nSemester ${match[2]}`;
    }

    return compact ? String(value || "").replace(/,\s*/g, "\n") : String(value || "");
};

export const toTitleCase = (value) => String(value || "")
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());

export const stripCommonPrefixWords = (labels) => {
    if (!labels.length) {
        return labels;
    }

    const tokenLists = labels.map((label) => String(label || "").trim().split(/\s+/).filter(Boolean));
    if (!tokenLists.every((tokens) => tokens.length >= 3)) {
        return labels;
    }

    let prefixLength = 0;
    while (true) {
        const token = tokenLists[0][prefixLength];
        if (!token) {
            break;
        }

        const everyMatches = tokenLists.every(
            (tokens) => tokens[prefixLength] && tokens[prefixLength].toLowerCase() === token.toLowerCase(),
        );

        if (!everyMatches) {
            break;
        }

        prefixLength += 1;
    }

    if (prefixLength < 2) {
        return labels;
    }

    return tokenLists.map((tokens, index) => {
        const trimmed = tokens.slice(prefixLength).join(" ");
        return trimmed || labels[index];
    });
};

export const wrapAxisLabel = (value, options = {}) => {
    const maxLineLength = options.maxLineLength || 16;
    const maxLines = options.maxLines || 3;
    const words = String(value || "").split(/\s+/).filter(Boolean);

    if (!words.length) {
        return "";
    }

    const lines = [];
    let currentLine = "";

    words.forEach((word) => {
        const candidate = currentLine ? `${currentLine} ${word}` : word;
        if (candidate.length <= maxLineLength || !currentLine) {
            currentLine = candidate;
            return;
        }

        lines.push(currentLine);
        currentLine = word;
    });

    if (currentLine) {
        lines.push(currentLine);
    }

    if (lines.length > maxLines) {
        const visibleLines = lines.slice(0, maxLines);
        const overflowText = lines.slice(maxLines - 1).join(" ");
        visibleLines[maxLines - 1] = formatChartLabel(overflowText, maxLineLength);
        return visibleLines.join("\n");
    }

    const normalizedLines = [...lines];
    normalizedLines[normalizedLines.length - 1] = formatChartLabel(
        normalizedLines[normalizedLines.length - 1],
        maxLineLength,
    );
    return normalizedLines.join("\n");
};

export const buildProgrammeAxisLabels = (rows, compact = false, narrow = false) => {
    const strippedLabels = stripCommonPrefixWords(rows.map((row) => row.programme));
    const maxLineLength = narrow ? 10 : compact ? 12 : 16;
    const maxLines = narrow ? 2 : compact ? 3 : 2;

    return strippedLabels.map((label) => wrapAxisLabel(toTitleCase(label), { maxLineLength, maxLines }));
};

export const formatStoryProgrammeName = (value) => {
    const cleanedValue = String(value || "")
        .replace(/^(Bachelor|Master(?:s)?) Of\s+/i, "")
        .replace(/\s+Honours Degree$/i, "")
        .trim();
    return formatChartLabel(toTitleCase(cleanedValue || value), 34);
};

export const formatLegendProgrammeName = (value) => String(value || "")
    .replace(/^(Bachelor|Master(?:s)?) Of\s+/i, "")
    .replace(/\s+Honours Degree$/i, "")
    .trim();

export const buildAnimationConfig = (rows) => ({
    animation: rows.length <= 60,
    animationDuration: rows.length <= 60 ? 700 : 0,
    animationDurationUpdate: rows.length <= 60 ? 300 : 0,
});

export const buildTooltipTextStyle = () => ({
    color: "#ffffff",
    fontSize: 11,
    fontWeight: 600,
    lineHeight: 16,
});

export const buildTooltipBase = (trigger) => ({
    trigger,
    triggerOn: "mousemove|click",
    backgroundColor: "rgba(8, 35, 64, 0.94)",
    borderWidth: 0,
    padding: [6, 8],
    confine: true,
    extraCssText: "max-width: 260px; border-radius: 10px; box-shadow: 0 10px 24px rgba(8, 35, 64, 0.2); white-space: normal;",
    textStyle: buildTooltipTextStyle(),
});

export const buildTooltipMarkup = (title, rows, options = {}) => {
    const maxWidth = options.maxWidth || 248;
    const titleHtml = escapeTooltipHtml(title);
    const rowsHtml = rows
        .filter((row) => row && row.value !== undefined && row.value !== null && row.value !== "")
        .map((row) => `
            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">
                <span style="color:rgba(255,255,255,0.76); font-weight:500;">${escapeTooltipHtml(row.label)}</span>
                <span style="text-align:right; font-weight:700;">${escapeTooltipHtml(row.value)}</span>
            </div>
        `)
        .join("");

    return `
        <div style="display:grid; gap:6px; min-width:170px; max-width:${maxWidth}px;">
            <div style="font-size:12px; font-weight:800; line-height:1.35; white-space:normal; word-break:break-word;">
                ${titleHtml}
            </div>
            <div style="display:grid; gap:4px;">
                ${rowsHtml}
            </div>
        </div>
    `;
};

export const buildHiddenAxisPointerStyle = () => ({
    show: false,
    snap: false,
    lineStyle: {
        opacity: 0,
    },
    shadowStyle: {
        opacity: 0,
    },
    crossStyle: {
        opacity: 0,
    },
    label: {
        show: false,
    },
});

export const getTooltipDataIndex = (params) => (
    Array.isArray(params) ? params[0]?.dataIndex : params?.dataIndex
);

export const buildAxisPointerConfig = (type = "line") => ({
    show: true,
    snap: type === "line",
    type,
    lineStyle: {
        opacity: 0,
    },
    shadowStyle: {
        opacity: 0,
    },
    crossStyle: {
        opacity: 0,
    },
    label: {
        show: false,
    },
});

export const buildHorizontalCategoryZoom = (rows) => {
    const visibleCount = 8;
    if (rows.length <= visibleCount) {
        return [];
    }

    return [
        {
            type: "inside",
            xAxisIndex: 0,
            startValue: 0,
            endValue: visibleCount - 1,
            filterMode: "weakFilter",
        },
        {
            type: "slider",
            xAxisIndex: 0,
            left: 72,
            right: 24,
            bottom: 8,
            height: 14,
            startValue: 0,
            endValue: visibleCount - 1,
            filterMode: "weakFilter",
            brushSelect: false,
            moveHandleSize: 0,
            textStyle: { color: "#4b5563" },
            borderColor: "#d9e2ec",
            fillerColor: "rgba(79, 176, 209, 0.18)",
            dataBackground: {
                lineStyle: { color: "#9cabbc" },
                areaStyle: { color: "rgba(156, 171, 188, 0.18)" },
            },
        },
    ];
};

export const buildVerticalCategoryZoom = (rows) => {
    const visibleCount = 8;
    if (rows.length <= visibleCount) {
        return [];
    }

    return [
        {
            type: "inside",
            yAxisIndex: 0,
            startValue: 0,
            endValue: visibleCount - 1,
            filterMode: "weakFilter",
        },
        {
            type: "slider",
            orient: "vertical",
            yAxisIndex: 0,
            right: 2,
            top: 8,
            bottom: 8,
            width: 12,
            startValue: 0,
            endValue: visibleCount - 1,
            filterMode: "weakFilter",
            brushSelect: false,
            moveHandleSize: 0,
            textStyle: { color: "#4b5563" },
            borderColor: "#d9e2ec",
            fillerColor: "rgba(79, 176, 209, 0.18)",
            dataBackground: {
                lineStyle: { color: "#9cabbc" },
                areaStyle: { color: "rgba(156, 171, 188, 0.18)" },
            },
        },
    ];
};

export const hasMeaningfulRows = (rows, key) => rows.some((row) => Number(row[key] || 0) > 0);

export const initialiseChart = (elementId, rows, optionBuilder, emptyMessage, validator = null, initOptions = {}) => {
    const element = document.getElementById(elementId);
    if (!element) {
        return null;
    }

    if (!echartsLib) {
        setChartFallback(element, "ECharts could not load. The table below is still available.");
        return null;
    }

    if (!rows.length || (validator && !validator(rows))) {
        setChartFallback(element, emptyMessage);
        return null;
    }

    const renderer = initOptions.renderer || "canvas";
    const chart = echartsLib.init(element, null, {
        renderer,
        useDirtyRect: renderer === "canvas",
    });
    chart.setOption(optionBuilder(rows, element.clientWidth));
    return chart;
};

export const setChartClickability = (chart, isClickable) => {
    if (!chart) {
        return;
    }

    chart.getDom().style.cursor = isClickable ? "pointer" : "default";
};
