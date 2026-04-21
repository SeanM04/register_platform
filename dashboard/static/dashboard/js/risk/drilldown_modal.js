import { escapeTooltipHtml } from "./shared.js?v=20260414-risk-drilldown01";

const DRILLDOWN_MODAL_ID = "risk-drilldown-modal";
let lastFocusedElement = null;

const getDisplayValue = (value) => {
    if (value === 0) {
        return "0";
    }

    const text = String(value ?? "").trim();
    return text || "--";
};

const buildPaginationHtml = (payload = {}) => {
    const page = Number(payload.page) || 1;
    const totalCount = Number(payload.total_count) || 0;
    const pageCount = Number(payload.page_count) || 1;
    const pageSize = Number(payload.page_size) || 10;
    const previousDisabled = page <= 1 ? "disabled" : "";
    const nextDisabled = page >= pageCount ? "disabled" : "";

    return `
        <div class="risk-drilldown-pagination">
            <div class="risk-drilldown-page-size-pill">${pageSize} rows per page</div>
            <div class="risk-drilldown-pagination-controls">
                <span class="risk-drilldown-pagination-info">
                    ${totalCount ? `Showing page ${page} of ${pageCount}` : "No matching students"}
                </span>
                <button class="risk-drilldown-pagination-button" type="button" data-drilldown-page="${page - 1}" ${previousDisabled}>Prev</button>
                <button class="risk-drilldown-pagination-button" type="button" data-drilldown-page="${page + 1}" ${nextDisabled}>Next</button>
            </div>
        </div>
    `.trim();
};

const buildTableBodyHtml = (payload = {}) => {
    const columns = Array.isArray(payload.columns) ? payload.columns : [];
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    if (!columns.length) {
        return `
            <div class="risk-drilldown-state">
                <p class="risk-drilldown-state-title">No drill-down columns are available for this selection.</p>
            </div>
        `.trim();
    }

    const headerHtml = columns.map((column) => (
        `<th scope="col">${escapeTooltipHtml(column?.label || column?.key || "Column")}</th>`
    )).join("");

    const rowsHtml = rows.length
        ? rows.map((row) => {
            const cellsHtml = columns.map((column, columnIndex) => {
                const cellValue = escapeTooltipHtml(getDisplayValue(row?.[column.key]));
                const detailUrl = String(row?.detail_url || "").trim();
                if (columnIndex === 0 && detailUrl) {
                    return `
                        <td>
                            <a class="risk-drilldown-link" href="${escapeTooltipHtml(detailUrl)}">${cellValue}</a>
                        </td>
                    `.trim();
                }

                return `<td>${cellValue}</td>`;
            }).join("");

            return `<tr>${cellsHtml}</tr>`;
        }).join("")
        : `
            <tr>
                <td class="risk-drilldown-empty" colspan="${columns.length}">No students matched this selection.</td>
            </tr>
        `.trim();

    return `
        <div class="risk-drilldown-table-wrap">
            <table class="risk-drilldown-table">
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
};

const handleEscapeKey = (event) => {
    if (event.key === "Escape") {
        closeRiskDrillDownModal();
    }
};

export const isRiskDrillDownModalOpen = () => Boolean(document.getElementById(DRILLDOWN_MODAL_ID));

export const closeRiskDrillDownModal = () => {
    const modal = document.getElementById(DRILLDOWN_MODAL_ID);
    if (modal) {
        modal.remove();
    }

    document.body.classList.remove("has-risk-drilldown-modal");
    document.removeEventListener("keydown", handleEscapeKey);

    if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
        lastFocusedElement.focus();
    }
    lastFocusedElement = null;
};

const renderModal = ({ title, subtitle = "", bodyHtml, toneClass = "", onPageChange = null }) => {
    closeRiskDrillDownModal();

    lastFocusedElement = document.activeElement;

    const modal = document.createElement("div");
    modal.id = DRILLDOWN_MODAL_ID;
    modal.className = "risk-drilldown-modal";
    modal.innerHTML = `
        <div class="risk-drilldown-dialog ${toneClass}" role="dialog" aria-modal="true" aria-labelledby="risk-drilldown-title" aria-describedby="risk-drilldown-subtitle" tabindex="-1">
            <div class="risk-drilldown-header">
                <div class="risk-drilldown-heading">
                    <h2 class="risk-drilldown-title" id="risk-drilldown-title">${escapeTooltipHtml(title)}</h2>
                    <p class="risk-drilldown-subtitle" id="risk-drilldown-subtitle">${escapeTooltipHtml(subtitle)}</p>
                </div>
                <button class="risk-drilldown-close" type="button" data-drilldown-close aria-label="Close risk drill-down">Close</button>
            </div>
            <div class="risk-drilldown-body">
                ${bodyHtml}
            </div>
        </div>
    `.trim();

    modal.addEventListener("click", (event) => {
        if (event.target === modal) {
            closeRiskDrillDownModal();
        }
    });

    const closeButton = modal.querySelector("[data-drilldown-close]");
    if (closeButton) {
        closeButton.addEventListener("click", () => {
            closeRiskDrillDownModal();
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

    document.body.appendChild(modal);
    document.body.classList.add("has-risk-drilldown-modal");
    document.addEventListener("keydown", handleEscapeKey);

    const dialog = modal.querySelector(".risk-drilldown-dialog");
    if (dialog instanceof HTMLElement) {
        dialog.focus();
    }
};

export const showRiskDrillDownLoadingModal = (title, subtitle = "") => {
    renderModal({
        title,
        subtitle,
        toneClass: "is-loading",
        bodyHtml: `
            <div class="risk-drilldown-state">
                <p class="risk-drilldown-state-title">Loading matching students...</p>
                <p class="risk-drilldown-state-copy">This drill-down is collecting the current student slice for you.</p>
            </div>
        `.trim(),
    });
};

export const showRiskDrillDownErrorModal = (title, subtitle = "") => {
    renderModal({
        title,
        subtitle,
        toneClass: "is-error",
        bodyHtml: `
            <div class="risk-drilldown-state">
                <p class="risk-drilldown-state-title">The student drill-down could not be loaded.</p>
                <p class="risk-drilldown-state-copy">Refresh the risk page and try the same chart selection again.</p>
            </div>
        `.trim(),
    });
};

export const showRiskDrillDownModal = (payload, options = {}) => {
    renderModal({
        title: payload?.title || "Risk Drill-Down",
        subtitle: payload?.subtitle || "",
        bodyHtml: buildTableBodyHtml(payload),
        onPageChange: options.onPageChange,
    });
};
