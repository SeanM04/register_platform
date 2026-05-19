document.addEventListener('DOMContentLoaded', function() {
    // Get all filter elements
    const yearFilter = document.getElementById('filter-year');
    const periodFilter = document.getElementById('filter-period');
    const facultyFilter = document.getElementById('filter-faculty');
    const yearTabs = document.querySelectorAll('.year-tab');
    const gradeValue = document.querySelector('.grade-value');
    const tableWrap = document.querySelector('.table-wrap');
    
    // Initialize dropdown tabs functionality
    function initializeDropdownTabs() {
        const dropdowns = document.querySelectorAll('.year-dropdown');
        
        dropdowns.forEach((dropdown, index) => {
            const toggle = dropdown.querySelector('.year-dropdown-toggle');
            const content = dropdown.querySelector('.year-dropdown-content');
            
            if (toggle && content) {
                // Set initial state - always start closed
                toggle.setAttribute('aria-expanded', 'false');
                content.classList.remove('show');
                
                // Handle semester selection
                const semesterOptions = content.querySelectorAll('.year-dropdown-option');
                semesterOptions.forEach(option => {
                    option.addEventListener('click', function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        
                        // Store the href for navigation after closing
                        const targetUrl = option.href;
                        
                        // Update year tab label with year and semester
                        const semesterInfo = option.querySelector('.year-dropdown-option-label').textContent;
                        const yearLabel = dropdown.querySelector('.year-dropdown-label').textContent;
                        
                        // Extract just the "Year X" part from current label
                        const yearOnly = yearLabel.match(/Year \d+/)[0];
                        
                        // Extract semester number from "Semester 1 - March - July"
                        const semesterNumber = semesterInfo.match(/Semester \d+/)[0];
                        
                        // Create new label: "Year 1 Semester 2"
                        const newLabel = `${yearOnly} ${semesterNumber}`;
                        
                        dropdown.querySelector('.year-dropdown-label').textContent = newLabel;
                        
                        // Immediately close and hide dropdown
                        toggle.setAttribute('aria-expanded', 'false');
                        content.classList.remove('show');
                        
                        // Mark as selected
                        dropdown.classList.add('semester-selected');
                        
                        // Navigate to the semester URL after a brief delay to ensure dropdown closes
                        setTimeout(() => {
                            window.location.href = targetUrl;
                        }, 100);
                    });
                });
                
                // Toggle dropdown
                toggle.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
                    
                    // Close all other dropdowns
                    dropdowns.forEach(otherDropdown => {
                        if (otherDropdown !== dropdown) {
                            const otherToggle = otherDropdown.querySelector('.year-dropdown-toggle');
                            const otherContent = otherDropdown.querySelector('.year-dropdown-content');
                            otherToggle.setAttribute('aria-expanded', 'false');
                            otherContent.classList.remove('show');
                        }
                    });
                    
                    // Toggle current dropdown
                    toggle.setAttribute('aria-expanded', !isExpanded);
                    if (!isExpanded) {
                        content.classList.add('show');
                    } else {
                        content.classList.remove('show');
                    }
                });
                
                // Close dropdown when clicking outside
                document.addEventListener('click', function(e) {
                    if (!dropdown.contains(e.target)) {
                        toggle.setAttribute('aria-expanded', 'false');
                        content.classList.remove('show');
                    }
                });
                
                // Handle keyboard navigation
                toggle.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        toggle.click();
                    } else if (e.key === 'Escape') {
                        toggle.setAttribute('aria-expanded', 'false');
                        content.classList.remove('show');
                        toggle.focus();
                    }
                });
            }
        });
    }
    
    // Call the initialization function
    initializeDropdownTabs();
    
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
    
    // Add event listeners to tabs
    yearTabs.forEach(tab => {
        tab.addEventListener('click', handleTabClick);
    });
    
    // Note: Filter event listeners are now handled by the global filter system (filters.js)
    // Custom filter handlers removed to prevent conflicts with global implementation
    
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
