/* Programme Drill-down Module */

const DEFAULT_DRILLDOWN_PAGE_SIZE = 10;
let activeProgrammeDrillDownToken = 0;

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

const showProgrammeDrillDownModal = (payload) => {
      removeExistingProgrammeDrillDownModal();   // 👈 ADD THIS LINE

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
        payload.rows.forEach(row => {
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
    
    // Assemble modal
    heading.appendChild(title);
    heading.appendChild(subtitle);
    header.appendChild(heading);
    header.appendChild(closeButton);
    tableWrap.appendChild(table);
    dialog.appendChild(header);
    dialog.appendChild(tableWrap);
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
    showProgrammeDrillDownModal({
        title,
        subtitle,
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

            showProgrammeDrillDownModal(payload);

        } catch (error) {
            console.error("Programme drill-down error:", error);
            if (requestToken === activeProgrammeDrillDownToken) {
                showProgrammeDrillDownErrorModal(
                    `${safeLabel} Students`,
                    "Could not load the student data. Please try again."
                );
            }
        }
    };

    await loadPage(1);
};
