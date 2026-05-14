/**
 * Topbar filter scope: URL + localStorage stay aligned so refresh and deep links
 * keep the same year / period / faculty, and returning from student detail
 * restores the list scope via preserved query strings.
 */

const FILTER_STORAGE_KEY = "dashboard_filters";
const FILTER_PARAM_NAMES = ["year", "period", "faculty"];

function readSavedFiltersFromStorage() {
    try {
        const raw = localStorage.getItem(FILTER_STORAGE_KEY);
        if (!raw) {
            return null;
        }
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object") {
            return null;
        }
        return {
            year: String(parsed.year || "").trim(),
            period: String(parsed.period || "").trim(),
            faculty: String(parsed.faculty || "").trim(),
        };
    } catch {
        return null;
    }
}

function writeStorageFromSearchParams(searchParams) {
    const next = {
        year: (searchParams.get("year") || "").trim(),
        period: (searchParams.get("period") || "").trim(),
        faculty: (searchParams.get("faculty") || "").trim(),
    };
    localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(next));
}

function hasActiveFilterScope(searchParams) {
    return FILTER_PARAM_NAMES.some((name) => (searchParams.get(name) || "").trim());
}

function hasSavedFilterScope(saved) {
    return Boolean(saved && (saved.year || saved.period || saved.faculty));
}

/**
 * If the URL has no filter query params but localStorage holds a scope,
 * replace the location so the server renders filtered data (avoids “All” data
 * with filter-looking selects after refresh).
 */
function applySavedFiltersToUrlIfMissing() {
    const params = new URLSearchParams(window.location.search);
    if (hasActiveFilterScope(params)) {
        writeStorageFromSearchParams(params);
        return false;
    }

    const saved = readSavedFiltersFromStorage();
    if (!hasSavedFilterScope(saved)) {
        return false;
    }

    const merged = new URLSearchParams(window.location.search);
    FILTER_PARAM_NAMES.forEach((name) => {
        const val = saved[name];
        if (val) {
            merged.set(name, val);
        }
    });

    const next = merged.toString();
    const curr = window.location.search.replace(/^\?/, "");
    if (next === curr) {
        return false;
    }

    const url = window.location.pathname + (next ? `?${next}` : "");
    window.location.replace(url);
    return true;
}

const saveFilters = () => {
    const filters = { year: "", period: "", faculty: "" };
    document.querySelectorAll(".filter-select").forEach((select) => {
        if (Object.prototype.hasOwnProperty.call(filters, select.name)) {
            filters[select.name] = select.value || "";
        }
    });
    localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(filters));
};

const initializeFilterPersistence = () => {
    if (applySavedFiltersToUrlIfMissing()) {
        return;
    }

    const filterSelects = document.querySelectorAll(".filter-select");
    filterSelects.forEach((select) => {
        select.addEventListener("change", () => {
            saveFilters();
            const form = select.closest("form");
            if (form) {
                form.submit();
            }
        });
    });
};

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeFilterPersistence);
} else {
    initializeFilterPersistence();
}
