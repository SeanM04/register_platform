/**
 * Graduation Analysis Page JavaScript
 * Handles data fetching, chart rendering, and user interactions
 */

class GraduationAnalysis {
    constructor() {
        this.currentData = null;
        this.currentFilters = {
            faculty: '',
            programme_id: '',
            graduation_stage: '',
            min_rate: ''
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
        document.getElementById('faculty-filter').addEventListener('change', (e) => {
            this.currentFilters.faculty = e.target.value;
            this.loadData();
        });

        document.getElementById('programme-filter').addEventListener('change', (e) => {
            this.currentFilters.programme_id = e.target.value;
            this.loadData();
        });

        document.getElementById('graduation-stage-filter').addEventListener('change', (e) => {
            this.currentFilters.graduation_stage = e.target.value;
            this.loadData();
        });

        document.getElementById('rate-filter').addEventListener('input', (e) => {
            this.currentFilters.min_rate = e.target.value;
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

        document.getElementById('student-details-close').addEventListener('click', () => {
            this.hideStudentDetailsModal();
        });

        // Close modals on outside click
        document.getElementById('error-modal').addEventListener('click', (e) => {
            if (e.target.id === 'error-modal') {
                this.hideErrorModal();
            }
        });

        document.getElementById('student-details-modal').addEventListener('click', (e) => {
            if (e.target.id === 'student-details-modal') {
                this.hideStudentDetailsModal();
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
            // Load programmes
            const programmesResponse = await fetch('/api/graduation/programmes');
            if (programmesResponse.ok) {
                const programmesData = await programmesResponse.json();
                this.populateFilter('programme-filter', programmesData.programmes || [], 'programme_id', 'programme_name');
            }

            // Load faculties
            const facultiesResponse = await fetch('/api/graduation/faculties');
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

            // Fetch graduation data
            const response = await fetch(`/api/graduation?${queryParams}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            
            if (result.status !== 'success') {
                throw new Error(result.message || 'Failed to load graduation data');
            }

            this.currentData = result.data;
            
            // Update UI with new data
            this.updateMetrics();
            this.updateCharts();
            this.updateFacultyGrid();
            this.updateStudentsTable();
            this.updateStatistics();
            
        } catch (error) {
            this.showError('Failed to load graduation data: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    updateMetrics() {
        if (!this.currentData || !this.currentData.kpis) return;

        const kpis = this.currentData.kpis;
        
        // Update metric values
        this.updateMetricValue('total_graduated_students', kpis.total_graduated_students || 0);
        this.updateMetricValue('average_completion_graduation_rate', kpis.average_completion_graduation_rate || 0);
        this.updateMetricValue('on_time_graduation_rate', kpis.on_time_graduation_rate || 0);
        
        // Find best faculty rate
        const facultyRates = kpis.graduation_rate_by_faculty || {};
        const bestFaculty = Object.entries(facultyRates).reduce((best, [faculty, rate]) => {
            return (!best || rate > best.rate) ? { faculty, rate } : best;
        }, null);
        
        this.updateMetricValue('best_faculty_rate', bestFaculty ? `${bestFaculty.faculty}: ${bestFaculty.rate}%` : 'N/A');
        this.updateMetricValue('graduation_periods', this.calculateGraduationPeriods());
    }

    calculateGraduationPeriods() {
        if (!this.currentData || !this.currentData.students) return 'N/A';
        
        const periods = new Set();
        this.currentData.students.forEach(student => {
            // Extract graduation stage from programme name or other logic
            const stage = this.inferGraduationStage(student.programme_name);
            periods.add(stage);
        });
        
        return periods.size > 0 ? `${periods.size} stages` : 'N/A';
    }

    inferGraduationStage(programmeName) {
        const name = (programmeName || '').toLowerCase();
        if (name.includes('master')) return '2.2';
        if (name.includes('engineering') || name.includes('eng')) return '5.2';
        return '4.2';
    }

    updateMetricValue(key, value) {
        const element = document.querySelector(`[data-metric-key="${key}"]`);
        if (element) {
            element.classList.remove('is-loading');
            
            if (key.includes('rate') || key.includes('Rate')) {
                element.textContent = typeof value === 'string' && value.includes('%') ? value : `${value}%`;
            } else {
                element.textContent = value;
            }
        }
    }

    setupChartInstances() {
        // Initialize chart containers
        this.charts.programme = this.createChart('programme-graduation-chart');
        this.charts.cohort = this.createChart('cohort-graduation-chart');
        this.charts.performance = this.createChart('performance-distribution-chart');
        this.charts.timeline = this.createChart('graduation-timeline-chart');
    }

    createChart(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return null;

        // Create a simple canvas-based chart
        const canvas = document.createElement('canvas');
        canvas.width = container.offsetWidth;
        canvas.height = containerId.includes('distribution') || containerId.includes('timeline') ? 200 : 300;
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
        
        // Update programme graduation chart
        if (charts.programme_graduation_rate && this.charts.programme) {
            this.renderProgrammeChart(charts.programme_graduation_rate);
        }

        // Update cohort graduation chart
        if (charts.cohort_graduation_rate && this.charts.cohort) {
            this.renderCohortChart(charts.cohort_graduation_rate);
        }
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
        
        // Simple bar chart implementation
        const padding = 40;
        const chartWidth = canvas.width - 2 * padding;
        const chartHeight = canvas.height - 2 * padding;
        const barWidth = chartWidth / data.length * 0.8;
        const barSpacing = chartWidth / data.length * 0.2;
        
        // Find max value for scaling
        const maxValue = Math.max(...data.map(d => d.graduation_rate || 0));
        
        // Draw bars
        data.forEach((item, index) => {
            const x = padding + index * (barWidth + barSpacing);
            const barHeight = (item.graduation_rate / maxValue) * chartHeight;
            const y = canvas.height - padding - barHeight;
            
            // Draw bar
            ctx.fillStyle = this.getRateColor(item.graduation_rate);
            ctx.fillRect(x, y, barWidth, barHeight);
            
            // Draw label (truncate if too long)
            ctx.fillStyle = '#333';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            const label = item.programme_name.length > 12 
                ? item.programme_name.substring(0, 12) + '...'
                : item.programme_name;
            ctx.fillText(label, x + barWidth / 2, canvas.height - 20);
            
            // Draw value
            ctx.fillText(`${item.graduation_rate}%`, x + barWidth / 2, y - 5);
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
        
        // Simple line chart implementation
        const padding = 40;
        const chartWidth = canvas.width - 2 * padding;
        const chartHeight = canvas.height - 2 * padding;
        
        // Sort by cohort period
        const sortedData = [...data].sort((a, b) => a.cohort_period_id - b.cohort_period_id);
        
        // Find max value for scaling
        const maxValue = Math.max(...sortedData.map(d => d.graduation_rate || 0));
        const xStep = chartWidth / (sortedData.length - 1 || 1);
        
        // Draw line
        ctx.strokeStyle = '#3b82f6';
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        sortedData.forEach((item, index) => {
            const x = padding + index * xStep;
            const y = canvas.height - padding - (item.graduation_rate / maxValue) * chartHeight;
            
            if (index === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        
        ctx.stroke();
        
        // Draw points and labels
        sortedData.forEach((item, index) => {
            const x = padding + index * xStep;
            const y = canvas.height - padding - (item.graduation_rate / maxValue) * chartHeight;
            
            // Draw point
            ctx.fillStyle = this.getRateColor(item.graduation_rate);
            ctx.beginPath();
            ctx.arc(x, y, 4, 0, 2 * Math.PI);
            ctx.fill();
            
            // Draw label
            ctx.fillStyle = '#333';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(`C${item.cohort_period_id}`, x, canvas.height - 20);
            
            // Draw value
            ctx.fillText(`${item.graduation_rate}%`, x, y - 10);
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
            <div class="graduation-empty-state">
                <div class="graduation-empty-state-icon">chart</div>
                <div class="graduation-empty-state-title">No Data</div>
                <div class="graduation-empty-state-description">${message}</div>
            </div>
        `;
    }

    getRateColor(rate) {
        if (rate >= 80) return '#059669';  // Green
        if (rate >= 60) return '#d97706';  // Orange
        return '#dc2626';  // Red
    }

    updateFacultyGrid() {
        if (!this.currentData || !this.currentData.kpis || !this.currentData.kpis.graduation_rate_by_faculty) {
            this.showEmptyFacultyGrid();
            return;
        }

        const facultyRates = this.currentData.kpis.graduation_rate_by_faculty;
        const grid = document.getElementById('faculty-grid');
        
        grid.innerHTML = '';
        
        Object.entries(facultyRates).forEach(([faculty, rate]) => {
            const card = this.createFacultyCard(faculty, rate);
            grid.appendChild(card);
        });
    }

    createFacultyCard(faculty, rate) {
        const card = document.createElement('div');
        card.className = 'graduation-faculty-card';
        
        const rateClass = rate >= 80 ? 'high' : rate >= 60 ? 'medium' : 'low';
        
        card.innerHTML = `
            <h3 class="graduation-faculty-name">${faculty}</h3>
            <div class="graduation-faculty-rate ${rateClass}">${rate}%</div>
            <p class="graduation-faculty-students">Graduation Rate</p>
        `;
        
        return card;
    }

    showEmptyFacultyGrid() {
        const grid = document.getElementById('faculty-grid');
        grid.innerHTML = `
            <div class="graduation-empty-state">
                <div class="graduation-empty-state-icon">business</div>
                <div class="graduation-empty-state-title">No Faculty Data</div>
                <div class="graduation-empty-state-description">No faculty performance data available.</div>
            </div>
        `;
    }

    updateStudentsTable() {
        if (!this.currentData || !this.currentData.students) {
            this.showEmptyStudentsTable();
            return;
        }

        const students = this.currentData.students;
        const tbody = document.getElementById('students-tbody');
        
        // Apply filters
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
        row.style.cursor = 'pointer';
        row.addEventListener('click', () => this.showStudentDetails(student));
        
        const graduationStage = this.inferGraduationStage(student.programme_name);
        const onTime = this.calculateOnTime(student);
        
        row.innerHTML = `
            <td>${student.regnum}</td>
            <td>${student.student_name}</td>
            <td>${student.programme_name}</td>
            <td>${student.faculty}</td>
            <td><span class="graduation-rate-badge ${this.getRateClass(student.graduation_rate)}">${student.graduation_rate}%</span></td>
            <td><span class="graduation-rate-badge">${graduationStage}</span></td>
            <td>
                <span class="graduation-on-time graduation-on-time-${onTime ? 'yes' : 'no'}">
                    <span class="graduation-on-time-icon">${onTime ? 'check' : 'close'}</span>
                    ${onTime ? 'Yes' : 'No'}
                </span>
            </td>
        `;
        
        return row;
    }

    calculateOnTime(student) {
        // This is a simplified calculation
        // In a real implementation, you'd use the actual cohort tracking logic
        return student.graduation_rate >= 70; // Placeholder logic
    }

    getRateClass(rate) {
        if (rate >= 80) return 'high';
        if (rate >= 60) return 'medium';
        return 'low';
    }

    getFilteredStudents(students) {
        let filtered = [...students];
        
        // Apply search filter
        const searchTerm = document.getElementById('student-search').value.toLowerCase();
        if (searchTerm) {
            filtered = filtered.filter(student => {
                return (
                    student.regnum.toLowerCase().includes(searchTerm) ||
                    student.student_name.toLowerCase().includes(searchTerm) ||
                    student.programme_name.toLowerCase().includes(searchTerm) ||
                    student.faculty.toLowerCase().includes(searchTerm)
                );
            });
        }
        
        // Apply rate filter
        const minRate = parseFloat(this.currentFilters.min_rate);
        if (!isNaN(minRate)) {
            filtered = filtered.filter(student => student.graduation_rate >= minRate);
        }
        
        return filtered;
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
                <td colspan="7" class="graduation-empty-state">
                    <div class="graduation-empty-state-icon">people</div>
                    <div class="graduation-empty-state-title">No Students Found</div>
                    <div class="graduation-empty-state-description">No graduation data available for the selected filters.</div>
                </td>
            </tr>
        `;
    }

    filterStudents(searchTerm) {
        this.currentPage = 1; // Reset to first page when searching
        this.updateStudentsTable();
    }

    updateStatistics() {
        if (!this.currentData || !this.currentData.students) return;
        
        // Update performance distribution
        this.updatePerformanceDistribution();
        
        // Update graduation timeline
        this.updateGraduationTimeline();
        
        // Update programme rankings
        this.updateProgrammeRankings();
    }

    updatePerformanceDistribution() {
        const students = this.currentData.students;
        const distribution = {
            high: students.filter(s => s.graduation_rate >= 80).length,
            medium: students.filter(s => s.graduation_rate >= 60 && s.graduation_rate < 80).length,
            low: students.filter(s => s.graduation_rate < 60).length
        };
        
        const chart = this.charts.performance;
        if (!chart) return;
        
        const ctx = chart.ctx;
        const canvas = chart.canvas;
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Simple pie chart
        const total = distribution.high + distribution.medium + distribution.low;
        if (total === 0) {
            this.showEmptyChart(chart, 'No performance data');
            return;
        }
        
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        const radius = Math.min(centerX, centerY) - 20;
        
        const colors = {
            high: '#059669',
            medium: '#d97706',
            low: '#dc2626'
        };
        
        let currentAngle = -Math.PI / 2;
        
        Object.entries(distribution).forEach(([key, count]) => {
            if (count === 0) return;
            
            const sliceAngle = (count / total) * 2 * Math.PI;
            
            // Draw slice
            ctx.fillStyle = colors[key];
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.arc(centerX, centerY, radius, currentAngle, currentAngle + sliceAngle);
            ctx.closePath();
            ctx.fill();
            
            // Draw label
            const labelAngle = currentAngle + sliceAngle / 2;
            const labelX = centerX + Math.cos(labelAngle) * (radius * 0.7);
            const labelY = centerY + Math.sin(labelAngle) * (radius * 0.7);
            
            ctx.fillStyle = '#fff';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(`${key}`, labelX, labelY);
            ctx.fillText(`${count}`, labelX, labelY + 15);
            
            currentAngle += sliceAngle;
        });
    }

    updateGraduationTimeline() {
        const chart = this.charts.timeline;
        if (!chart) return;
        
        // This would show graduation trends over time
        // For now, show a placeholder
        this.showEmptyChart(chart, 'Timeline data coming soon');
    }

    updateProgrammeRankings() {
        if (!this.currentData || !this.currentData.charts || !this.currentData.charts.programme_graduation_rate) {
            this.showEmptyRankings();
            return;
        }
        
        const programmeData = this.currentData.charts.programme_graduation_rate;
        const rankings = document.getElementById('programme-rankings');
        
        // Sort by graduation rate
        const sorted = [...programmeData].sort((a, b) => b.graduation_rate - a.graduation_rate).slice(0, 10);
        
        rankings.innerHTML = '';
        
        sorted.forEach((programme, index) => {
            const item = document.createElement('div');
            item.className = 'graduation-ranking-item';
            
            item.innerHTML = `
                <span class="graduation-ranking-name">${index + 1}. ${programme.programme_name}</span>
                <span class="graduation-ranking-rate">${programme.graduation_rate}%</span>
            `;
            
            rankings.appendChild(item);
        });
    }

    showEmptyRankings() {
        const rankings = document.getElementById('programme-rankings');
        rankings.innerHTML = `
            <div class="graduation-empty-state">
                <div class="graduation-empty-state-title">No Rankings</div>
                <div class="graduation-empty-state-description">No programme rankings available.</div>
            </div>
        `;
    }

    showStudentDetails(student) {
        const modal = document.getElementById('student-details-modal');
        const content = document.getElementById('student-details-content');
        
        content.innerHTML = `
            <div class="graduation-student-details">
                <h4>${student.student_name}</h4>
                <div class="graduation-detail-grid">
                    <div class="graduation-detail-item">
                        <strong>Student ID:</strong> ${student.regnum}
                    </div>
                    <div class="graduation-detail-item">
                        <strong>Programme:</strong> ${student.programme_name}
                    </div>
                    <div class="graduation-detail-item">
                        <strong>Faculty:</strong> ${student.faculty}
                    </div>
                    <div class="graduation-detail-item">
                        <strong>Graduation Rate:</strong> <span class="graduation-rate-badge ${this.getRateClass(student.graduation_rate)}">${student.graduation_rate}%</span>
                    </div>
                    <div class="graduation-detail-item">
                        <strong>Graduation Stage:</strong> ${this.inferGraduationStage(student.programme_name)}
                    </div>
                    <div class="graduation-detail-item">
                        <strong>On-Time:</strong> <span class="graduation-on-time graduation-on-time-${this.calculateOnTime(student) ? 'yes' : 'no'}">${this.calculateOnTime(student) ? 'Yes' : 'No'}</span>
                    </div>
                </div>
                <div class="graduation-student-progress">
                    <h5>Progress Visualization</h5>
                    <div class="graduation-progress-bar">
                        <div class="graduation-progress-fill" style="width: ${student.graduation_rate}%"></div>
                    </div>
                    <p>Graduation Progress: ${student.graduation_rate}%</p>
                </div>
            </div>
        `;
        
        modal.classList.add('active');
    }

    hideStudentDetailsModal() {
        document.getElementById('student-details-modal').classList.remove('active');
    }

    exportStudentsData() {
        if (!this.currentData || !this.currentData.students) {
            this.showError('No data available to export');
            return;
        }

        const students = this.getFilteredStudents(this.currentData.students);
        const sortedStudents = this.getSortedStudents(students);
        
        // Create CSV content
        const headers = ['Student ID', 'Student Name', 'Programme', 'Faculty', 'Graduation Rate', 'Graduation Stage', 'On-Time'];
        const rows = sortedStudents.map(student => [
            student.regnum,
            student.student_name,
            student.programme_name,
            student.faculty,
            student.graduation_rate,
            this.inferGraduationStage(student.programme_name),
            this.calculateOnTime(student) ? 'Yes' : 'No'
        ]);
        
        const csvContent = [headers, ...rows]
            .map(row => row.map(cell => `"${cell}"`).join(','))
            .join('\n');
        
        // Download CSV
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `graduation_analysis_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }

    toggleChartFullscreen(button) {
        const chartCard = button.closest('.graduation-chart-card');
        chartCard.classList.toggle('is-fullscreen');
        
        const isFullscreen = chartCard.classList.contains('is-fullscreen');
        button.setAttribute('aria-pressed', isFullscreen);
        
        // Re-render chart when toggling fullscreen
        setTimeout(() => {
            this.setupChartInstances();
            this.updateCharts();
            this.updateStatistics();
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
    new GraduationAnalysis();
});
