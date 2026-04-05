document.documentElement.classList.add("js");

const filterForm = document.querySelector(".topbar-filters");
const filterSelects = document.querySelectorAll(".filter-select");
const filterLoadingOverlay = document.getElementById("filter-loading-overlay");
const scrollRegions = document.querySelectorAll("[data-scroll-region]");

const setFilterLoadingState = (isLoading) => {
    if (!filterLoadingOverlay) {
        return;
    }

    document.body.classList.toggle("is-filter-loading", isLoading);
    document.body.setAttribute("aria-busy", isLoading ? "true" : "false");
    filterLoadingOverlay.hidden = !isLoading;
    filterLoadingOverlay.setAttribute("aria-hidden", isLoading ? "false" : "true");
};

const showFilterLoadingState = () => {
    if (document.body.classList.contains("is-filter-loading")) {
        return;
    }

    setFilterLoadingState(true);
};

const clearFilterLoadingState = () => {
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
            showFilterLoadingState();
            window.requestAnimationFrame(() => {
                filterForm.requestSubmit();
            });
        }
    });
});

window.addEventListener("pageshow", () => {
    clearFilterLoadingState();
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
