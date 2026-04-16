/* eslint-env browser */
/* global document */

export const initialiseAccordion = () => {
    const accordionItems = document.querySelectorAll('.demographic-accordion-item');
    
    accordionItems.forEach((item) => {
        const toggleButton = item.querySelector('.demographic-accordion-toggle');
        const content = item.querySelector('.demographic-accordion-content');
        
        if (!toggleButton || !content) {
            return;
        }
        
        toggleButton.addEventListener('click', () => {
            const isOpen = item.classList.contains('is-open');
            const toggleText = toggleButton.querySelector('.demographic-accordion-toggle-text');
            const toggleIcon = toggleButton.querySelector('.demographic-accordion-toggle-icon');
            
            // Close all other accordion items
            accordionItems.forEach((otherItem) => {
                if (otherItem !== item) {
                    otherItem.classList.remove('is-open');
                    const otherContent = otherItem.querySelector('.demographic-accordion-content');
                    const otherToggle = otherItem.querySelector('.demographic-accordion-toggle');
                    const otherToggleText = otherToggle?.querySelector('.demographic-accordion-toggle-text');
                    const otherToggleIcon = otherToggle?.querySelector('.demographic-accordion-toggle-icon');
                    
                    if (otherContent) {
                        otherContent.classList.add('is-hidden');
                        otherContent.style.maxHeight = '0';
                    }
                    
                    if (otherToggle) {
                        otherToggle.setAttribute('aria-expanded', 'false');
                    }
                    
                    if (otherToggleText) {
                        otherToggleText.textContent = 'Expand';
                    }
                    
                    if (otherToggleIcon) {
                        otherToggleIcon.textContent = '+';
                    }
                }
            });
            
            // Toggle current item
            if (isOpen) {
                item.classList.remove('is-open');
                content.classList.add('is-hidden');
                content.style.maxHeight = '0';
                toggleButton.setAttribute('aria-expanded', 'false');
                if (toggleText) {
                    toggleText.textContent = 'Expand';
                }
                if (toggleIcon) {
                    toggleIcon.textContent = '+';
                }
            } else {
                item.classList.add('is-open');
                content.classList.remove('is-hidden');
                content.style.maxHeight = content.scrollHeight + 'px';
                toggleButton.setAttribute('aria-expanded', 'true');
                if (toggleText) {
                    toggleText.textContent = 'Collapse';
                }
                if (toggleIcon) {
                    toggleIcon.textContent = '−';
                }
            }
        });
    });
};
