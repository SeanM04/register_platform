const riskSearchForm = document.querySelector(".risk-toolbar");
const riskSearchInput = document.querySelector(".risk-search");
let riskSearchTimer = null;

if (riskSearchForm && riskSearchInput) {
    riskSearchInput.addEventListener("input", () => {
        window.clearTimeout(riskSearchTimer);
        riskSearchTimer = window.setTimeout(() => {
            riskSearchForm.requestSubmit();
        }, 450);
    });
}
