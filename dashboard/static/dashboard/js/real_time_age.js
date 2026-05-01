/**
 * Real-time age display and calculation utilities
 */

class RealTimeAge {
    constructor() {
        this.init();
    }

    init() {
        // Update age display every minute
        this.startRealTimeUpdates();
        this.addAgeCalculationHelpers();
    }

    /**
     * Start real-time updates for age display
     */
    startRealTimeUpdates() {
        // Update immediately
        this.updateAgeDisplay();
        
        // Update every minute
        setInterval(() => {
            this.updateAgeDisplay();
        }, 60000); // 60 seconds

        // Update every second for time display
        setInterval(() => {
            this.updateCurrentTime();
        }, 1000);
    }

    /**
     * Update age display with current date
     */
    updateAgeDisplay() {
        const ageElements = document.querySelectorAll('[data-age-dob]');
        
        ageElements.forEach(element => {
            const dob = element.dataset.ageDob;
            if (dob) {
                const age = this.calculateAge(dob);
                const ageDetails = this.calculateDetailedAge(dob);
                
                // Update age display
                const ageDisplay = element.querySelector('.age-display');
                if (ageDisplay) {
                    ageDisplay.textContent = `${age} years old`;
                }

                // Update detailed age
                const detailsDisplay = element.querySelector('.age-details-display');
                if (detailsDisplay && ageDetails) {
                    detailsDisplay.textContent = `(${ageDetails.formatted})`;
                }

                // Update age category
                const categoryDisplay = element.querySelector('.age-category');
                if (categoryDisplay) {
                    const category = this.categorizeAge(age);
                    categoryDisplay.textContent = category;
                    categoryDisplay.className = `age-category age-${this.getCategoryClass(category)}`;
                }
            }
        });
    }

    /**
     * Update current time display
     */
    updateCurrentTime() {
        const timeElements = document.querySelectorAll('.current-time');
        const now = new Date();
        const timeString = now.toLocaleString('en-US', {
            weekday: 'short',
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });

        timeElements.forEach(element => {
            element.textContent = timeString;
        });
    }

    /**
     * Calculate age from date of birth
     */
    calculateAge(birthDate) {
        const birth = new Date(birthDate);
        const today = new Date();
        
        let age = today.getFullYear() - birth.getFullYear();
        const monthDiff = today.getMonth() - birth.getMonth();
        
        if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
            age--;
        }
        
        return age;
    }

    /**
     * Calculate detailed age breakdown
     */
    calculateDetailedAge(birthDate) {
        const birth = new Date(birthDate);
        const today = new Date();
        
        let years = today.getFullYear() - birth.getFullYear();
        let months = today.getMonth() - birth.getMonth();
        let days = today.getDate() - birth.getDate();
        
        if (days < 0) {
            const lastMonth = new Date(today.getFullYear(), today.getMonth(), 0);
            days += lastMonth.getDate();
            months--;
        }
        
        if (months < 0) {
            months += 12;
            years--;
        }
        
        return {
            years,
            months,
            days,
            formatted: `${years} years, ${months} months, ${days} days`
        };
    }

    /**
     * Categorize age
     */
    categorizeAge(age) {
        if (age < 18) return "Under 18";
        if (age < 20) return "18-19";
        if (age < 22) return "20-21";
        if (age < 25) return "22-24";
        if (age < 30) return "25-29";
        return "30+";
    }

    /**
     * Get CSS class for age category
     */
    getCategoryClass(category) {
        return category.toLowerCase().replace(' ', '-').replace('+', 'plus');
    }

    /**
     * Add age calculation helpers to the page
     */
    addAgeCalculationHelpers() {
        // Add current time display if not present
        if (!document.querySelector('.current-time-display')) {
            const profileHeader = document.querySelector('.profile-header');
            if (profileHeader) {
                const timeDisplay = document.createElement('div');
                timeDisplay.className = 'current-time-display';
                timeDisplay.innerHTML = `
                    <small class="text-muted">
                        <span class="current-time"></span>
                    </small>
                `;
                profileHeader.appendChild(timeDisplay);
            }
        }
    }

    
    /**
     * Format date for display
     */
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    }

    /**
     * Check if birthday is today
     */
    isBirthdayToday(birthDate) {
        const birth = new Date(birthDate);
        const today = new Date();
        
        return birth.getMonth() === today.getMonth() && 
               birth.getDate() === today.getDate();
    }

    /**
     * Add birthday celebration
     */
    addBirthdayCelebration() {
        const ageElements = document.querySelectorAll('[data-age-dob]');
        
        ageElements.forEach(element => {
            const dob = element.dataset.ageDob;
            if (dob && this.isBirthdayToday(dob)) {
                const ageDisplay = element.querySelector('.age-primary');
                if (ageDisplay && !ageDisplay.querySelector('.birthday-indicator')) {
                    const indicator = document.createElement('span');
                    indicator.className = 'birthday-indicator';
                    indicator.innerHTML = '🎂';
                    indicator.title = 'Happy Birthday!';
                    ageDisplay.appendChild(indicator);
                }
            }
        });
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.realTimeAge = new RealTimeAge();
    
    // Check for birthdays on page load
    setTimeout(() => {
        window.realTimeAge.addBirthdayCelebration();
    }, 1000);
});

// Export for external use
window.RealTimeAge = RealTimeAge;
