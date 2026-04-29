/* eslint-env browser */
/* global document, HTMLElement, HTMLSelectElement */

import { escapeTooltipHtml } from "./shared.js?v=20260416-home-drilldown08";

const DRILLDOWN_MODAL_ID = "home-drilldown-modal";
let lastFocusedElement = null;

const getDisplayValue = (value) => {
    if (value === 0) {
        return "0";
    }

    const text = String(value ?? "").trim();
    return text || "--";
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

const buildTableBodyHtml = (payload = {}) => {
    const columns = Array.isArray(payload.columns) ? payload.columns : [];
    const rows = Array.isArray(payload.rows) 
        ? [...payload.rows].sort((a, b) => {
            const getLastName = (row) => {
                const fullName = String(row?.[columns[0]?.key] || "").trim();
                const parts = fullName.split(/\s+/);
                return parts[parts.length - 1].toLowerCase();
            };

            return getLastName(a).localeCompare(getLastName(b));
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
                const cellValue = escapeTooltipHtml(getDisplayValue(row?.[column.key]));
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
        return `
        <div class="home-drilldown-hierarchical-item">
            <div class="home-drilldown-item-info">
                <span class="home-drilldown-item-label">${escapeTooltipHtml(item.label)}</span>
                <span class="home-drilldown-item-count">${getDisplayValue(item.count)}</span>
                ${item.programme_count ? `<span class="home-drilldown-item-subcount">${item.programme_count} programmes</span>` : ''}
            </div>
            <button class="home-drilldown-navigate-button" data-drilldown-navigate="${escapeTooltipHtml(navigateValue)}">
                View ${type === 'departments' ? 'Programmes' : 'Students'} →
            </button>
        </div>
        `;
    }).join("");

    return `
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
    if (payload.type && (payload.type === 'departments' || payload.type === 'programmes')) {
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

const renderModal = ({ title, subtitle = "", bodyHtml, toneClass = "", onPageChange = null, onPageSizeChange = null, onNavigate = null }) => {
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
                    onNavigate(navigateValue);
                }
            });
        });
    }

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
                <p class="home-drilldown-state-title">Loading student rows...</p>
                <p class="home-drilldown-state-copy">This drill-down is collecting the current student slice for you.</p>
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
    });
};
