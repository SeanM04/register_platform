export const initialiseAcademicLevelSearch = (elements) => {
    const { levelSearchForm, levelSearchInput } = elements;
    let levelSearchTimer = null;

    if (!levelSearchForm || !levelSearchInput) {
        return;
    }

    levelSearchInput.addEventListener("input", () => {
        window.clearTimeout(levelSearchTimer);
        levelSearchTimer = window.setTimeout(() => {
            levelSearchForm.requestSubmit();
        }, 450);
    });
};
