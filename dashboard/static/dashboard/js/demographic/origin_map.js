import { escapeTooltipHtml, formatChartLabel, setChartFallback } from "./shared.js";
import { initialiseOriginMapNarrative } from "./narratives.js";

const getMapLibreLib = () => window.maplibregl || null;

const MAP_STYLE = {
    version: 8,
    sources: {
        osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "&copy; OpenStreetMap contributors",
            maxzoom: 19,
        },
    },
    layers: [
        {
            id: "osm",
            type: "raster",
            source: "osm",
        },
    ],
};

const ZIMBABWE_VIEW_BOUNDS = [
    [25.0, -22.6],
    [33.3, -15.4],
];
const ZIMBABWE_MAX_BOUNDS = [
    [24.3, -23.3],
    [34.0, -14.9],
];
const FEATURED_MARKER_LIMIT = 6;

const formatCount = (value) => Number(value || 0).toLocaleString();

const getMarkerPalette = (count, maxCount) => {
    const ratio = Number(count || 0) / Math.max(maxCount, 1);
    if (ratio >= 0.68) {
        return { start: "#082340", end: "#1f4f88" };
    }
    if (ratio >= 0.34) {
        return { start: "#0d325d", end: "#4fb0d1" };
    }
    return { start: "#54b7d6", end: "#9dddee" };
};

const buildPopupMarkup = (row) => `
    <div class="demographic-origin-popup">
        <p class="demographic-origin-popup-kicker">${escapeTooltipHtml(row.province)}</p>
        <h3 class="demographic-origin-popup-title">${escapeTooltipHtml(row.place)}</h3>
        <div class="demographic-origin-popup-grid">
            <span>Students</span><strong>${escapeTooltipHtml(formatCount(row.count))}</strong>
            <span>Share</span><strong>${escapeTooltipHtml(row.share)}</strong>
            <span>Male</span><strong>${escapeTooltipHtml(formatCount(row.male))}</strong>
            <span>Female</span><strong>${escapeTooltipHtml(formatCount(row.female))}</strong>
            ${Number(row.unspecified || 0) > 0 ? `<span>Unspecified</span><strong>${escapeTooltipHtml(formatCount(row.unspecified))}</strong>` : ""}
        </div>
    </div>
`;

const buildMarkerElement = (row, maxCount, rank) => {
    const markerElement = document.createElement("button");
    const palette = getMarkerPalette(row.count, maxCount);
    const markerSize = 18 + Math.round((Number(row.count || 0) / Math.max(maxCount, 1)) * 20);
    const isFeatured = rank < FEATURED_MARKER_LIMIT;
    const labelSideClass = Number(row.lng || 0) >= 31.8 ? "is-label-left" : "is-label-right";

    markerElement.type = "button";
    markerElement.className = `demographic-origin-marker${isFeatured ? " is-featured" : ""} ${labelSideClass}`.trim();
    markerElement.setAttribute("aria-label", `${row.place}: ${formatCount(row.count)} students`);
    markerElement.style.setProperty("--marker-size", `${markerSize}px`);
    markerElement.style.setProperty("--marker-start", palette.start);
    markerElement.style.setProperty("--marker-end", palette.end);

    markerElement.innerHTML = `
        <span class="demographic-origin-marker-bubble" aria-hidden="true"></span>
        ${isFeatured ? `
            <span class="demographic-origin-marker-label">
                <span class="demographic-origin-marker-name">${escapeTooltipHtml(formatChartLabel(row.place, 20))}</span>
                <span class="demographic-origin-marker-value">${escapeTooltipHtml(formatCount(row.count))}</span>
            </span>
        ` : ""}
    `.trim();

    return markerElement;
};

const buildMapPadding = (containerWidth = 0) => {
    if (containerWidth > 0 && containerWidth < 720) {
        return { top: 28, right: 22, bottom: 38, left: 22 };
    }
    return { top: 34, right: 34, bottom: 40, left: 34 };
};

const createMapLibreInstance = (container) => {
    const maplibre = getMapLibreLib();
    if (!maplibre || !container) {
        return null;
    }

    const map = new maplibre.Map({
        container,
        style: MAP_STYLE,
        center: [29.9, -19.0],
        zoom: 5.1,
        minZoom: 4.5,
        maxZoom: 8.5,
        maxBounds: ZIMBABWE_MAX_BOUNDS,
        attributionControl: true,
        cooperativeGestures: true,
        dragRotate: false,
        pitchWithRotate: false,
        touchPitch: false,
        renderWorldCopies: false,
    });

    map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-right");
    map.scrollZoom.disable();
    map.touchZoomRotate.disableRotation();
    return map;
};

export const initialiseOriginMapSection = (context) => {
    const { cardNarratives, locationMapRows, locationMapMeta } = context.data;
    const { originMapChart } = context.elements;
    initialiseOriginMapNarrative(context.elements, locationMapRows, locationMapMeta, cardNarratives, context.flags);

    if (!originMapChart) {
        return {
            getChart: () => null,
            resize: () => {},
        };
    }

    const maplibre = getMapLibreLib();
    if (!maplibre) {
        setChartFallback(originMapChart, "MapLibre could not load. The geographic view is unavailable.");
        return {
            getChart: () => null,
            resize: () => {},
        };
    }

    if (!locationMapRows.length || !locationMapRows.some((row) => Number(row.count || 0) > 0)) {
        setChartFallback(originMapChart, "No mapped birth-location data matched the current filters.");
        return {
            getChart: () => null,
            resize: () => {},
        };
    }

    originMapChart.classList.remove("is-empty");
    originMapChart.textContent = "";

    const map = createMapLibreInstance(originMapChart);
    if (!map) {
        setChartFallback(originMapChart, "The interactive map could not start for this view.");
        return {
            getChart: () => null,
            resize: () => {},
        };
    }

    const markers = [];
    const maxCount = Math.max(...locationMapRows.map((row) => Number(row.count || 0)), 1);
    const sortedRows = [...locationMapRows].sort((left, right) => right.count - left.count || left.place.localeCompare(right.place));

    map.on("load", () => {
        map.fitBounds(ZIMBABWE_VIEW_BOUNDS, {
            padding: buildMapPadding(originMapChart.clientWidth),
            duration: 0,
            maxZoom: 6.2,
        });

        sortedRows.forEach((row, index) => {
            const markerElement = buildMarkerElement(row, maxCount, index);
            const popup = new maplibre.Popup({
                closeButton: false,
                closeOnClick: true,
                offset: 18,
                maxWidth: "300px",
                className: "demographic-origin-popup-shell",
            }).setHTML(buildPopupMarkup(row));

            const marker = new maplibre.Marker({
                element: markerElement,
                anchor: "center",
            })
                .setLngLat([Number(row.lng), Number(row.lat)])
                .setPopup(popup)
                .addTo(map);

            markers.push(marker);
        });
    });

    return {
        getChart: () => null,
        resize: () => {
            map.resize();
        },
    };
};
