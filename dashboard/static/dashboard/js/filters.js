/**
 * Filter persistence functionality for dashboard
 * Saves filter selections to localStorage and restores them on page load
 */

const FILTER_STORAGE_KEY = 'dashboard_filters';

/**
 * Save filter selections to localStorage
 */
const saveFilters = () => {
    const filters = {};
    const filterSelects = document.querySelectorAll('.filter-select');
    
    filterSelects.forEach(select => {
        if (select.value) {
            filters[select.name] = select.value;
        }
    });
    
    localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(filters));
};

/**
 * Restore filter selections from localStorage
 */
const restoreFilters = () => {
    try {
        const savedFilters = localStorage.getItem(FILTER_STORAGE_KEY);
        if (!savedFilters) return;
        
        const filters = JSON.parse(savedFilters);
        const filterSelects = document.querySelectorAll('.filter-select');
        
        filterSelects.forEach(select => {
            if (filters[select.name]) {
                select.value = filters[select.name];
            }
        });
    } catch (error) {
        console.error('Error restoring filters:', error);
    }
};

/**
 * Initialize filter persistence
 */
const initializeFilterPersistence = () => {
    // Restore filters on page load
    restoreFilters();
    
    // Add change event listeners to all filter selects
    const filterSelects = document.querySelectorAll('.filter-select');
    filterSelects.forEach(select => {
        select.addEventListener('change', () => {
            saveFilters();
            // Submit form after filter change
            const form = select.closest('form');
            if (form) {
                form.submit();
            }
        });
    });
};

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeFilterPersistence);
} else {
    initializeFilterPersistence();
}
