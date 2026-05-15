export const initialiseAcademicLevelSearch = (elements, { fetchPayload, onRowsUpdate } = {}) => {
    const { levelSearchForm, levelSearchInput } = elements;
    let levelSearchTimer = null;

    if (!levelSearchForm || !levelSearchInput) {
        return;
    }

    levelSearchForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const formData = new FormData(levelSearchForm);
        const searchParams = new URLSearchParams(formData);

        const currentUrl = new URL(window.location.href);
        currentUrl.searchParams.forEach((value, key) => {
            if (!searchParams.has(key)) {
                searchParams.set(key, value);
            }
        });

        const newUrl = new URL(window.location.href);
        newUrl.search = searchParams.toString();
        window.history.pushState({}, "", newUrl);

        if (fetchPayload && onRowsUpdate) {
            try {
                const data = await fetchPayload();
                if (data?.level_rows) {
                    onRowsUpdate(data.level_rows);
                }
            } catch (error) {
                console.error("[Academic Level] Search fetch failed:", error);
            }
        }
    });

    levelSearchInput.addEventListener("input", () => {
        window.clearTimeout(levelSearchTimer);
        levelSearchTimer = window.setTimeout(() => {
            levelSearchForm.requestSubmit();
        }, 450);
    });
};
