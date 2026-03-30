document.querySelectorAll("[data-card]").forEach((card, index) => {
    window.setTimeout(() => {
        card.classList.add("is-ready");
    }, 60 * (index + 1));
});
