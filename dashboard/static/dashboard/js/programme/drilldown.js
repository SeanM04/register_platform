/* Programme Drill-down Module */

const DEFAULT_DRILLDOWN_PAGE_SIZE = 10;
let activeProgrammeDrillDownToken = 0;

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

const removeExistingProgrammeDrillDownModal = () => {
    document.querySelectorAll('.risk-drilldown-modal').forEach((modal) => {
        modal.remove();
    });
    document.body.classList.remove('has-risk-drilldown-modal');
};

export const cancelProgrammeDrillDownRequests = () => {
    activeProgrammeDrillDownToken += 1;
};

const buildRequestUrl = (endpoint, params = {}) => {
    const requestUrl = new URL(endpoint, window.location.origin);
    const currentUrl = new URL(window.location.href);

    currentUrl.searchParams.forEach((value, key) => {
        requestUrl.searchParams.set(key, value);
    });

    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && String(value).trim()) {
            requestUrl.searchParams.set(key, String(value).trim());
        }
    });

    return requestUrl;
};

const fetchDrillDownPayload = async (endpoint, params = {}) => {
    const response = await fetch(buildRequestUrl(endpoint, params), {
        method: "GET",
        headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
    });

    if (!response.ok) {
        throw new Error(`Drill-down request failed: ${response.status}`);
    }

    return response.json();
};

