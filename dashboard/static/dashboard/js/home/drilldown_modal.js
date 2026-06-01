/* eslint-env browser */
/* global document, HTMLElement, HTMLSelectElement */

import { escapeTooltipHtml } from "./shared.js?v=20260416-home-drilldown08";

const DRILLDOWN_MODAL_ID = "home-drilldown-modal";
let lastFocusedElement = null;

const getStudentNameSortKey = (fullName = "") => {
    const normalized = String(fullName || "").trim().replace(/\s+/g, " ");
    if (!normalized) {
        return { surname: "", givenNames: "" };
    }
    const parts = normalized.split(" ");
    return {
        surname: String(parts[parts.length - 1] || "").toLowerCase(),
        givenNames: String(parts.slice(0, -1).join(" ") || "").toLowerCase(),
    };
};

const getDisplayValue = (value) => {
    if (value === 0) {
        return "0";
    }

    const text = String(value ?? "").trim();
    return text || "--";
};

const buildStatusCellHtml = (value) => {
    const text = getDisplayValue(value);
    const normalized = String(text).trim().toLowerCase();
    let toneClass = "";
    if (normalized === "on time") {
        toneClass = "is-on-time";
    } else if (normalized === "delayed") {
        toneClass = "is-delayed";
    }

    if (!toneClass) {
        return escapeTooltipHtml(text);
    }

    return `<span class="home-drilldown-status ${toneClass}">${escapeTooltipHtml(text)}</span>`;
};

const buildSummaryBodyHtml = (items = []) => {
    if (!items.length) {
        return `
            <div class="home-drilldown-state">
                <p class="home-drilldown-state-title">No detail is available for this selection yet.</p>
            </div>
        `.trim();
    }

    const itemsHtml = items.map((item) => `
        <div class="home-drilldown-summary-row">
            <span class="home-drilldown-summary-label">${escapeTooltipHtml(item?.label || "Item")}</span>
            <span class="home-drilldown-summary-value">${escapeTooltipHtml(getDisplayValue(item?.value))}</span>
        </div>
    `).join("");

    return `
        <div class="home-drilldown-summary-list">
            ${itemsHtml}
        </div>
    `.trim();
};

const buildBreadcrumbHtml = (payload = {}) => {
    const breadcrumbs = Array.isArray(payload.breadcrumbs) ? payload.breadcrumbs : [];
    if (!breadcrumbs.length) {
        return "";
    }

    const itemsHtml = breadcrumbs.map((item, index) => {
        const isLast = index === breadcrumbs.length - 1;
        const label = escapeTooltipHtml(item?.label || "Details");
        if (isLast || !item?.chart || !item?.bucket) {
            return `<span class="home-drilldown-breadcrumb-current">${label}</span>`;
        }
        return `
            <button class="home-drilldown-breadcrumb" type="button" data-drilldown-breadcrumb-chart="${escapeTooltipHtml(item.chart)}" data-drilldown-breadcrumb-bucket="${escapeTooltipHtml(item.bucket)}">${label}</button>
        `.trim();
    }).join('<span class="home-drilldown-breadcrumb-separator">/</span>');

    return `<nav class="home-drilldown-breadcrumbs" aria-label="Drill-down breadcrumb">${itemsHtml}</nav>`;
};

const buildToolbarHtml = (payload = {}) => {
    const hasRows = Array.isArray(payload.rows) && payload.rows.length;
    const hasItems = Array.isArray(payload.data) && payload.data.length;
    if (!hasRows && !hasItems) {
        return "";
    }

    return `
        <div class="home-drilldown-toolbar">
            <label class="home-drilldown-search-label">
                <span class="home-drilldown-search-text">Search</span>
                <input class="home-drilldown-search" type="search" data-drilldown-search placeholder="Search current results">
            </label>
            <button class="home-drilldown-export" type="button" data-drilldown-export>Export CSV</button>
        </div>
    `.trim();
};

