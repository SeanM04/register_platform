import { escapeTooltipHtml } from "./shared.js?v=20260412-insights-shell01";

const DRILLDOWN_MODAL_ID = "insights-drilldown-modal";
let lastFocusedElement = null;

const getDisplayValue = (value) => {
    if (value === null || value === undefined || value === "") {
        return "—";
    }
    return String(value);
};

const buildPaginationControls = (page, pageSize, totalCount) => {
    const pageCount = Math.ceil(totalCount / pageSize);
    const previousDisabled = page <= 1 ? "disabled" : "";
    const nextDisabled = page >= pageCount ? "disabled" : "";

    return `
        <div class="insights-drilldown-pagination">
            <div class="insights-drilldown-page-size-pill">${pageSize} rows per page</div>
            <div class="insights-drilldown-pagination-controls">
                <span class="insights-drilldown-pagination-info">
                    ${totalCount ? `Showing page ${page} of ${pageCount}` : "No matching students"}
                </span>
                <button class="insights-drilldown-pagination-button" type="button" data-drilldown-page="${page - 1}" ${previousDisabled}>Prev</button>
                <button class="insights-drilldown-pagination-button" type="button" data-drilldown-page="${page + 1}" ${nextDisabled}>Next</button>
            </div>
        </div>
    `.trim();
};

const buildHierarchicalListHtml = (items, type, onNavigate) => {
    if (!items.length) {
        return `
            <div class="insights-drilldown-state">
                <p class="insights-drilldown-state-title">No ${type} found</p>
                <p class="insights-drilldown-state-copy">No ${type} are available for the current selection.</p>
            </div>
        `.trim();
    }

    const itemsHtml = items.map((item, index) => {
        const countLabel = type === "departments" ? `${item.count} students, ${item.programme_count || 0} programmes` : `${item.count} students`;
        return `
            <div class="insights-drilldown-hierarchical-item">
                <div class="insights-drilldown-item-content">
                    <h3 class="insights-drilldown-item-title">${escapeTooltipHtml(item.label)}</h3>
                    <p class="insights-drilldown-item-meta">${countLabel}</p>
                </div>
                <button class="insights-drilldown-navigate-button" type="button" data-index="${index}">
                    View ${type === "departments" ? "Programmes" : "Students"} →
                </button>
            </div>
        `.trim();
    }).join("");

    return `
        <div class="insights-drilldown-hierarchical-list">
            ${itemsHtml}
        </div>
    `.trim();
};

const buildTableHtml = (columns, rows, totalCount) => {
    if (!columns.length) {
        return `
            <div class="insights-drilldown-state">
                <p class="insights-drilldown-state-title">No drill-down columns are available for this selection.</p>
            </div>
        `.trim();
    }

    const headerHtml = columns.map((column) => 
        `<th scope="col">${escapeTooltipHtml(column.label)}</th>`
    ).join("");

    const sortedRows = rows.length 
        ? [...rows].sort((a, b) => {
            const getLastName = (row) => {
                const fullName = String(row?.[columns[0]?.key] || "").trim();
                const parts = fullName.split(/\s+/);
                return parts[parts.length - 1].toLowerCase();
            };

            return getLastName(a).localeCompare(getLastName(b));
        })
        : [];

    const bodyHtml = sortedRows.length
        ? sortedRows.map((row) => {
            const detailUrl = row.detail_url;
            const cells = columns.map((column, columnIndex) => {
                const cellValue = getDisplayValue(row[column.key]);
                
                if (columnIndex === 0 && detailUrl) {
                    return `
                        <td>
                            <a class="insights-drilldown-link" href="${escapeTooltipHtml(detailUrl)}">${cellValue}</a>
                        </td>
                    `.trim();
                }
                
                return `<td>${escapeTooltipHtml(cellValue)}</td>`;
            }).join("");
            
            return `<tr>${cells}</tr>`;
        }).join("")
        : `
            <tr>
                <td class="insights-drilldown-empty" colspan="${columns.length}">No students matched this selection.</td>
            </tr>
        `.trim();

    return `
        <div class="insights-drilldown-table-wrap">
            <table class="insights-drilldown-table">
                <thead>
                    <tr>${headerHtml}</tr>
                </thead>
                <tbody>
                    ${bodyHtml}
                </tbody>
            </table>
        </div>
    `.trim();
};

const handleEscapeKey = (event) => {
    if (event.key === "Escape") {
        closeInsightsDrillDownModal();
    }
};

export const isInsightsDrillDownModalOpen = () => Boolean(document.getElementById(DRILLDOWN_MODAL_ID));

