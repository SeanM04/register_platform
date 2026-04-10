document.addEventListener('DOMContentLoaded', function() {
    // Get all filter elements
    const yearFilter = document.getElementById('year-filter');
    const periodFilter = document.getElementById('period-filter');
    const facultyFilter = document.getElementById('faculty-filter');
    const yearTabs = document.querySelectorAll('.year-tab');
    const gradeValue = document.querySelector('.grade-value');
    const tableWrap = document.querySelector('.table-wrap');
    
    // Function to update URL with current filter values
    function updateUrl(tabId = null) {
        const urlParams = new URLSearchParams(window.location.search);
        
        // Update filter parameters
        if (yearFilter && yearFilter.value) {
            urlParams.set('year', yearFilter.value);
        }
        if (periodFilter && periodFilter.value) {
            urlParams.set('period', periodFilter.value);
        }
        if (facultyFilter && facultyFilter.value) {
            urlParams.set('faculty', facultyFilter.value);
        }
        
        // Update tab parameter if provided
        if (tabId) {
            urlParams.set('term', tabId);
        }
        
        // Show loading states
        showLoadingStates();
        
        // Navigate to new URL
        const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
        window.location.href = newUrl;
    }
    
    // Function to show loading states
    function showLoadingStates() {
        // Add loading class to table
        if (tableWrap) {
            tableWrap.classList.add('loading');
        }
        
        // Add updating class to grade
        if (gradeValue) {
            gradeValue.classList.add('updating');
        }
        
        // Add syncing class to active tab
        const activeTab = document.querySelector('.year-tab.is-active');
        if (activeTab) {
            activeTab.classList.add('is-syncing');
        }
    }
    
    // Function to hide loading states
    function hideLoadingStates() {
        // Remove loading class from table
        if (tableWrap) {
            tableWrap.classList.remove('loading');
        }
        
        // Remove updating class from grade
        if (gradeValue) {
            gradeValue.classList.remove('updating');
        }
        
        // Remove syncing class from tabs
        yearTabs.forEach(tab => {
            tab.classList.remove('is-syncing');
        });
    }
    
    // Function to handle tab clicks
    function handleTabClick(event) {
        event.preventDefault();
        const tab = event.currentTarget;
        const tabId = tab.getAttribute('href').split('term=')[1]?.split('&')[0];
        
        if (tabId) {
            updateUrl(tabId);
        }
    }
    
    // Function to handle filter changes
    function handleFilterChange() {
        updateUrl();
    }
    
    // Add event listeners to tabs
    yearTabs.forEach(tab => {
        tab.addEventListener('click', handleTabClick);
    });
    
    // Add event listeners to filters
    if (yearFilter) {
        yearFilter.addEventListener('change', handleFilterChange);
    }
    
    if (periodFilter) {
        periodFilter.addEventListener('change', handleFilterChange);
    }
    
    if (facultyFilter) {
        facultyFilter.addEventListener('change', handleFilterChange);
    }
    
    // Auto-refresh functionality (disabled for cumulative grade accuracy)
    function setupAutoRefresh() {
        // Auto-refresh disabled to ensure cumulative grade accuracy
        // Users will manually refresh by changing filters/tabs
    }
    
    // Initialize auto-refresh
    setupAutoRefresh();
    
    // Hide loading states when page loads
    window.addEventListener('load', hideLoadingStates);
    
    // Add keyboard navigation for tabs
    function setupKeyboardNavigation() {
        yearTabs.forEach((tab, index) => {
            tab.addEventListener('keydown', (event) => {
                if (event.key === 'ArrowLeft' && index > 0) {
                    event.preventDefault();
                    yearTabs[index - 1].click();
                } else if (event.key === 'ArrowRight' && index < yearTabs.length - 1) {
                    event.preventDefault();
                    yearTabs[index + 1].click();
                } else if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    tab.click();
                }
            });
            
            // Add ARIA attributes for accessibility
            tab.setAttribute('role', 'tab');
            tab.setAttribute('tabindex', tab.classList.contains('is-active') ? '0' : '-1');
        });
    }
    
    // Initialize keyboard navigation
    setupKeyboardNavigation();
    
    // Add cumulative grade animation
    function animateGradeChange() {
        if (gradeValue) {
            gradeValue.style.transform = 'scale(1.1)';
            setTimeout(() => {
                gradeValue.style.transform = 'scale(1)';
            }, 300);
        }
    }
    
    // Monitor grade changes and animate
    if (gradeValue) {
        const observer = new MutationObserver(() => {
            animateGradeChange();
        });
        observer.observe(gradeValue, { childList: true, characterData: true });
    }
});