const buildTableBodyHtml = (payload = {}) => {
    const columns = Array.isArray(payload.columns) ? payload.columns : [];
    const rows = Array.isArray(payload.rows) 
        ? [...payload.rows].sort((a, b) => {
            const aName = getStudentNameSortKey(a?.[columns[0]?.key] || "");
            const bName = getStudentNameSortKey(b?.[columns[0]?.key] || "");
            return (
                aName.surname.localeCompare(bName.surname)
                || aName.givenNames.localeCompare(bName.givenNames)
                || String(a?.registration_number || a?.regnum || a?.detail_slug || "").localeCompare(
                    String(b?.registration_number || b?.regnum || b?.detail_slug || "")
                )
            );
        })
        : [];
    
    console.log("DEBUG: buildTableBodyHtml - columns:", columns.length, "rows:", rows.length);
    
    if (!columns.length) {
        return `
            <div class="home-drilldown-state">
                <p class="home-drilldown-state-title">No student columns were returned for this drill-down.</p>
            </div>
        `.trim();
    }

    const headerHtml = columns.map((column) => `
        <th scope="col">${escapeTooltipHtml(column?.label || column?.key || "Column")}</th>
    `).join("");

    const rowsHtml = rows.length
        ? rows.map((row) => {
            const cellsHtml = columns.map((column, columnIndex) => {
                const rawValue = row?.[column.key];
                const cellValue = column?.key === "status"
                    ? buildStatusCellHtml(rawValue)
                    : escapeTooltipHtml(getDisplayValue(rawValue));
                const detailUrl = String(row?.detail_url || "").trim();
                if (columnIndex === 0 && detailUrl) {
                    return `
                        <td>
                            <a class="home-drilldown-link" href="${escapeTooltipHtml(detailUrl)}">${cellValue}</a>
                        </td>
                    `.trim();
                }

                return `<td>${cellValue}</td>`;
            }).join("");

            return `<tr>${cellsHtml}</tr>`;
        }).join("")
        : `
            <tr>
                <td class="home-drilldown-empty" colspan="${columns.length}">No students matched this selection.</td>
            </tr>
        `.trim();

    const result = `
        ${buildBreadcrumbHtml(payload)}
        ${buildToolbarHtml(payload)}
        <div class="home-drilldown-table-wrap">
            <table class="home-drilldown-table">
                <thead>
                    <tr>${headerHtml}</tr>
                </thead>
                <tbody>
                    ${rowsHtml}
                </tbody>
            </table>
        </div>
        ${buildPaginationHtml(payload)}
    `.trim();
    
    console.log("DEBUG: buildTableBodyHtml - result length:", result.length);
    return result;
};

const buildPaginationHtml = (payload = {}) => {
    // Handle both old and new pagination field names for compatibility
    const page = Number(payload.current_page || payload.page) || 1;
    const pageSize = Number(payload.page_size) || 100;
    const totalCount = Number(payload.total_items || payload.total_count) || 0;
    const pageCount = Number(payload.total_pages || payload.page_count) || (pageSize ? Math.max(1, Math.ceil(totalCount / pageSize)) : 1);

    const sizeInfoHtml = `
        <div class="home-drilldown-page-size-pill">${pageSize} rows per page</div>
    `.trim();

    const previousDisabled = page <= 1 ? "disabled" : "";
    const nextDisabled = page >= pageCount ? "disabled" : "";

    return `
        <div class="home-drilldown-pagination">
            ${sizeInfoHtml}
            <div class="home-drilldown-pagination-controls">
                <button class="home-drilldown-pagination-button page-link page-link-arrow" type="button" data-drilldown-page="${page - 1}" ${previousDisabled}>Prev</button>
                <span class="home-drilldown-pagination-info">Page ${page} of ${pageCount}</span>
                <button class="home-drilldown-pagination-button page-link page-link-arrow" type="button" data-drilldown-page="${page + 1}" ${nextDisabled}>Next</button>
            </div>
        </div>
    `.trim();
};

const buildHierarchicalListHtml = (payload = {}) => {
    const { type, data = [] } = payload;
    if (!data.length) {
        return `
            <div class="home-drilldown-state">
                <p class="home-drilldown-state-title">No data available for this selection.</p>
            </div>
        `.trim();
    }

    const itemsHtml = data.map((item) => {
        // Use key for navigation if available (for programmes), otherwise use label (for departments)
        const navigateValue = item.key || item.label;
        const navigateChart = item.next_chart || "";
        const navigateBucket = item.next_bucket || navigateValue;
        return `
        <div class="home-drilldown-hierarchical-item">
            <div class="home-drilldown-item-info">
                <span class="home-drilldown-item-label">${escapeTooltipHtml(item.label)}</span>
                <span class="home-drilldown-item-count">${getDisplayValue(item.count)}</span>
                ${item.department ? `<span class="home-drilldown-item-subcount">${escapeTooltipHtml(item.department)}</span>` : ''}
                ${item.programme_count ? `<span class="home-drilldown-item-subcount">${item.programme_count} programmes</span>` : ''}
            </div>
            <button class="home-drilldown-navigate-button" data-drilldown-navigate="${escapeTooltipHtml(navigateValue)}" data-drilldown-navigate-chart="${escapeTooltipHtml(navigateChart)}" data-drilldown-navigate-bucket="${escapeTooltipHtml(navigateBucket)}">
                View ${type === 'departments' ? 'Programmes' : 'Students'} &rarr;
            </button>
        </div>
        `;
    }).join("");

    return `
        ${buildBreadcrumbHtml(payload)}
        ${buildToolbarHtml(payload)}
        <div class="home-drilldown-hierarchical-list">
            ${itemsHtml}
        </div>
    `.trim();
};

