export const echartsLib = window.echarts;
export const numberFormatter = new Intl.NumberFormat();

export const PROGRAMME_COLORS = {
    navy: "#163d69",
    teal: "#2f80ac",
    sky: "#69c1df",
    mint: "#60bf94",
    amber: "#f1b55d",
    rose: "#d76770",
    ink: "#12395f",
    slate: "#4f6583",
    pale: "#dbeaf5",
};

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

export const formatCount = (value) => numberFormatter.format(Number(value || 0));

export const setChartFallback = (element, message) => {
    if (!element) {
        return;
    }

    element.classList.add("is-empty");
    element.textContent = message;
};

export const createEmptyController = () => ({
    getChart: () => null,
    resize: () => {},
});

export const buildGradient = (startColor, endColor, direction = "vertical") => {
    if (!echartsLib) {
        return startColor;
    }

    const isHorizontal = direction === "horizontal";
    return new echartsLib.graphic.LinearGradient(
        0,
        0,
        isHorizontal ? 1 : 0,
        isHorizontal ? 0 : 1,
        [
            { offset: 0, color: startColor },
            { offset: 1, color: endColor },
        ],
    );
};

export const wrapAxisLabel = (value, options = {}) => {
    const maxLineLength = options.maxLineLength || 16;
    const maxLines = options.maxLines || 2;
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
        visibleLines[maxLines - 1] = `${visibleLines[maxLines - 1].slice(0, Math.max(maxLineLength - 3, 1))}...`;
        return visibleLines.join("\n");
    }

    return lines.join("\n");
};

export const escapeTooltipHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

export const buildTooltipBase = (trigger = "item") => ({
    trigger,
    triggerOn: "mousemove|click",
    confine: true,
    borderWidth: 0,
    padding: [6, 8],
    backgroundColor: "rgba(8, 35, 64, 0.94)",
    textStyle: {
        color: "#ffffff",
        fontSize: 11,
        fontWeight: 600,
        lineHeight: 16,
    },
    extraCssText: "max-width: 280px; border-radius: 10px; box-shadow: 0 10px 24px rgba(8, 35, 64, 0.2); white-space: normal;",
});

export const buildTooltipMarkup = (title, rows) => {
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
        <div style="display:grid; gap:6px; min-width:180px; max-width:260px;">
            <div style="font-size:12px; font-weight:800; line-height:1.35; white-space:normal; word-break:break-word;">
                ${titleHtml}
            </div>
            <div style="display:grid; gap:4px;">
                ${rowsHtml}
            </div>
        </div>
    `;
};
