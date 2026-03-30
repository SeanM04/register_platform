const searchForm = document.querySelector(".table-toolbar");
const searchInput = document.querySelector(".search-input");
let searchTimer = null;

if (searchForm && searchInput) {
    searchInput.addEventListener("input", () => {
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(() => {
            searchForm.requestSubmit();
        }, 450);
    });
}