const buildBodyHtml = (payloadOrTitle, legacyItems = []) => {
    if (typeof payloadOrTitle === "string") {
        return buildSummaryBodyHtml(legacyItems);
    }

    const payload = payloadOrTitle || {};
    
    if (Array.isArray(payload.items) && !payload.columns) {
        return buildSummaryBodyHtml(payload.items);
    }

    // Handle hierarchical drilldown data
    if (payload.type && (payload.type === 'departments' || payload.type === 'programmes' || payload.type === 'levels')) {
        return buildHierarchicalListHtml(payload);
    }

    return buildTableBodyHtml(payload);
};

const buildTitle = (payloadOrTitle) => {
    if (typeof payloadOrTitle === "string") {
        return payloadOrTitle;
    }

    return String(payloadOrTitle?.title || "Drill-down details").trim() || "Drill-down details";
};

const buildSubtitle = (payloadOrTitle) => {
    if (typeof payloadOrTitle === "string") {
        return "";
    }

    return String(payloadOrTitle?.subtitle || "").trim();
};

const handleEscapeKey = (event) => {
    if (event.key === "Escape") {
        closeDrillDownModal();
    }
};

const normaliseCsvValue = (value) => {
    const text = String(value ?? "").replace(/\s+/g, " ").trim();
    return `"${text.replace(/"/g, '""')}"`;
};

const downloadCsv = (filename, rows) => {
    const csv = rows.map((row) => row.map(normaliseCsvValue).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
};

const initialiseSearchAndExport = (modal, payload = {}) => {
    const searchInput = modal.querySelector("[data-drilldown-search]");
    const exportButton = modal.querySelector("[data-drilldown-export]");

    if (searchInput) {
        searchInput.addEventListener("input", () => {
            const query = searchInput.value.trim().toLowerCase();
            modal.querySelectorAll(".home-drilldown-table tbody tr, .home-drilldown-hierarchical-item").forEach((row) => {
                row.hidden = Boolean(query) && !row.textContent.toLowerCase().includes(query);
            });
        });
    }

    if (!exportButton) {
        return;
    }

    exportButton.addEventListener("click", () => {
        const columns = Array.isArray(payload.columns) ? payload.columns : [];
        const rows = Array.isArray(payload.rows) ? payload.rows : [];
        const hierarchy = Array.isArray(payload.data) ? payload.data : [];
        const filenameBase = String(payload.title || "drilldown")
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-|-$/g, "") || "drilldown";

        if (columns.length && rows.length) {
            downloadCsv(
                `${filenameBase}.csv`,
                [
                    columns.map((column) => column.label || column.key || "Column"),
                    ...rows.map((row) => columns.map((column) => row?.[column.key] ?? "")),
                ],
            );
            return;
        }

        if (hierarchy.length) {
            downloadCsv(
                `${filenameBase}.csv`,
                [
                    ["Label", "Count", "Department"],
                    ...hierarchy.map((item) => [item.label || "", item.count || "", item.department || ""]),
                ],
            );
        }
    });
};

export const isDrillDownModalOpen = () => Boolean(document.getElementById(DRILLDOWN_MODAL_ID));

export const closeDrillDownModal = () => {
    const modal = document.getElementById(DRILLDOWN_MODAL_ID);
    if (modal) {
        modal.remove();
    }

    document.body.classList.remove("has-home-drilldown-modal");
    document.removeEventListener("keydown", handleEscapeKey);

    if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
        lastFocusedElement.focus();
    }
    lastFocusedElement = null;
};

