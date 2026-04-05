export const getEchartsLib = () => window.echarts || null;

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

export const buildGradient = (startColor, endColor, orientation = "horizontal") => {
    const echartsLib = getEchartsLib();
    if (!echartsLib) {
        return endColor;
    }

    const coordinates = orientation === "vertical"
        ? [0, 1, 0, 0]
        : [0, 0, 1, 0];

    return new echartsLib.graphic.LinearGradient(...coordinates, [
        { offset: 0, color: startColor },
        { offset: 1, color: endColor },
    ]);
};

export const escapeTooltipHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

export const formatChartLabel = (value, maxLength = 26) => {
    const text = String(value || "");
    return text.length > maxLength ? `${text.slice(0, Math.max(maxLength - 3, 1))}...` : text;
};

export const buildAnimationConfig = (rows) => ({
    animation: rows.length <= 60,
    animationDuration: rows.length <= 60 ? 700 : 0,
    animationDurationUpdate: rows.length <= 60 ? 300 : 0,
});

export const buildTooltipBase = (trigger = "item") => ({
    trigger,
    triggerOn: "mousemove|click",
    backgroundColor: "rgba(8, 35, 64, 0.94)",
    borderWidth: 0,
    padding: [6, 8],
    confine: true,
    extraCssText: "max-width: 260px; border-radius: 10px; box-shadow: 0 10px 24px rgba(8, 35, 64, 0.2); white-space: normal;",
    textStyle: {
        color: "#ffffff",
        fontSize: 11,
        fontWeight: 600,
        lineHeight: 16,
    },
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

export const buildVerticalCategoryZoom = (rows, options = {}) => {
    const visibleCount = options.visibleCount || 6;
    const showSlider = Boolean(options.showSlider);

    if (rows.length <= visibleCount) {
        return [];
    }

    const zoomConfig = [
        {
            type: "inside",
            yAxisIndex: 0,
            startValue: 0,
            endValue: visibleCount - 1,
            filterMode: "weakFilter",
        },
    ];

    if (showSlider) {
        zoomConfig.push(
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
        );
    }

    return zoomConfig;
};

export const initialiseChart = (elementId, rows, optionBuilder, emptyMessage, validator = null, initOptions = {}) => {
    const element = document.getElementById(elementId);
    if (!element) {
        return null;
    }

    const echartsLib = getEchartsLib();
    if (!echartsLib) {
        setChartFallback(element, "ECharts could not load. The risk register is still available.");
        return null;
    }

    if (!rows.length || (validator && !validator(rows))) {
        setChartFallback(element, emptyMessage);
        return null;
    }

    element.classList.remove("is-empty");
    element.textContent = "";

    const renderer = initOptions.renderer || "canvas";
    const chart = echartsLib.init(element, null, {
        renderer,
        useDirtyRect: renderer === "canvas",
    });
    chart.setOption(optionBuilder(rows, element.clientWidth));
    return chart;
};
