import {
    buildAnimationConfig,
    buildTooltipBase,
    buildTooltipMarkup,
    buildVerticalCategoryZoom,
    formatChartLabel,
    initialiseChart,
} from "./shared.js";
import { initialiseLocationMixNarrative } from "./narratives.js";

const GENDER_DIMENSIONS = [
    { key: "male", label: "Male" },
    { key: "female", label: "Female" },
    { key: "unspecified", label: "Unspecified" },
];
const CONTRAST_LABEL_RATIO = 0.3;

const getVisibleGenderDimensions = (rows) => GENDER_DIMENSIONS.filter(
    (dimension) => rows.some((row) => Number(row[dimension.key] || 0) > 0),
);

const buildLocationMixData = (rows, dimensions) => rows.flatMap(
    (row, rowIndex) => dimensions.map((dimension, columnIndex) => ({
        value: [columnIndex, rowIndex, Number(row[dimension.key] || 0)],
        place: row.place,
        genderLabel: dimension.label,
        total: row.total,
        share: row.share,
    })),
);

const getHeatmapLabelStyleName = (value, maxValue) => (
    value >= maxValue * CONTRAST_LABEL_RATIO ? "contrast" : "default"
);

const buildLocationMixChartOption = (rows) => {
    const visibleDimensions = getVisibleGenderDimensions(rows);
    const heatmapData = buildLocationMixData(rows, visibleDimensions);
    const maxValue = Math.max(...heatmapData.map((item) => item.value[2]), 1);

    return {
        ...buildAnimationConfig(rows),
        grid: { top: 28, right: rows.length > 8 ? 34 : 20, bottom: 18, left: 132, containLabel: true },
        dataZoom: buildVerticalCategoryZoom(rows),
        tooltip: {
            ...buildTooltipBase("item"),
            formatter: (params) => {
                const [, rowIndex, value] = params.value;
                const row = rows[rowIndex];
                return buildTooltipMarkup(`${row.place} | ${params.data.genderLabel}`, [
                    { label: "Students", value },
                    { label: "Location total", value: row.total },
                    { label: "Location share", value: row.share },
                ], { maxWidth: 224 });
            },
        },
        visualMap: {
            show: false,
            min: 0,
            max: maxValue,
            inRange: {
                color: ["#ecf5ff", "#9bd8e7", "#4fb0d1", "#1f4f88", "#082340"],
            },
        },
        xAxis: {
            type: "category",
            position: "top",
            data: visibleDimensions.map((dimension) => dimension.label),
            axisTick: { show: false },
            axisLine: { show: false },
            axisLabel: {
                color: "#082340",
                fontWeight: 700,
                fontSize: 12,
            },
        },
        yAxis: {
            type: "category",
            data: rows.map((row) => formatChartLabel(row.place, 18)),
            axisTick: { show: false },
            axisLine: { show: false },
            axisLabel: {
                color: "#082340",
                fontWeight: 600,
                width: 120,
                overflow: "truncate",
            },
        },
        series: [
            {
                name: "Birth location mix",
                type: "heatmap",
                data: heatmapData,
                itemStyle: {
                    borderWidth: 0,
                    borderColor: "transparent",
                },
                label: {
                    show: true,
                    fontWeight: 700,
                    formatter: ({ value }) => {
                        const numericValue = value[2];
                        if (!numericValue) {
                            return "";
                        }

                        return `{${getHeatmapLabelStyleName(numericValue, maxValue)}|${numericValue}}`;
                    },
                    rich: {
                        default: {
                            color: "#082340",
                            fontWeight: 700,
                        },
                        contrast: {
                            color: "#f8fbff",
                            fontWeight: 800,
                            textShadowColor: "rgba(8, 35, 64, 0.24)",
                            textShadowBlur: 6,
                        },
                    },
                },
                emphasis: {
                    itemStyle: {
                        borderWidth: 0,
                        borderColor: "transparent",
                    },
                },
            },
        ],
    };
};

export const initialiseLocationMixSection = (context) => {
    const { cardNarratives, locationMixRows } = context.data;
    initialiseLocationMixNarrative(context.elements, locationMixRows, cardNarratives, context.flags);

    const chart = initialiseChart(
        "demographic-location-mix-chart",
        locationMixRows,
        buildLocationMixChartOption,
        "No birth-location mix data matched the current filters.",
        (rows) => rows.some((row) => Number(row.total || 0) > 0),
    );

    return {
        getChart: () => chart,
        resize: () => {
            if (!chart) {
                return;
            }
            chart.resize();
            chart.setOption(buildLocationMixChartOption(locationMixRows), true);
        },
    };
};
