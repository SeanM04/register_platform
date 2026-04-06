const escapeHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

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

export const renderProgrammeRegister = (body, metaElement, rows = [], registerMeta = {}) => {
    if (!body) {
        return;
    }

    if (!rows.length) {
        body.innerHTML = `
            <tr>
                <td class="programme-empty" colspan="8">No programmes matched the current filters.</td>
            </tr>
        `.trim();

        if (metaElement) {
            metaElement.textContent = "No programme rows are visible in the current scope.";
        }
        return;
    }

    body.innerHTML = rows.map((row) => `
        <tr>
            <td class="programme-td-code">${escapeHtml(row.code)}</td>
            <td>${escapeHtml(row.name)}</td>
            <td>${escapeHtml(row.faculty)}</td>
            <td>${escapeHtml(row.department)}</td>
            <td>${escapeHtml(row.students)}</td>
            <td>${escapeHtml(row.registrations)}</td>
            <td>${escapeHtml(row.average_mark)}</td>
            <td class="programme-td-pass">${escapeHtml(row.pass_rate)}</td>
        </tr>
    `).join("");

    if (metaElement) {
        const visibleCount = Number(registerMeta.visibleCount || rows.length || 0);
        metaElement.textContent = `Showing ${visibleCount.toLocaleString()} visible programme rows in the current register scope.`;
    }
};
