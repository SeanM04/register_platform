document.documentElement.classList.add("js");

const filterForm = document.querySelector(".topbar-filters");
const filterSelects = document.querySelectorAll(".filter-select");
const scrollRegions = document.querySelectorAll("[data-scroll-region]");

filterSelects.forEach((select) => {
    select.addEventListener("change", () => {
        if (filterForm) {
            filterForm.requestSubmit();
        }
    });
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
