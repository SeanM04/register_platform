export const initialiseRiskSearch = (form, input) => {
    if (!form || !input) {
        return;
    }

    let searchTimer = null;
    input.addEventListener("input", () => {
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(() => {
            form.requestSubmit();
        }, 450);
    });
};
