const renderLevelTable = (context) => {
    // 动态查询 table body，避免依赖初始化时缓存的引用
    const tableBody = document.querySelector(".level-table tbody");
    if (!tableBody) {
        console.warn('[Academic Level] Table body element not found. Available elements:', Object.keys(context.elements || {}));
        return;
    }

    const rows = context.data.levelRows || [];
    if (!rows.length) {
        tableBody.innerHTML = `
            <tr>
                <td class="level-empty" colspan="6">No academic level data matched the current filters.</td>
            </tr>
        `.trim();
        context.elements.levelTableRows = [];
        return;
    }

    console.log('[Academic Level] Rendering table with', rows.length, 'rows');
    tableBody.innerHTML = rows.map((row) => `
        <tr data-level-row="${escapeTooltipHtml(row.level)}">
            <td class="level-td-key">${escapeTooltipHtml(row.level)}</td>
            <td>${escapeTooltipHtml(row.students)}</td>
            <td>${escapeTooltipHtml(row.registrations)}</td>
            <td>${escapeTooltipHtml(row.average_mark)}</td>
            <td class="level-td-pass">
                <span class="level-pass-pill${row.below_target ? " is-below-target" : ""}">${escapeTooltipHtml(row.pass_rate)}</span>
                ${row.below_target ? '<span class="level-pass-flag">Below 85% target</span>' : ""}
            </td>
            <td class="level-td-programme">${escapeTooltipHtml(row.top_programme || "")}</td>
        </tr>
    `).join("").trim();
    context.elements.levelTableRows = Array.from(tableBody.querySelectorAll("[data-level-row]"));
};
