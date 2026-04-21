export const initialiseAcademicLevelSearch = (elements) => {
    const { levelSearchForm, levelSearchInput } = elements;
    let levelSearchTimer = null;

    if (!levelSearchForm || !levelSearchInput) {
        console.log('[Academic Level Search] Form or input not found, skipping initialization');
        return;
    }

    console.log('[Academic Level Search] Initializing search functionality');

    // Listen for form submission to refresh data with new filters
    levelSearchForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        console.log('[Academic Level Search] Form submitted, refreshing data');
        
        // Get current filter values from the form
        const formData = new FormData(levelSearchForm);
        const searchParams = new URLSearchParams(formData);
        
        // Add existing URL parameters (topbar filters)
        const currentUrl = new URL(window.location.href);
        currentUrl.searchParams.forEach((value, key) => {
            if (!searchParams.has(key)) {
                searchParams.set(key, value);
            }
        });
        
        // Update URL without page reload
        const newUrl = new URL(window.location);
        newUrl.search = searchParams.toString();
        window.history.pushState({}, '', newUrl);
        
        console.log('[Academic Level Search] Updated URL:', newUrl.toString());
        
        // Fetch fresh data with current filters
        await refreshTableDataWithFilters();
    });

    levelSearchInput.addEventListener("input", () => {
        window.clearTimeout(levelSearchTimer);
        levelSearchTimer = window.setTimeout(() => {
            console.log('[Academic Level Search] Input changed, submitting form');
            levelSearchForm.requestSubmit();
        }, 450);
    });

    // Note: Topbar filter event listeners are now handled by the global filter system (filters.js)
    // Custom topbar filter handlers removed to prevent conflicts with global implementation
};

// Function to refresh table data with current filters
const refreshTableDataWithFilters = async () => {
    try {
        // Build request URL with current filters
        const requestUrl = new URL(window.location.pathname, window.location.origin);
        const currentUrl = new URL(window.location.href);
        
        // Copy all search parameters to request
        currentUrl.searchParams.forEach((value, key) => {
            requestUrl.searchParams.set(key, value);
        });
        
        // Fetch fresh data
        const response = await fetch(requestUrl, {
            credentials: "same-origin",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
        });
        
        if (!response.ok) {
            throw new Error(`Request failed with status ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update table with filtered data
        if (data.level_rows && Array.isArray(data.level_rows)) {
            // Update global pagination state
            window.paginationState = window.paginationState || {
                allRows: [],
                currentPage: 1,
                pageSize: 10,
                totalPages: 1,
            };
            
            window.paginationState.allRows = data.level_rows;
            window.paginationState.currentPage = 1;
            window.paginationState.totalPages = Math.ceil(data.level_rows.length / window.paginationState.pageSize);
            
            // Re-render table with filtered data
            renderTableWithFilteredData(data.level_rows);
        }
        
    } catch (error) {
        console.error('Error refreshing table data:', error);
    }
};

// Function to render table with filtered data
const renderTableWithFilteredData = (rows) => {
    const tableBody = document.querySelector('.level-table tbody');
    if (!tableBody) {
        console.error('Table body not found');
        return;
    }
    
    if (!rows || rows.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td class="level-empty" colspan="6">No academic level data matched the current filters.</td>
            </tr>
        `;
        return;
    }
    
    // Get pagination state
    const pagination = window.paginationState || {
        currentPage: 1,
        pageSize: 10,
    };
    
    const startIndex = (pagination.currentPage - 1) * pagination.pageSize;
    const endIndex = startIndex + pagination.pageSize;
    const paginatedRows = rows.slice(startIndex, endIndex);
    
    // Render table rows
    tableBody.innerHTML = paginatedRows.map((row) => `
        <tr data-level-row="${escapeHtml(row.level)}">
            <td class="level-td-key">${escapeHtml(row.level)}</td>
            <td>${escapeHtml(row.students)}</td>
            <td>${escapeHtml(row.registrations)}</td>
            <td>${escapeHtml(row.pass_rate)}</td>
            <td>${escapeHtml(row.average_mark)}</td>
            <td>${escapeHtml(row.top_programme)}</td>
        </tr>
    `).join("").trim();
    
    // Update pagination controls
    updatePaginationControls(rows.length);
};

// Helper function to escape HTML
const escapeHtml = (text) => {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
};

// Function to update pagination controls
const updatePaginationControls = (totalRows) => {
    const pagination = window.paginationState || {
        currentPage: 1,
        pageSize: 10,
    };
    
    const totalPages = Math.ceil(totalRows / pagination.pageSize);
    
    // Update pagination controls if they exist
    const prevButton = document.querySelector('.pagination-prev');
    const nextButton = document.querySelector('.pagination-next');
    const pageInfo = document.querySelector('.pagination-info');
    
    if (prevButton) {
        prevButton.disabled = pagination.currentPage <= 1;
    }
    
    if (nextButton) {
        nextButton.disabled = pagination.currentPage >= totalPages;
    }
    
    if (pageInfo) {
        pageInfo.textContent = `Page ${pagination.currentPage} of ${totalPages}`;
    }
};

// Make pagination functions globally accessible
window.refreshTableDataWithFilters = refreshTableDataWithFilters;
window.renderTableWithFilteredData = renderTableWithFilteredData;
