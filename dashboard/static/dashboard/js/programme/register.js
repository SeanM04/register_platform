export const initialiseRegisterInteractions = (form, input) => {
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
