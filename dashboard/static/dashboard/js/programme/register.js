import { escapeHtml, formatProgrammeName } from "./shared.js?v=20260414-msc-support01";

export const initialiseRegisterInteractions = (form, input) => {
    if (!form || !input) {
        return;
    }

    let searchTimer = null;

    input.addEventListener("input", () => {
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(() => {
            form.requestSubmit();
        }, 450);
    });
};

const renderPaginationControls = (body, registerMeta) => {
    const currentPage = Number(registerMeta.current_page || 1);
    const totalPages = Number(registerMeta.total_pages || 1);
    const hasPrevious = Boolean(registerMeta.has_previous);
    const hasNext = Boolean(registerMeta.has_next);

    if (totalPages <= 1) {
        return; // No pagination needed
    }

    // Create pagination controls row
    const paginationRow = document.createElement("tr");
    paginationRow.innerHTML = `
        <td colspan="8" class="programme-pagination-cell">
            <div class="programme-pagination">
                <div class="programme-pagination-info">
                    Page ${currentPage} of ${totalPages}
                </div>
                <div class="programme-pagination-controls">
                    ${hasPrevious ? `
                        <button class="programme-pagination-link" onclick="loadPage(${currentPage - 1})" aria-label="Previous page">
                            Previous
                        </button>
                    ` : ''}
                    <span class="programme-pagination-current">${currentPage}</span>
                    ${hasNext ? `
                        <button class="programme-pagination-link" onclick="loadPage(${currentPage + 1})" aria-label="Next page">
                            Next
                        </button>
                    ` : ''}
                </div>
            </div>
        </td>
    `;

    // Add pagination row after the table body
    body.appendChild(paginationRow);
};

// Global function to load a specific page
window.loadPage = async (pageNumber) => {
    try {
        // Get the root element and payload URL
        const root = document.querySelector('.programme-dashboard');
        if (!root) return;
        
        const payloadUrl = new URL(root.dataset.payloadUrl, window.location.origin);
        
        // Copy current filter parameters and set new page
        const currentUrl = new URL(window.location.href);
        currentUrl.searchParams.forEach((value, key) => {
            if (key !== 'page') {
                payloadUrl.searchParams.set(key, value);
            }
        });
        payloadUrl.searchParams.set('page', pageNumber);
        
        // Fetch new data
        const response = await fetch(payloadUrl.toString(), {
            credentials: "same-origin",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
        });
        
        if (!response.ok) {
            throw new Error(`Request failed with status ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update the table with new data
        const tableBody = document.getElementById('programme-register-body');
        const metaElement = document.getElementById('programme-register-meta');
        
        if (tableBody && data.programme_rows) {
            // Clear existing pagination controls
            const existingPagination = tableBody.querySelector('.programme-pagination-cell');
            if (existingPagination) {
                existingPagination.parentElement.remove();
            }
            
            // Re-render the register with new data
            renderProgrammeRegister(tableBody, metaElement, data.programme_rows, data.register_meta || {});
            
            // Update URL without page reload
            const newUrl = new URL(window.location.href);
            newUrl.searchParams.set('page', pageNumber);
            window.history.pushState({}, '', newUrl.toString());
        }
        
    } catch (error) {
        console.error('Error loading page:', error);
        // Fallback to page reload if dynamic loading fails
        const currentUrl = new URL(window.location.href);
        currentUrl.searchParams.set('page', pageNumber);
        window.location.href = currentUrl.toString();
    }
};

export const renderProgrammeRegister = (body, metaElement, rows, registerMeta) => {
    if (!body) {
        return;
    }
    if (!rows.length) {
        body.innerHTML = `
            <tr>
                <td class="programme-empty" colspan="8">No programme rows are visible in the current scope.</td>
            </tr>
        `.trim();

        if (metaElement) {
            metaElement.textContent = "No programme rows are visible in the current scope.";
        }
        return;
    }

    // Clear existing content including pagination
    body.innerHTML = '';

    // Add table rows
    rows.forEach((row) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="programme-td-code">${escapeHtml(row.code)}</td>
            <td>${escapeHtml(formatProgrammeName(row.name))}</td>
            <td>${escapeHtml(row.faculty)}</td>
            <td>${escapeHtml(row.department)}</td>
            <td>${escapeHtml(row.students)}</td>
            <td>${escapeHtml(row.registrations)}</td>
            <td>${escapeHtml(row.average_mark)}</td>
            <td class="programme-td-pass">${escapeHtml(row.pass_rate)}</td>
        `;
        body.appendChild(tr);
    });

    // Update meta information with pagination details
    if (metaElement) {
        const visibleCount = Number(registerMeta.visible_count || 0);
        const currentPage = Number(registerMeta.current_page || 1);
        const perPage = Number(registerMeta.per_page || 10);
        const totalPages = Number(registerMeta.total_pages || 1);
        
        const startItem = (currentPage - 1) * perPage + 1;
        const endItem = Math.min(currentPage * perPage, visibleCount);
        
        metaElement.textContent = `Showing ${startItem}-${endItem} of ${visibleCount.toLocaleString()} programmes (Page ${currentPage} of ${totalPages}).`;
    }

    // Render pagination controls
    renderPaginationControls(body, registerMeta);
};
