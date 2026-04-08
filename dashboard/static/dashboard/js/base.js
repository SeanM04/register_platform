document.documentElement.classList.add("js");

const filterForm = document.querySelector(".topbar-filters");
const filterSelects = document.querySelectorAll(".filter-select");
const filterLoadingOverlay = document.getElementById("filter-loading-overlay");
const filterLoadingTitle = document.getElementById("filter-loading-title");
const filterLoadingText = document.getElementById("filter-loading-text");
const sidebarLinks = document.querySelectorAll(".sidebar-link");
const scrollRegions = document.querySelectorAll("[data-scroll-region]");

const DEFAULT_LOADING_COPY = {
    title: "Applying filters",
    text: "Updating the dashboard with your selected scope.",
};

const setLoadingCopy = (copy = DEFAULT_LOADING_COPY) => {
    if (filterLoadingTitle) {
        filterLoadingTitle.textContent = copy.title || DEFAULT_LOADING_COPY.title;
    }

    if (filterLoadingText) {
        filterLoadingText.textContent = copy.text || DEFAULT_LOADING_COPY.text;
    }
};

const setFilterLoadingState = (isLoading) => {
    if (!filterLoadingOverlay) {
        return;
    }

    document.body.classList.toggle("is-filter-loading", isLoading);
    document.body.setAttribute("aria-busy", isLoading ? "true" : "false");
    filterLoadingOverlay.hidden = !isLoading;
    filterLoadingOverlay.setAttribute("aria-hidden", isLoading ? "false" : "true");
};

const showFilterLoadingState = (copy = DEFAULT_LOADING_COPY) => {
    if (document.body.classList.contains("is-filter-loading")) {
        return;
    }

    setLoadingCopy(copy);
    setFilterLoadingState(true);
};

const clearFilterLoadingState = () => {
    setLoadingCopy(DEFAULT_LOADING_COPY);
    setFilterLoadingState(false);
};

if (filterForm) {
    filterForm.addEventListener("submit", () => {
        showFilterLoadingState();
    });
}

filterSelects.forEach((select) => {
    select.addEventListener("change", () => {
        if (filterForm && !document.body.classList.contains("is-filter-loading")) {
            showFilterLoadingState(DEFAULT_LOADING_COPY);
            window.requestAnimationFrame(() => {
                filterForm.requestSubmit();
            });
        }
    });
});

sidebarLinks.forEach((link) => {
    link.addEventListener("click", (event) => {
        if (
            event.defaultPrevented
            || event.button !== 0
            || event.metaKey
            || event.ctrlKey
            || event.shiftKey
            || event.altKey
        ) {
            return;
        }

        if (link.target && link.target !== "_self") {
            return;
        }

        const destination = new URL(link.href, window.location.href);
        const currentPage = new URL(window.location.href);
        const isSameDestination = destination.pathname === currentPage.pathname
            && destination.search === currentPage.search
            && destination.hash === currentPage.hash;

        if (isSameDestination) {
            return;
        }

        showFilterLoadingState({
            title: `Opening ${link.textContent.trim() || "workspace"}`,
            text: "Loading the selected dashboard workspace.",
        });
    });
});

window.addEventListener("pageshow", () => {
    clearFilterLoadingState();
    
    // Re-initialize charts after filter changes
    if (window.performance && window.performance.navigation.type === 1) {
        // Page was loaded via back/forward or refresh
        const charts = document.querySelectorAll('[role="img"][aria-label*="chart"]');
        charts.forEach(chart => {
            // Clear and re-render charts
            const chartId = chart.id;
            if (chartId && window.echarts && window.echarts.dispose) {
                window.echarts.dispose(chartId);
            }
        });
        
        // Trigger chart re-initialization if home page functions exist
        if (typeof initialiseOverviewPage === 'function') {
            setTimeout(() => {
                initialiseOverviewPage();
            }, 100);
        }
    }
});

scrollRegions.forEach((region) => {
    const updateScrollState = () => {
        const maxScrollLeft = region.scrollWidth - region.clientWidth;
        const isScrollable = maxScrollLeft > 4;
        const isAtStart = region.scrollLeft <= 4;
        const isAtEnd = region.scrollLeft >= maxScrollLeft - 4;

        region.classList.toggle("is-scrollable", isScrollable);
        region.classList.toggle("is-scroll-start", isAtStart);
        region.classList.toggle("is-scroll-end", isAtEnd);
    };

    region.scrollTop = 0;
    region.scrollLeft = 0;
    updateScrollState();
    region.addEventListener("scroll", updateScrollState, { passive: true });
    window.addEventListener("resize", updateScrollState);
});
