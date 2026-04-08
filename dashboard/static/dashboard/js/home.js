import { initialiseOverviewPage } from "./home/index.js?v=20260403-home-story04";

// Initialize collapsible sections
function initializeCollapsibleSections() {
    const toggles = document.querySelectorAll('.home-flow-toggle');
    
    toggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const contentId = this.getAttribute('aria-controls');
            const content = document.getElementById(contentId);
            const icon = this.querySelector('.home-flow-toggle-icon');
            const isExpanded = this.getAttribute('aria-expanded') === 'true';
            
            if (content && icon) {
                if (isExpanded) {
                    // Collapse
                    content.classList.add('collapsed');
                    icon.textContent = '+';
                    this.setAttribute('aria-expanded', 'false');
                } else {
                    // Expand
                    content.classList.remove('collapsed');
                    icon.textContent = '−';
                    this.setAttribute('aria-expanded', 'true');
                }
            }
        });
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initializeCollapsibleSections);

initialiseOverviewPage();