export const closeInsightsDrillDownModal = () => {
    const modal = document.getElementById(DRILLDOWN_MODAL_ID);
    if (modal) {
        modal.remove();
    }

    document.body.classList.remove("has-insights-drilldown-modal");
    document.removeEventListener("keydown", handleEscapeKey);

    if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
        lastFocusedElement.focus();
    }
};

const renderModal = ({ title, subtitle = "", bodyHtml, toneClass = "", onPageChange = null, onNavigate = null, payload = null }) => {
    closeInsightsDrillDownModal();

    lastFocusedElement = document.activeElement;

    const modal = document.createElement("div");
    modal.id = DRILLDOWN_MODAL_ID;
    modal.className = "insights-drilldown-modal";
    modal.innerHTML = `
        <div class="insights-drilldown-dialog ${toneClass}" role="dialog" aria-modal="true" aria-labelledby="insights-drilldown-title" aria-describedby="insights-drilldown-subtitle" tabindex="-1">
            <div class="insights-drilldown-header">
                <div class="insights-drilldown-heading">
                    <h2 class="insights-drilldown-title" id="insights-drilldown-title">${escapeTooltipHtml(title)}</h2>
                    <p class="insights-drilldown-subtitle" id="insights-drilldown-subtitle">${escapeTooltipHtml(subtitle)}</p>
                </div>
                <button class="insights-drilldown-close" type="button" data-drilldown-close aria-label="Close insights drill-down">Close</button>
            </div>
            <div class="insights-drilldown-body">
                ${bodyHtml}
            </div>
        </div>
    `;

    modal.addEventListener("click", (event) => {
        if (event.target === modal) {
            closeInsightsDrillDownModal();
        }
    });

    const closeButton = modal.querySelector("[data-drilldown-close]");
    if (closeButton) {
        closeButton.addEventListener("click", () => {
            closeInsightsDrillDownModal();
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

    // Set up navigation buttons for hierarchical drilldown
    const navigateButtons = modal.querySelectorAll(".insights-drilldown-navigate-button");
    if (typeof onNavigate === "function" && navigateButtons.length) {
        navigateButtons.forEach((button, index) => {
            button.addEventListener("click", () => {
                const dataIndex = Number(button.dataset.index);
                const items = payload.data || [];
                const item = items[dataIndex];
                if (item) {
                    const type = payload.type;
                    onNavigate(item, type);
                }
            });
        });
    }
    
    document.body.appendChild(modal);
    document.body.classList.add("has-insights-drilldown-modal");
    document.addEventListener("keydown", handleEscapeKey);

    const dialog = modal.querySelector(".insights-drilldown-dialog");
    if (dialog instanceof HTMLElement) {
        dialog.focus();
    }
};

export const showInsightsDrillDownLoadingModal = (title, subtitle = "") => {
    renderModal({
        title,
        subtitle,
        toneClass: "is-loading",
        bodyHtml: `
            <div class="insights-drilldown-state">
                <div class="insights-drilldown-spinner"></div>
                <p class="insights-drilldown-state-title">Loading student data...</p>
                <p class="insights-drilldown-state-copy">Please wait while we gather the requested information.</p>
            </div>
        `.trim(),
    });
};

export const showInsightsDrillDownErrorModal = (title, subtitle = "") => {
    renderModal({
        title,
        subtitle,
        toneClass: "is-error",
        bodyHtml: `
            <div class="insights-drilldown-state">
                <p class="insights-drilldown-state-title">Unable to load drill-down data</p>
                <p class="insights-drilldown-state-copy">${escapeTooltipHtml(subtitle)}</p>
            </div>
        `.trim(),
    });
};

export const showInsightsDrillDownModal = (payload, { onPageChange = null, onNavigate = null } = {}) => {
    const { title, subtitle, type, data, columns, rows, page = 1, page_size = 10, total_count = 0 } = payload || {};
    
        
    if (!title) {
        showInsightsDrillDownErrorModal("Drill-Down Error", "The drill-down data could not be processed.");
        return;
    }

    let bodyHtml = "";
    
    if (type === "departments" || type === "programmes") {
        // Show hierarchical list
        bodyHtml = buildHierarchicalListHtml(data || [], type, onNavigate);
    } else {
        // Show student table
        const tableHtml = buildTableHtml(columns || [], rows || [], total_count || 0);
        const paginationHtml = buildPaginationControls(page, page_size, total_count);
        bodyHtml = `${tableHtml}${paginationHtml}`;
    }

    renderModal({
        title,
        subtitle: subtitle || "",
        bodyHtml,
        onPageChange,
        onNavigate,
        payload,
    });
};