const showProgrammeDrillDownModal = (payload, onPageChange = null) => {
    removeExistingProgrammeDrillDownModal();

    // Create modal using system styling
    const modal = document.createElement('div');
    modal.className = 'risk-drilldown-modal';
    
    const dialog = document.createElement('div');
    dialog.className = 'risk-drilldown-dialog';
    
    const header = document.createElement('div');
    header.className = 'risk-drilldown-header';
    
    const heading = document.createElement('div');
    heading.className = 'risk-drilldown-heading';
    
    const title = document.createElement('h2');
    title.className = 'risk-drilldown-title';
    title.textContent = payload.title || 'Drill-down Results';
    title.style.cssText = `
        margin: 0;
        font-size: 1.25rem;
        font-weight: 700;
        color: #0d2f54;
    `;
    
    const subtitle = document.createElement('p');
    subtitle.className = 'risk-drilldown-subtitle';
    subtitle.textContent = payload.subtitle || '';
    subtitle.style.cssText = `
        margin: 0.22rem 0 0;
        font-size: 0.9rem;
        color: #64748b;
        line-height: 1.4;
    `;
    
    const closeButton = document.createElement('button');
    closeButton.className = 'risk-drilldown-close';
    closeButton.textContent = 'Close';
    closeButton.style.cssText = `
        background: none;
        border: none;
        font-size: 0.9rem;
        color: #64748b;
        cursor: pointer;
        padding: 0;
        font-weight: 600;
    `;

    closeButton.onclick = (event) => {
        event.preventDefault();
        event.stopPropagation();
        modal.remove();
        document.body.classList.remove('has-risk-drilldown-modal');
    };

    closeButton.onmouseover = () => {
        closeButton.style.color = '#1e293b';
    };

    closeButton.onmouseout = () => {
        closeButton.style.color = '#64748b';
    };
    
    // Create table with system styling
    const tableWrap = document.createElement('div');
    tableWrap.className = 'risk-drilldown-table-wrap';
    
    const table = document.createElement('table');
    table.className = 'risk-drilldown-table';
    
    // Create table header
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    if (payload.columns && payload.columns.length > 0) {
        payload.columns.forEach(column => {
            const th = document.createElement('th');
            th.textContent = column.label;
            headerRow.appendChild(th);
        });
    }
    thead.appendChild(headerRow);
    table.appendChild(thead);
    
    // Create table body
    const tbody = document.createElement('tbody');
    if (payload.rows && payload.rows.length > 0) {
        // Sort rows by last name
        const sortedRows = [...payload.rows].sort((a, b) => {
            const aName = getStudentNameSortKey(a?.name || "");
            const bName = getStudentNameSortKey(b?.name || "");
            return (
                aName.surname.localeCompare(bName.surname)
                || aName.givenNames.localeCompare(bName.givenNames)
                || String(a?.registration_number || a?.regnum || a?.detail_slug || "").localeCompare(
                    String(b?.registration_number || b?.regnum || b?.detail_slug || "")
                )
            );
        });
        
        sortedRows.forEach(row => {
            const tr = document.createElement('tr');
            payload.columns.forEach(column => {
                const td = document.createElement('td');
                const value = row[column.key] || '';
                
                // Add link for student name if it's the first column
                if (column.key === 'name' && row.detail_url) {
                    const link = document.createElement('a');
                    link.href = row.detail_url;
                    link.className = 'risk-drilldown-link';
                    link.textContent = value;
                    td.appendChild(link);
                } else {
                    td.textContent = value;
                }
                
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    } else {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.textContent = 'No data available';
        td.style.cssText = `
            text-align: center;
            font-style: italic;
            color: #64748b;
            padding: 2rem;
        `;
        td.colSpan = payload.columns ? payload.columns.length : 1;
        tr.appendChild(td);
        tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    
    // Create pagination controls if available
    let paginationControls = '';
    if (payload.pagination && onPageChange) {
        const { current_page, page_size, total_items, total_pages, has_next, has_previous } = payload.pagination;
        
        paginationControls = document.createElement('div');
        paginationControls.className = 'risk-drilldown-pagination';
        paginationControls.style.cssText = `
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem;
            border-top: 1px solid #e2e8f0;
            font-size: 0.9rem;
            color: #64748b;
        `;
        
        // Page info
        const pageInfo = document.createElement('div');
        pageInfo.textContent = total_items > 0 
            ? `Showing ${page_size * (current_page - 1) + 1}-${Math.min(page_size * current_page, total_items)} of ${total_items} students`
            : 'No students found';
        paginationControls.appendChild(pageInfo);
        
        // Page navigation buttons
        const navButtons = document.createElement('div');
        navButtons.style.cssText = `
            display: flex;
            gap: 0.5rem;
        `;
        
        // Previous button
        const prevButton = document.createElement('button');
        prevButton.textContent = 'Previous';
        prevButton.disabled = !has_previous;
        prevButton.style.cssText = `
            padding: 0.25rem 0.75rem;
            border: 1px solid #d1d5db;
            background: ${has_previous ? '#ffffff' : '#f9fafb'};
            color: ${has_previous ? '#374151' : '#9ca3af'};
            cursor: ${has_previous ? 'pointer' : 'not-allowed'};
            border-radius: 0.375rem;
            font-size: 0.875rem;
        `;
        if (has_previous) {
            prevButton.onclick = () => onPageChange(current_page - 1);
        }
        navButtons.appendChild(prevButton);
        
        // Page indicator
        const pageIndicator = document.createElement('span');
        pageIndicator.textContent = `Page ${current_page} of ${total_pages}`;
        pageIndicator.style.cssText = `
            padding: 0.25rem 0.75rem;
            color: #6b7280;
            font-weight: 500;
        `;
        navButtons.appendChild(pageIndicator);
        
        // Next button
        const nextButton = document.createElement('button');
        nextButton.textContent = 'Next';
        nextButton.disabled = !has_next;
        nextButton.style.cssText = `
            padding: 0.25rem 0.75rem;
            border: 1px solid #d1d5db;
            background: ${has_next ? '#ffffff' : '#f9fafb'};
            color: ${has_next ? '#374151' : '#9ca3af'};
            cursor: ${has_next ? 'pointer' : 'not-allowed'};
            border-radius: 0.375rem;
            font-size: 0.875rem;
        `;
        if (has_next) {
            nextButton.onclick = () => onPageChange(current_page + 1);
        }
        navButtons.appendChild(nextButton);
        
        paginationControls.appendChild(navButtons);
    }
    
    // Assemble modal
    heading.appendChild(title);
    heading.appendChild(subtitle);
    header.appendChild(heading);
    header.appendChild(closeButton);
    tableWrap.appendChild(table);
    dialog.appendChild(header);
    dialog.appendChild(tableWrap);
    
    if (paginationControls) {
        dialog.appendChild(paginationControls);
    }
    
    modal.appendChild(dialog);
    
    // Add to page and prevent body scroll
    document.body.appendChild(modal);
    document.body.classList.add('has-risk-drilldown-modal');
    
    // Close on backdrop click
    modal.onclick = (e) => {
        if (e.target === modal) {
            e.stopPropagation();
            modal.remove();
            document.body.classList.remove('has-risk-drilldown-modal');
        }
    };
};

const showProgrammeDrillDownLoadingModal = (title, subtitle) => {
    // Use renderModal approach for consistency
    const renderModal = ({ title, subtitle = "", bodyHtml, toneClass = "" }) => {
        // Close any existing modal
        hideProgrammeDrillDownLoadingModal();
        
        const modalOverlay = document.createElement("div");
        modalOverlay.id = "programme-drilldown-loading-modal";
        modalOverlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10010;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        `;
        
        const modalDialog = document.createElement("div");
        modalDialog.style.cssText = `
            background: white;
            padding: 30px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            max-width: 400px;
            border: 1px solid rgba(184, 200, 217, 0.9);
        `;
        
        const modalHeader = document.createElement("div");
        modalHeader.style.cssText = `
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 20px;
        `;
        
        const modalTitle = document.createElement("h2");
        modalTitle.textContent = title || "Loading Drilldown Data";
        modalTitle.style.cssText = `
            margin: 0;
            color: #0d2f54;
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.3;
        `;
        
        const modalClose = document.createElement("button");
        modalClose.textContent = "×";
        modalClose.style.cssText = `
            background: none;
            border: none;
            font-size: 1.5rem;
            cursor: pointer;
            color: #666;
            padding: 0;
            width: 24px;
            height: 24px;
        `;
        
        const modalBody = document.createElement("div");
        modalBody.innerHTML = bodyHtml;
        
        modalHeader.appendChild(modalTitle);
        modalHeader.appendChild(modalClose);
        modalDialog.appendChild(modalHeader);
        modalDialog.appendChild(modalBody);
        modalOverlay.appendChild(modalDialog);
        
        document.body.appendChild(modalOverlay);
        
        // Handle close button
        modalClose.addEventListener('click', () => {
            hideProgrammeDrillDownLoadingModal();
        });
        
        // Handle backdrop click
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) {
                hideProgrammeDrillDownLoadingModal();
            }
        });
    };
    
    renderModal({
        title: title || "Loading Drilldown Data",
        subtitle: subtitle,
        toneClass: "is-loading",
        bodyHtml: `
            <div class="programme-drilldown-state">
                <div class="programme-drilldown-spinner"></div>
                <p class="programme-drilldown-state-title">Loading student data...</p>
                <p class="programme-drilldown-state-copy">Please wait while we gather the requested information.</p>
            </div>
        `.trim(),
    });
};

const hideProgrammeDrillDownLoadingModal = () => {
    const loadingModal = document.getElementById("programme-drilldown-loading-modal");
    if (loadingModal) {
        loadingModal.remove();
    }
};

const showProgrammeDrillDownErrorModal = (title, message) => {
    showProgrammeDrillDownModal({
        title,
        subtitle: message,
        columns: [],
        rows: [],
        pagination: {
            current_page: 1,
            page_size: DEFAULT_DRILLDOWN_PAGE_SIZE,
            total_items: 0,
            total_pages: 0,
            has_next: false,
            has_previous: false,
        },
    });
};

export const openProgrammeDrillDown = async (context, { chartKey, bucketKey, label }) => {
    cancelProgrammeDrillDownRequests();

    const endpoint = context?.config?.drilldownUrl;
    const safeLabel = String(label || "Selected").trim() || "Selected";
    const requestToken = activeProgrammeDrillDownToken;
    let currentPageSize = DEFAULT_DRILLDOWN_PAGE_SIZE;

    if (!endpoint || !chartKey || !bucketKey) {
        showProgrammeDrillDownErrorModal(`${safeLabel} Students`, "This chart drill-down is not available right now.");
        return;
    }

    const subtitle = `Loading the students behind ${safeLabel.toLowerCase()}.`;
    showProgrammeDrillDownLoadingModal(`${safeLabel} Students`, subtitle);

    const loadPage = async (page, pageSize = currentPageSize) => {
        currentPageSize = pageSize || DEFAULT_DRILLDOWN_PAGE_SIZE;
        showProgrammeDrillDownLoadingModal(`${safeLabel} Students`, subtitle);

        try {
            const payload = await fetchDrillDownPayload(endpoint, {
                chart: chartKey,
                bucket: bucketKey,
                page,
                page_size: currentPageSize,
            });

            if (requestToken !== activeProgrammeDrillDownToken) {
                return;
            }

            hideProgrammeDrillDownLoadingModal();
            showProgrammeDrillDownModal(payload, loadPage);

        } catch (error) {
            console.error("Programme drill-down error:", error);
            if (requestToken === activeProgrammeDrillDownToken) {
                hideProgrammeDrillDownLoadingModal();
                showProgrammeDrillDownErrorModal(
                    `${safeLabel} Students`,
                    "Could not load the student data. Please try again."
                );
            }
        }
    };

    await loadPage(1);
};
