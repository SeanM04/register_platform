/**
 * Completion Analysis Page JavaScript
 * Handles data fetching, chart rendering, and user interactions
 */

class CompletionAnalysis {
    getFiltersFromURL() {
        const urlParams = new URLSearchParams(window.location.search);
        const filters = {};
        for (const [key, value] of urlParams) {
            if (key === 'year' || key === 'period' || key === 'faculty') {
                filters[key] = value;
            }
        }
        return filters;
    }

    constructor() {
        this.root = document.querySelector('.completion-layout');
        console.log('Root element found:', this.root);
        this.payloadUrl = this.root?.dataset.payloadUrl || '/metrics/completion/payload/';
        console.log('Payload URL:', this.payloadUrl);
        this.currentData = null;
        this.currentFilters = this.getFiltersFromURL();
        console.log('Current filters:', this.currentFilters);
        this.currentPage = 1;
        this.itemsPerPage = 10;
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
        // Search event
        const studentSearch = document.getElementById('student-search');
        if (studentSearch) {
            studentSearch.addEventListener('input', () => {
                this.filterStudents();
            });
        }

        // Export event
        document.getElementById('export-students').addEventListener('click', () => {
            this.exportStudentsData();
        });

        // Sorting functionality removed - table headers are no longer sortable

        // Chart fullscreen events
        document.querySelectorAll('[data-chart-fullscreen-toggle]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.toggleChartFullscreen(e.currentTarget);
            });
        });

        // Fullscreen event listeners
        document.addEventListener("fullscreenchange", () => this.syncFullscreenButtons());
        document.addEventListener("webkitfullscreenchange", () => this.syncFullscreenButtons());
        
        // Initial sync
        this.syncFullscreenButtons();

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
            await this.loadData();
        } catch (error) {
            this.showError('Failed to load initial data: ' + error.message);
        }
    }

    populateFilter(selectId, options, valueKey, labelKey) {
        const select = document.getElementById(selectId);
        const currentValue = select.value;

        while (select.children.length > 1) {
            select.removeChild(select.lastChild);
        }

        options.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option[valueKey];
            optionElement.textContent = option[labelKey];
            select.appendChild(optionElement);
        });

        if (currentValue) {
            select.value = currentValue;
        }
    }

    async loadData() {
        try {
            console.log('Loading data from:', this.payloadUrl);

            const queryParams = new URLSearchParams();
            Object.entries(this.currentFilters).forEach(([key, value]) => {
                if (value) {
                    queryParams.append(key, value);
                }
            });

            const fullUrl = `${this.payloadUrl}?${queryParams}`;
            console.log('Full request URL:', fullUrl);
            
            const response = await fetch(fullUrl);
            console.log('Response status:', response.status);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();

            if (result.status !== 'success') {
                throw new Error(result.message || 'Failed to load completion data');
            }

            this.currentData = result.data;

            this.updateMetrics();
            this.updateCharts();
            this.updateStudentsTable();

        } catch (error) {
            this.showError('Failed to load completion data: ' + error.message);
        }
    }

    updateMetrics() {
        if (!this.currentData || !this.currentData.kpis) return;

        const kpis = this.currentData.kpis;

        this.updateMetricValue('total_students', kpis.total_students || 0);
        this.updateMetricValue('total_cohorts', kpis.total_cohorts || 0);
        this.updateMetricValue('average_completion_rate', kpis.average_completion_rate || 0);
        this.updateMetricValue('male_students', kpis.gender_distribution?.male || 0);
        this.updateMetricValue('female_students', kpis.gender_distribution?.female || 0);
    }

    updateMetricValue(key, value) {
        const element = document.querySelector(`[data-metric-key="${key}"]`);
        if (element) {
            if (key.includes('rate')) {
                element.textContent = `${Math.round(value)}%`;
            } else {
                element.textContent = value;
            }
        }
    }

    formatNumber(num) {
        if (typeof num !== 'number') return num;
        return num.toString();
    }

    formatAcademicStage(stage) {
        if (!stage) return stage;
        return stage.replace(/,\s*/g, ' '); // Remove commas and extra spaces
    }

    setupChartInstances() {
        this.charts.cohort = this.createChart('cohort-completion-chart');
        this.charts.programme = this.createChart('programme-completion-chart');
    }

    createChart(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return null;

        const canvas = document.createElement('canvas');
        canvas.width = container.offsetWidth || 800; // Fallback width if container is hidden
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

        // Use requestAnimationFrame for non-blocking rendering
        requestAnimationFrame(() => {
            if (charts.cohort_completion && this.charts.cohort) {
                this.renderCohortChart(charts.cohort_completion);
            }

            if (charts.programme_completion && this.charts.programme) {
                this.renderProgrammeChart(charts.programme_completion);
            }
        });
    }

    renderCohortChart(data) {
        const chart = this.charts.cohort;
        if (!chart || !data || data.length === 0) {
            this.showEmptyChart(chart, 'No cohort data available');
            return;
        }

        const ctx = chart.ctx;
        const canvas = chart.canvas;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const padding = 40;
        const chartWidth = canvas.width - 2 * padding;
        const chartHeight = canvas.height - 2 * padding;
        const barWidth = chartWidth * 0.8;
        const barSpacing = chartWidth * 0.2;

        const maxValue = Math.max(...data.map(d => d.completion_rate || 0), 1);

        data.forEach((item, index) => {
            const x = padding + barSpacing;
            const barHeight = (item.completion_rate / maxValue) * chartHeight;
            const y = canvas.height - padding - barHeight;

            ctx.fillStyle = this.getRateColor(item.completion_rate);
            ctx.fillRect(x, y, barWidth, barHeight);

            ctx.fillStyle = '#333';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(`C${item.cohort_period_id}`, x + barWidth / 2, canvas.height - 20);
            ctx.fillText(`${Math.round(item.completion_rate)}%`, x + barWidth / 2, y - 5);
        });

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

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const padding = 40;
        const chartWidth = canvas.width - 2 * padding;
        const chartHeight = canvas.height - 2 * padding;
        const barWidth = chartWidth / data.length * 0.6;
        const barSpacing = chartWidth / data.length * 0.4;

        const maxValue = Math.max(...data.map(d => d.completion_rate || 0), 1);

        data.forEach((item, index) => {
            const x = padding + index * (barWidth + barSpacing);
            const barHeight = (item.completion_rate / maxValue) * chartHeight;
            const y = canvas.height - padding - barHeight;

            ctx.fillStyle = this.getRateColor(item.completion_rate);
            ctx.fillRect(x, y, barWidth, barHeight);

            ctx.fillStyle = '#333';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            const label = item.programme_name.length > 15
                ? item.programme_name.substring(0, 15) + '...'
                : item.programme_name;
            ctx.fillText(label, x + barWidth / 2, canvas.height - 20);
            ctx.fillText(`${Math.round(item.completion_rate)}%`, x + barWidth / 2, y - 5);
        });

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
        if (rate >= 80) return '#059669';
        if (rate >= 60) return '#d97706';
        return '#dc2626';
    }

    updateStudentsTable() {
        if (!this.currentData || !this.currentData.students) {
            this.showEmptyStudentsTable();
            return;
        }

        const students = this.currentData.students;
        const tbody = document.getElementById('students-tbody');

        const filteredStudents = this.getFilteredStudents(students);
        const sortedStudents = this.getSortedStudents(filteredStudents);
        const paginatedStudents = this.getPaginatedStudents(sortedStudents);

        // Use document fragment for better performance
        const fragment = document.createDocumentFragment();
        
        paginatedStudents.forEach(student => {
            const row = this.createStudentRow(student);
            fragment.appendChild(row);
        });

        // Single DOM operation - much faster
        tbody.innerHTML = '';
        tbody.appendChild(fragment);

        this.updatePagination(sortedStudents.length);
    }

    createStudentRow(student) {
        const row = document.createElement('tr');

        row.innerHTML = `
            <td class="students-td-name">
                <a class="student-link" href="/students/${student.detail_slug}/" aria-label="View ${student.student_name} profile">
                    ${student.student_name ?? ''}
                </a>
            </td>
            <td>${student.programme_name ?? ''}</td>
            <td>${this.formatAcademicStage(student.academic_stage ?? '')}</td>
            <td><span class="completion-rate-badge ${this.getDecisionClass(student.decision)}">${student.decision ?? ''}</span></td>
            <td><span class="completion-rate-badge ${this.getRateClass(student.completion_rate)}">${Math.round(student.completion_rate ?? 0)}%</span></td>
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
                (student.student_name || '').toLowerCase().includes(searchTerm) ||
                (student.programme_name || '').toLowerCase().includes(searchTerm)
            );
        });
    }

    getSortedStudents(students) {
        if (!this.sortColumn) return students;

        return [...students].sort((a, b) => {
            let aVal = a[this.sortColumn];
            let bVal = b[this.sortColumn];

            if (aVal == null) aVal = '';
            if (bVal == null) bVal = '';

            if (!isNaN(aVal) && !isNaN(bVal) && aVal !== '' && bVal !== '') {
                aVal = parseFloat(aVal);
                bVal = parseFloat(bVal);
            }

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
        if (this.sortColumn === column) {
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortColumn = column;
            this.sortDirection = 'asc';
        }

        document.querySelectorAll('[data-sort]').forEach(th => {
            th.classList.remove('sort-asc', 'sort-desc');
        });

        const currentTh = document.querySelector(`[data-sort="${column}"]`);
        if (currentTh) {
            currentTh.classList.add(`sort-${this.sortDirection}`);
        }

        this.updateStudentsTable();
    }

    updatePagination(totalItems) {
        const totalPages = Math.ceil(totalItems / this.itemsPerPage);
        const paginationContainer = document.getElementById('pagination');
        const resultsMeta = document.getElementById('results-meta');

        // Update results meta
        const startItem = totalItems > 0 ? (this.currentPage - 1) * this.itemsPerPage + 1 : 0;
        const endItem = Math.min(this.currentPage * this.itemsPerPage, totalItems);
        resultsMeta.textContent = `Showing ${startItem}-${endItem} of ${totalItems} students`;

        paginationContainer.innerHTML = '';

        if (totalPages <= 1) return;

        // Previous button
        const prevLink = document.createElement('a');
        prevLink.className = 'page-link page-link-arrow';
        prevLink.textContent = 'Prev';
        if (this.currentPage === 1) {
            prevLink.className += ' is-disabled';
            prevLink.href = '#';
        } else {
            prevLink.href = '#';
            prevLink.addEventListener('click', (e) => {
                e.preventDefault();
                this.currentPage--;
                this.updateStudentsTable();
            });
        }
        paginationContainer.appendChild(prevLink);

        // Page numbers
        const startPage = Math.max(1, this.currentPage - 2);
        const endPage = Math.min(totalPages, this.currentPage + 2);

        for (let i = startPage; i <= endPage; i++) {
            const pageLink = document.createElement(i === this.currentPage ? 'span' : 'a');
            pageLink.className = 'page-link';
            if (i === this.currentPage) {
                pageLink.className += ' is-current';
                pageLink.textContent = i;
            } else {
                pageLink.href = '#';
                pageLink.textContent = i;
                pageLink.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.currentPage = i;
                    this.updateStudentsTable();
                });
            }
            paginationContainer.appendChild(pageLink);
        }

        // Next button
        const nextLink = document.createElement('a');
        nextLink.className = 'page-link page-link-arrow';
        nextLink.textContent = 'Next';
        if (this.currentPage === totalPages) {
            nextLink.className += ' is-disabled';
            nextLink.href = '#';
        } else {
            nextLink.href = '#';
            nextLink.addEventListener('click', (e) => {
                e.preventDefault();
                this.currentPage++;
                this.updateStudentsTable();
            });
        }
        paginationContainer.appendChild(nextLink);
    }

    showEmptyStudentsTable() {
        const tbody = document.getElementById('students-tbody');
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="completion-empty-state">
                    <div class="completion-empty-state-icon">people</div>
                    <div class="completion-empty-state-title">No Students Found</div>
                    <div class="completion-empty-state-description">No student data available for the selected filters.</div>
                </td>
            </tr>
        `;
    }

    filterStudents() {
        this.currentPage = 1;
        this.updateStudentsTable();
    }

    exportStudentsData() {
        if (!this.currentData || !this.currentData.students) {
            this.showError('No data available to export');
            return;
        }

        const students = this.getFilteredStudents(this.currentData.students);
        const sortedStudents = this.getSortedStudents(students);

        const headers = ['Student Name', 'Academic Programme', 'Academic Stage', 'Decision Status', 'Completion Rate'];
        const rows = sortedStudents.map(student => [
            student.student_name ?? '',
            student.programme_name ?? '',
            this.formatAcademicStage(student.academic_stage ?? ''),
            student.decision ?? '',
            `${Math.round(student.completion_rate ?? 0)}%`
        ]);

        const csvContent = [headers, ...rows]
            .map(row => row.map(cell => `"${cell}"`).join(','))
            .join('\n');

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
        const chartCard = button.closest('.demographic-insight-card');
        
        if (!chartCard) return;
        
        try {
            if (document.fullscreenElement === chartCard) {
                // Exit fullscreen
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                } else if (document.webkitExitFullscreen) {
                    document.webkitExitFullscreen();
                }
            } else {
                // Enter fullscreen
                if (chartCard.requestFullscreen) {
                    chartCard.requestFullscreen();
                } else if (chartCard.webkitRequestFullscreen) {
                    chartCard.webkitRequestFullscreen();
                }
            }
        } catch (error) {
            console.error('Fullscreen error:', error);
        }
        
        this.syncFullscreenButtons();
    }

    syncFullscreenButtons() {
        const activeCard = document.fullscreenElement;
        
        document.querySelectorAll('[data-chart-fullscreen-toggle]').forEach(button => {
            const card = button.closest('.demographic-insight-card');
            const chartTitle = button.dataset.chartTitle || "chart";
            const isActive = Boolean(card && activeCard === card);
            
            if (card) {
                card.classList.toggle("is-fullscreen", isActive);
            }
            
            button.textContent = isActive ? "Exit full screen" : "Full screen";
            button.setAttribute('aria-pressed', isActive);
        });
    }

    showError(message) {
        document.getElementById('error-message').textContent = message;
        document.getElementById('error-modal').classList.add('active');
    }

    hideErrorModal() {
        document.getElementById('error-modal').classList.remove('active');
    }
}

console.log('Completion.js loaded and DOM ready');

document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded event fired');
    try {
        new CompletionAnalysis();
        console.log('CompletionAnalysis instance created');
    } catch (error) {
        console.error('Error creating CompletionAnalysis:', error);
    }
});