import { escapeTooltipHtml, formatChartLabel, setChartFallback } from "./shared.js";
import { initialiseOriginMapNarrative } from "./narratives.js";

const getLeafletLib = () => window.L || null;

const MAP_STYLE = {
    version: 8,
    sources: {
        osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "&copy; OpenStreetMap contributors | Leaflet",
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

const WORLD_VIEW_BOUNDS = [
    [-90, -180],
    [90, 180],
];
const WORLD_MAX_BOUNDS = [
    [-90, -180],
    [90, 180],
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

const createLeafletInstance = (container) => {
    const L = getLeafletLib();
    if (!L || !container) {
        return null;
    }

    const map = L.map(container, {
        center: [-19.0, 29.9], // Zimbabwe center
        zoom: 6, // Zimbabwe zoom level
        minZoom: 1,
        maxZoom: 18,
        worldCopyJump: false,
        attributionControl: true,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | Leaflet',
        maxZoom: 19,
    }).addTo(map);

    L.control.zoom({
        position: 'topright'
    }).addTo(map);

    return map;
};

const calculateDataBounds = (locationMapRows) => {
    if (!locationMapRows || locationMapRows.length === 0) {
        return null;
    }
    
    // Get all coordinate points
    const coordinates = locationMapRows
        .filter(row => row.latitude && row.longitude)
        .map(row => [parseFloat(row.latitude), parseFloat(row.longitude)]);
    
    if (coordinates.length === 0) {
        return null;
    }
    
    // Calculate bounds from actual data points
    const lats = coordinates.map(coord => coord[0]);
    const lngs = coordinates.map(coord => coord[1]);
    
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);
    
    // Add padding around bounds
    const padding = 0.5;
    
    // Return Leaflet bounds format: [[minLat, minLng], [maxLat, maxLng]]
    return [
        [minLat - padding, minLng - padding],
        [maxLat + padding, maxLng + padding]
    ];
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

    const L = getLeafletLib();
    if (!L) {
        console.error("Leaflet library not available:", L);
        setChartFallback(originMapChart, "Leaflet could not load. The geographic view is unavailable.");
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

    const map = createLeafletInstance(originMapChart);
    if (!map) {
        console.error("Map creation failed:", originMapChart);
        setChartFallback(originMapChart, "The interactive map could not start for this view.");
        return {
            getChart: () => null,
            resize: () => {},
        };
    }
    const markers = [];
    const maxCount = Math.max(...locationMapRows.map((row) => Number(row.count || 0)), 1);
    const sortedRows = [...locationMapRows].sort((left, right) => right.count - left.count || left.place.localeCompare(right.place));

    map.whenReady(() => {
        // Calculate dynamic bounds based on actual data
        const dataBounds = calculateDataBounds(locationMapRows);
        if (dataBounds) {
            map.fitBounds(dataBounds, { padding: buildMapPadding(originMapChart.clientWidth) });
        } else {
            map.setView([-19.0, 29.9], 6); // Default to Zimbabwe
        }

        sortedRows.forEach((row, index) => {
            const markerElement = buildMarkerElement(row, maxCount, index);
            const markerSize = 18 + Math.round((Number(row.count || 0) / Math.max(maxCount, 1)) * 20);
            const popup = L.popup({
                closeButton: false,
                closeOnClick: true,
                offset: [18, 0],
                maxWidth: 300,
                className: "demographic-origin-popup-shell",
            }).setContent(buildPopupMarkup(row));

            // Validate coordinates before creating marker
            const latitude = parseFloat(row.latitude);
            const longitude = parseFloat(row.longitude);
            
            // Check if coordinates are valid numbers and within reasonable ranges
            if (isNaN(latitude) || isNaN(longitude) || 
                latitude < -90 || latitude > 90 || 
                longitude < -180 || longitude > 180) {
                console.warn('Invalid coordinates for row:', row, 'Skipping marker creation');
                return; // Skip this row
            }

            const marker = L.marker([latitude, longitude], {
                icon: L.divIcon({
                    html: markerElement,
                    className: 'leaflet-div-icon',
                    iconSize: [markerSize, markerSize],
                    iconAnchor: [markerSize/2, markerSize/2]
                })
            })
            .bindPopup(popup)
            .addTo(map);

            markers.push(marker);
        });
    });

    return {
        getChart: () => map,
        resize: () => {
            map.invalidateSize();
        },
    };
};
