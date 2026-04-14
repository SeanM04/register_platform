/**
 * Completion Analysis Page JavaScript
 * Handles data fetching, chart rendering, and user interactions
 */

class CompletionAnalysis {
    constructor() {
        this.root = document.querySelector('.completion-layout');
        this.payloadUrl = this.root?.dataset.payloadUrl || '/metrics/completion/payload/';
        this.currentData = null;
        this.currentFilters = {
            academic_year: '',
            semester: '',
            programme_id: '',
            faculty: ''
        };
        this.currentPage = 1;
        this.itemsPerPage = 25;
        this.sortColumn = null;
        this.sortDirection = 'asc';
        this.charts = {};
        
        this.init();
    }

    async init() {
        this.bindEvents();
        await this.loadInitialData();
        this.setupChartInstances();
    }

    bindEvents() {
        // Filter events
        document.getElementById('academic-year-filter').addEventListener('change', (e) => {
            this.currentFilters.academic_year = e.target.value;
            this.loadData();
        });

        document.getElementById('semester-filter').addEventListener('change', (e) => {
            this.currentFilters.semester = e.target.value;
            this.loadData();
        });

        document.getElementById('programme-filter').addEventListener('change', (e) => {
            this.currentFilters.programme_id = e.target.value;
            this.loadData();
        });

        document.getElementById('faculty-filter').addEventListener('change', (e) => {
            this.currentFilters.faculty = e.target.value;
            this.loadData();
        });

        // Search event
        document.getElementById('student-search').addEventListener('input', (e) => {
            this.filterStudents(e.target.value);
        });

        // Export event
        document.getElementById('export-students').addEventListener('click', () => {
            this.exportStudentsData();
        });

        // Table sorting events
        document.querySelectorAll('[data-sort]').forEach(th => {
            th.addEventListener('click', (e) => {
                const column = e.target.dataset.sort;
                this.sortTable(column);
            });
        });

        // Chart fullscreen events
        document.querySelectorAll('[data-chart-fullscreen-toggle]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.toggleChartFullscreen(e.target);
            });
        });

        // Modal close events
        document.getElementById('error-modal-close').addEventListener('click', () => {
            this.hideErrorModal();
        });

        // Close modal on outside click
        document.getElementById('error-modal').addEventListener('click', (e) => {
            if (e.target.id === 'error-modal') {
                this.hideErrorModal();
            }
        });
    }

    async loadInitialData() {
        try {
            this.showLoading();
            
            // Load filter options
            await this.loadFilterOptions();
            
            // Load initial data
            await this.loadData();
        } catch (error) {
            this.showError('Failed to load initial data: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    async loadFilterOptions() {
        try {
            // Load academic years
            const yearsResponse = await fetch('/api/completion/academic-years');
            if (yearsResponse.ok) {
                const yearsData = await yearsResponse.json();
                this.populateFilter('academic-year-filter', yearsData.years || [], 'year', 'year');
            }

            // Load programmes
            const programmesResponse = await fetch('/api/completion/programmes');
            if (programmesResponse.ok) {
                const programmesData = await programmesResponse.json();
                this.populateFilter('programme-filter', programmesData.programmes || [], 'programme_id', 'programme_name');
            }

            // Load faculties
            const facultiesResponse = await fetch('/api/completion/faculties');
            if (facultiesResponse.ok) {
                const facultiesData = await facultiesResponse.json();
                this.populateFilter('faculty-filter', facultiesData.faculties || [], 'faculty', 'faculty');
            }
        } catch (error) {
            console.error('Failed to load filter options:', error);
        }
    }

    populateFilter(selectId, options, valueKey, labelKey) {
        const select = document.getElementById(selectId);
        const currentValue = select.value;
        
        // Clear existing options except the first one
        while (select.children.length > 1) {
            select.removeChild(select.lastChild);
        }

        // Add new options
        options.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option[valueKey];
            optionElement.textContent = option[labelKey];
            select.appendChild(optionElement);
        });

        // Restore current value if it still exists
        if (currentValue) {
            select.value = currentValue;
        }
    }

    async loadData() {
        try {
            this.showLoading();
            
            // Build query string
            const queryParams = new URLSearchParams();
            Object.entries(this.currentFilters).forEach(([key, value]) => {
                if (value) {
                    queryParams.append(key, value);
                }
            });

            // Fetch completion data
            const response = await fetch(`${this.payloadUrl}?${queryParams}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            
            if (result.status !== 'success') {
                throw new Error(result.message || 'Failed to load completion data');
            }

            this.currentData = result.data;
            
            // Update UI with new data
            this.updateMetrics();
            this.updateCharts();
            this.updateStudentsTable();
            
        } catch (error) {
            this.showError('Failed to load completion data: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    updateMetrics() {
        if (!this.currentData || !this.currentData.kpis) return;

        const kpis = this.currentData.kpis;
        
        // Update metric values
        this.updateMetricValue('total_students', kpis.total_students || 0);
        this.updateMetricValue('total_cohorts', kpis.total_cohorts || 0);
        this.updateMetricValue('average_completion_rate', kpis.average_completion_rate || 0);
        this.updateMetricValue('male_students', kpis.gender_distribution?.male || 0);
        this.updateMetricValue('female_students', kpis.gender_distribution?.female || 0);
    }

    updateMetricValue(key, value) {
        const element = document.querySelector(`[data-metric-key="${key}"]`);
        if (element) {
            element.classList.remove('is-loading');
            
            if (key.includes('rate')) {
                element.textContent = `${value}%`;
            } else {
                element.textContent = this.formatNumber(value);
            }
        }
    }

    formatNumber(num) {
        if (typeof num !== 'number') return num;
        return num.toLocaleString();
    }

    setupChartInstances() {
        // Initialize chart containers
        this.charts.cohort = this.createChart('cohort-completion-chart');
        this.charts.programme = this.createChart('programme-completion-chart');
    }

    createChart(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return null;

        // Create a simple canvas-based chart for now
        // In a real implementation, you'd use a charting library like Chart.js, D3.js, etc.
        const canvas = document.createElement('canvas');
        canvas.width = container.offsetWidth;
        canvas.height = 300;
        container.innerHTML = '';
        container.appendChild(canvas);

        return {
            canvas,
            ctx: canvas.getContext('2d'),
            container,
            data: null
        };
    }

    updateCharts() {
        if (!this.currentData || !this.currentData.charts) return;

        const charts = this.currentData.charts;
        
        // Update cohort completion chart
        if (charts.cohort_completion && this.charts.cohort) {
            this.renderCohortChart(charts.cohort_completion);
        }

        // Update programme completion chart
        if (charts.programme_completion && this.charts.programme) {
            this.renderProgrammeChart(charts.programme_completion);
        }
    }

    renderCohortChart(data) {
        const chart = this.charts.cohort;
        if (!chart || !data || data.length === 0) {
            this.showEmptyChart(chart, 'No cohort data available');
            return;
        }

        const ctx = chart.ctx;
        const canvas = chart.canvas;
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Simple bar chart implementation
        const padding = 40;
        const chartWidth = canvas.width - 2 * padding;
        const chartHeight = canvas.height - 2 * padding;
        const barWidth = chartWidth / data.length * 0.8;
        const barSpacing = chartWidth / data.length * 0.2;
        
        // Find max value for scaling
        const maxValue = Math.max(...data.map(d => d.completion_rate || 0));
        
        // Draw bars
        data.forEach((item, index) => {
            const x = padding + index * (barWidth + barSpacing);
            const barHeight = (item.completion_rate / maxValue) * chartHeight;
            const y = canvas.height - padding - barHeight;
            
            // Draw bar
            ctx.fillStyle = this.getRateColor(item.completion_rate);
            ctx.fillRect(x, y, barWidth, barHeight);
            
            // Draw label
            ctx.fillStyle = '#333';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(`C${item.cohort_period_id}`, x + barWidth / 2, canvas.height - 20);
            
            // Draw value
            ctx.fillText(`${item.completion_rate}%`, x + barWidth / 2, y - 5);
        });
        
        // Draw axes
        ctx.strokeStyle = '#ddd';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padding, padding);
        ctx.lineTo(padding, canvas.height - padding);
        ctx.lineTo(canvas.width - padding, canvas.height - padding);
        ctx.stroke();
    }

    renderProgrammeChart(data) {
        const chart = this.charts.programme;
        if (!chart || !data || data.length === 0) {
            this.showEmptyChart(chart, 'No programme data available');
            return;
        }

        const ctx = chart.ctx;
        const canvas = chart.canvas;
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Simple horizontal bar chart
        const padding = 40;
        const chartWidth = canvas.width - 2 * padding;
        const chartHeight = canvas.height - 2 * padding;
        const barHeight = chartHeight / data.length * 0.8;
        const barSpacing = chartHeight / data.length * 0.2;
        
        // Find max value for scaling
        const maxValue = Math.max(...data.map(d => d.completion_rate || 0));
        
        // Draw bars
        data.forEach((item, index) => {
            const y = padding + index * (barHeight + barSpacing);
            const barWidth = (item.completion_rate / maxValue) * chartWidth;
            
            // Draw bar
            ctx.fillStyle = this.getRateColor(item.completion_rate);
            ctx.fillRect(padding, y, barWidth, barHeight);
            
            // Draw label (truncate if too long)
            ctx.fillStyle = '#333';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'right';
            const label = item.programme_name.length > 15 
                ? item.programme_name.substring(0, 15) + '...'
                : item.programme_name;
            ctx.fillText(label, padding - 5, y + barHeight / 2 + 3);
            
            // Draw value
            ctx.textAlign = 'left';
            ctx.fillText(`${item.completion_rate}%`, padding + barWidth + 5, y + barHeight / 2 + 3);
        });
        
        // Draw axes
        ctx.strokeStyle = '#ddd';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padding, padding);
        ctx.lineTo(padding, canvas.height - padding);
        ctx.lineTo(canvas.width - padding, canvas.height - padding);
        ctx.stroke();
    }

    showEmptyChart(chart, message) {
        if (!chart) return;
        chart.container.innerHTML = `
            <div class="completion-empty-state">
                <div class="completion-empty-state-icon">chart</div>
                <div class="completion-empty-state-title">No Data</div>
                <div class="completion-empty-state-description">${message}</div>
            </div>
        `;
    }

    getRateColor(rate) {
        if (rate >= 80) return '#059669';  // Green
        if (rate >= 60) return '#d97706';  // Orange
        return '#dc2626';  // Red
    }

    updateStudentsTable() {
        if (!this.currentData || !this.currentData.students) {
            this.showEmptyStudentsTable();
            return;
        }

        const students = this.currentData.students;
        const tbody = document.getElementById('students-tbody');
        
        // Apply current search filter
        const filteredStudents = this.getFilteredStudents(students);
        
        // Apply sorting
        const sortedStudents = this.getSortedStudents(filteredStudents);
        
        // Apply pagination
        const paginatedStudents = this.getPaginatedStudents(sortedStudents);
        
        // Clear existing rows
        tbody.innerHTML = '';
        
        // Add new rows
        paginatedStudents.forEach(student => {
            const row = this.createStudentRow(student);
            tbody.appendChild(row);
        });
        
        // Update pagination
        this.updatePagination(sortedStudents.length);
    }

    createStudentRow(student) {
        const row = document.createElement('tr');
        
        row.innerHTML = `
            <td>${student.regnum}</td>
            <td>${student.student_name}</td>
            <td>${student.programme_name}</td>
            <td>${student.academic_stage}</td>
            <td><span class="completion-rate-badge ${this.getDecisionClass(student.decision)}">${student.decision}</span></td>
            <td><span class="completion-rate-badge ${this.getRateClass(student.completion_rate)}">${student.completion_rate}%</span></td>
            
        `;
        
        return row;
    }

    getDecisionClass(decision) {
        const decisionLower = (decision || '').toLowerCase();
        if (decisionLower.includes('proceed')) return 'high';
        if (decisionLower.includes('pending')) return 'medium';
        if (decisionLower.includes('retake') || decisionLower.includes('deferred')) return 'low';
        return 'medium';
    }

    getRateClass(rate) {
        if (rate >= 80) return 'high';
        if (rate >= 60) return 'medium';
        return 'low';
    }

    getFilteredStudents(students) {
        const searchTerm = document.getElementById('student-search').value.toLowerCase();
        
        if (!searchTerm) return students;
        
        return students.filter(student => {
            return (
                student.regnum.toLowerCase().includes(searchTerm) ||
                student.student_name.toLowerCase().includes(searchTerm) ||
                student.programme_name.toLowerCase().includes(searchTerm)
            );
        });
    }

    getSortedStudents(students) {
        if (!this.sortColumn) return students;
        
        return [...students].sort((a, b) => {
            let aVal = a[this.sortColumn];
            let bVal = b[this.sortColumn];
            
            // Handle null/undefined values
            if (aVal == null) aVal = '';
            if (bVal == null) bVal = '';
            
            // Convert to numbers if possible
            if (!isNaN(aVal) && !isNaN(bVal)) {
                aVal = parseFloat(aVal);
                bVal = parseFloat(bVal);
            }
            
            // Compare
            let result = 0;
            if (aVal > bVal) result = 1;
            else if (aVal < bVal) result = -1;
            
            return this.sortDirection === 'desc' ? -result : result;
        });
    }

    getPaginatedStudents(students) {
        const startIndex = (this.currentPage - 1) * this.itemsPerPage;
        const endIndex = startIndex + this.itemsPerPage;
        return students.slice(startIndex, endIndex);
    }

    sortTable(column) {
        // Update sort direction
        if (this.sortColumn === column) {
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortColumn = column;
            this.sortDirection = 'asc';
        }
        
        // Update header classes
        document.querySelectorAll('[data-sort]').forEach(th => {
            th.classList.remove('sort-asc', 'sort-desc');
        });
        
        const currentTh = document.querySelector(`[data-sort="${column}"]`);
        currentTh.classList.add(`sort-${this.sortDirection}`);
        
        // Update table
        this.updateStudentsTable();
    }

    updatePagination(totalItems) {
        const totalPages = Math.ceil(totalItems / this.itemsPerPage);
        const paginationContainer = document.getElementById('pagination');
        
        paginationContainer.innerHTML = '';
        
        if (totalPages <= 1) return;
        
        // Previous button
        const prevBtn = document.createElement('button');
        prevBtn.textContent = 'Previous';
        prevBtn.disabled = this.currentPage === 1;
        prevBtn.addEventListener('click', () => {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.updateStudentsTable();
            }
        });
        paginationContainer.appendChild(prevBtn);
        
        // Page numbers
        const startPage = Math.max(1, this.currentPage - 2);
        const endPage = Math.min(totalPages, this.currentPage + 2);
        
        for (let i = startPage; i <= endPage; i++) {
            const pageBtn = document.createElement('button');
            pageBtn.textContent = i;
            pageBtn.classList.toggle('active', i === this.currentPage);
            pageBtn.addEventListener('click', () => {
                this.currentPage = i;
                this.updateStudentsTable();
            });
            paginationContainer.appendChild(pageBtn);
        }
        
        // Next button
        const nextBtn = document.createElement('button');
        nextBtn.textContent = 'Next';
        nextBtn.disabled = this.currentPage === totalPages;
        nextBtn.addEventListener('click', () => {
            if (this.currentPage < totalPages) {
                this.currentPage++;
                this.updateStudentsTable();
            }
        });
        paginationContainer.appendChild(nextBtn);
        
        // Page info
        const pageInfo = document.createElement('div');
        pageInfo.className = 'page-info';
        const startItem = (this.currentPage - 1) * this.itemsPerPage + 1;
        const endItem = Math.min(this.currentPage * this.itemsPerPage, totalItems);
        pageInfo.textContent = `Showing ${startItem}-${endItem} of ${totalItems} students`;
        paginationContainer.appendChild(pageInfo);
    }

    showEmptyStudentsTable() {
        const tbody = document.getElementById('students-tbody');
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="completion-empty-state">
                    <div class="completion-empty-state-icon">people</div>
                    <div class="completion-empty-state-title">No Students Found</div>
                    <div class="completion-empty-state-description">No student data available for the selected filters.</div>
                </td>
            </tr>
        `;
    }

    filterStudents(searchTerm) {
        this.currentPage = 1; // Reset to first page when searching
        this.updateStudentsTable();
    }

    exportStudentsData() {
        if (!this.currentData || !this.currentData.students) {
            this.showError('No data available to export');
            return;
        }

        const students = this.getFilteredStudents(this.currentData.students);
        const sortedStudents = this.getSortedStudents(students);
        
        // Create CSV content
        const headers = ['Student ID', 'Student Name', 'Programme', 'Academic Stage', 'Decision', 'Completion Rate'];
        const rows = sortedStudents.map(student => [
            student.regnum,
            student.student_name,
            student.programme_name,
            student.academic_stage,
            student.decision,
            student.completion_rate,
           ''
        ]);
        
        const csvContent = [headers, ...rows]
            .map(row => row.map(cell => `"${cell}"`).join(','))
            .join('\n');
        
        // Download CSV
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `completion_analysis_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }

    toggleChartFullscreen(button) {
        const chartCard = button.closest('.completion-chart-card');
        chartCard.classList.toggle('is-fullscreen');
        
        const isFullscreen = chartCard.classList.contains('is-fullscreen');
        button.setAttribute('aria-pressed', isFullscreen);
        
        // Re-render chart when toggling fullscreen
        setTimeout(() => {
            this.setupChartInstances();
            this.updateCharts();
        }, 100);
    }

    showLoading() {
        document.getElementById('loading-overlay').classList.add('active');
    }

    hideLoading() {
        document.getElementById('loading-overlay').classList.remove('active');
    }

    showError(message) {
        document.getElementById('error-message').textContent = message;
        document.getElementById('error-modal').classList.add('active');
    }

    hideErrorModal() {
        document.getElementById('error-modal').classList.remove('active');
    }
}

// Initialize the page when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new CompletionAnalysis();
});