const renderModal = ({ title, subtitle = "", bodyHtml, toneClass = "", onPageChange = null, onPageSizeChange = null, onNavigate = null, payload = null }) => {
    closeDrillDownModal();

    lastFocusedElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;

    const modal = document.createElement("div");
    modal.id = DRILLDOWN_MODAL_ID;
    modal.className = "home-drilldown-modal";
    modal.innerHTML = `
        <div class="home-drilldown-dialog ${toneClass}" role="dialog" aria-modal="true" aria-labelledby="home-drilldown-title" aria-describedby="home-drilldown-subtitle" tabindex="-1">
            <div class="home-drilldown-header">
                <div class="home-drilldown-heading">
                    <h2 class="home-drilldown-title" id="home-drilldown-title">${escapeTooltipHtml(title)}</h2>
                    <p class="home-drilldown-subtitle" id="home-drilldown-subtitle">${escapeTooltipHtml(subtitle)}</p>
                </div>
                <button class="home-drilldown-close" type="button" data-drilldown-close aria-label="Close student drill-down">Close</button>
            </div>
            <div class="home-drilldown-body">
                ${bodyHtml}
            </div>
        </div>
    `.trim();

    modal.addEventListener("click", (event) => {
        if (event.target === modal) {
            closeDrillDownModal();
        }
    });

    const closeButton = modal.querySelector("[data-drilldown-close]");
    if (closeButton) {
        closeButton.addEventListener("click", () => {
            closeDrillDownModal();
        });
    }

    const pageButtons = modal.querySelectorAll("[data-drilldown-page]");
    if (typeof onPageChange === "function" && pageButtons.length) {
        pageButtons.forEach((button) => {
            button.addEventListener("click", () => {
                const pageValue = Number(button.dataset.drilldownPage);
                if (!Number.isNaN(pageValue)) {
                    onPageChange(pageValue);
                }
            });
        });
    }

    const pageSizeSelect = modal.querySelector("[data-drilldown-page-size]");
    if (typeof onPageSizeChange === "function" && pageSizeSelect instanceof HTMLSelectElement) {
        pageSizeSelect.addEventListener("change", () => {
            const selectedValue = Number(pageSizeSelect.value);
            if (!Number.isNaN(selectedValue) && selectedValue > 0) {
                onPageSizeChange(selectedValue);
            }
        });
    }

    // Handle hierarchical navigation buttons
    const navigateButtons = modal.querySelectorAll("[data-drilldown-navigate]");
    if (typeof onNavigate === "function" && navigateButtons.length) {
        navigateButtons.forEach((button) => {
            button.addEventListener("click", () => {
                const navigateValue = button.dataset.drilldownNavigate;
                if (navigateValue) {
                    onNavigate({
                        value: navigateValue,
                        chart: button.dataset.drilldownNavigateChart || "",
                        bucket: button.dataset.drilldownNavigateBucket || navigateValue,
                    });
                }
            });
        });
    }

    const breadcrumbButtons = modal.querySelectorAll("[data-drilldown-breadcrumb-chart]");
    if (typeof onNavigate === "function" && breadcrumbButtons.length) {
        breadcrumbButtons.forEach((button) => {
            button.addEventListener("click", () => {
                onNavigate({
                    chart: button.dataset.drilldownBreadcrumbChart || "",
                    bucket: button.dataset.drilldownBreadcrumbBucket || "",
                });
            });
        });
    }

    initialiseSearchAndExport(modal, payload || {});

    document.body.appendChild(modal);
    document.body.classList.add("has-home-drilldown-modal");
    document.addEventListener("keydown", handleEscapeKey);

    const dialog = modal.querySelector(".home-drilldown-dialog");
    if (dialog instanceof HTMLElement) {
        dialog.focus();
    }
};

export const showLoadingDrillDownModal = (title, subtitle = "") => {
    renderModal({
        title,
        subtitle,
        toneClass: "is-loading",
        bodyHtml: `
            <div class="home-drilldown-state">
                <div class="home-drilldown-spinner"></div>
                <p class="home-drilldown-state-title">Loading student data...</p>
                <p class="home-drilldown-state-copy">Please wait while we gather the requested information.</p>
            </div>
        `.trim(),
    });
};

export const showDrillDownErrorModal = (title, subtitle = "") => {
    renderModal({
        title,
        subtitle,
        toneClass: "is-error",
        bodyHtml: `
            <div class="home-drilldown-state">
                <p class="home-drilldown-state-title">The student drill-down could not be loaded.</p>
                <p class="home-drilldown-state-copy">Refresh the dashboard and try the selection again.</p>
            </div>
        `.trim(),
    });
};

export const showDrillDownModal = (payloadOrTitle, legacyItems = [], options = {}) => {
    console.log("DEBUG: showDrillDownModal called with:", payloadOrTitle, "options:", options);
    renderModal({
        title: buildTitle(payloadOrTitle),
        subtitle: buildSubtitle(payloadOrTitle),
        bodyHtml: buildBodyHtml(payloadOrTitle, legacyItems),
        onPageChange: options.onPageChange,
        onPageSizeChange: options.onPageSizeChange,
        onNavigate: options.onNavigate,
        payload: typeof payloadOrTitle === "string" ? null : payloadOrTitle,
    });
};
