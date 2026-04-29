import { escapeTooltipHtml } from "../insights/shared.js";

const GRADUATION_DRILLDOWN_MODAL_ID = "home-drilldown-modal";
let lastFocusedElement = null;

const getDisplayValue = (value) => {
    if (value === null || value === undefined) return "";
    return String(value);
};

const buildPaginationHtml = (payload = {}) => {
    const { page = 1, page_size = 10, total_items = 0 } = payload.pagination || {};
    const pageCount = Math.ceil(total_items / page_size);
    const previousDisabled = page <= 1 ? "disabled" : "";
    const nextDisabled = page >= pageCount ? "disabled" : "";

    return `
        <div class="home-drilldown-pagination">
            <div class="home-drilldown-page-size-pill">${page_size} rows per page</div>
            <div class="home-drilldown-pagination-controls">
                <span class="home-drilldown-pagination-info">
                    ${total_items ? `Showing page ${page} of ${pageCount}` : "No matching students"}
                </span>
                <button class="home-drilldown-pagination-button" type="button" data-drilldown-page="${page - 1}" ${previousDisabled}>Prev</button>
                <button class="home-drilldown-pagination-button" type="button" data-drilldown-page="${page + 1}" ${nextDisabled}>Next</button>
            </div>
        </div>
    `.trim();
};

const buildTableBodyHtml = (payload = {}) => {
    const columns = Array.isArray(payload.columns) ? payload.columns : [];
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    
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

    return `
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
};

const handleEscapeKey = (event) => {
    if (event.key === "Escape") {
        closeGraduationDrillDownModal();
    }
};

export const isGraduationDrillDownModalOpen = () => Boolean(document.getElementById(GRADUATION_DRILLDOWN_MODAL_ID));

export const closeGraduationDrillDownModal = () => {
    const modal = document.getElementById(GRADUATION_DRILLDOWN_MODAL_ID);
    if (modal) {
        modal.remove();
    }

    document.body.classList.remove("has-home-drilldown-modal");
    document.removeEventListener("keydown", handleEscapeKey);

    if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
        lastFocusedElement.focus();
    }
};

const renderModal = ({ title, subtitle = "", bodyHtml, toneClass = "", onPageChange = null }) => {
    closeGraduationDrillDownModal();

    lastFocusedElement = document.activeElement;

    const modal = document.createElement("div");
    modal.id = GRADUATION_DRILLDOWN_MODAL_ID;
    modal.className = "home-drilldown-modal";
    modal.innerHTML = `
        <div class="home-drilldown-dialog ${toneClass}" role="dialog" aria-modal="true" aria-labelledby="home-drilldown-title" aria-describedby="home-drilldown-subtitle" tabindex="-1">
            <div class="home-drilldown-header">
                <div class="home-drilldown-heading">
                    <h2 class="home-drilldown-title" id="home-drilldown-title">${escapeTooltipHtml(title)}</h2>
                    <p class="home-drilldown-subtitle" id="home-drilldown-subtitle">${escapeTooltipHtml(subtitle)}</p>
                </div>
                <button class="home-drilldown-close" type="button" data-drilldown-close aria-label="Close drill-down">Close</button>
            </div>
            <div class="home-drilldown-body">
                ${bodyHtml}
            </div>
        </div>
    `.trim();

    modal.addEventListener("click", (event) => {
        if (event.target === modal) {
            closeGraduationDrillDownModal();
        }
    });

    const closeButton = modal.querySelector("[data-drilldown-close]");
    if (closeButton) {
        closeButton.addEventListener("click", () => {
            closeGraduationDrillDownModal();
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
    document.body.classList.add("has-home-drilldown-modal");
    document.addEventListener("keydown", handleEscapeKey);

    const dialog = modal.querySelector(".home-drilldown-dialog");
    if (dialog instanceof HTMLElement) {
        dialog.focus();
    }
};

export const showGraduationDrillDownModal = (payload, onPageChange = null) => {
    const { title = "Drill-down Results", subtitle = "", type = "table" } = payload;

    let bodyHtml = "";
    if (type === "table") {
        bodyHtml = buildTableBodyHtml(payload);
    } else {
        bodyHtml = `
            <div class="home-drilldown-state">
                <p class="home-drilldown-state-title">Unsupported drill-down type: ${type}</p>
            </div>
        `.trim();
    }

    renderModal({
        title,
        subtitle,
        bodyHtml,
        toneClass: "",
        onPageChange,
    });
};
