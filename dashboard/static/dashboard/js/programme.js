const programmeSearchForm = document.querySelector(".programme-toolbar");
const programmeSearchInput = document.querySelector(".programme-search");
let programmeSearchTimer = null;

if (programmeSearchForm && programmeSearchInput) {
    programmeSearchInput.addEventListener("input", () => {
        window.clearTimeout(programmeSearchTimer);
        programmeSearchTimer = window.setTimeout(() => {
            programmeSearchForm.requestSubmit();
        }, 450);
    });
}
