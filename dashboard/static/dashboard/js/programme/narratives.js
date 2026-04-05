import { escapeTooltipHtml, formatCount } from "./shared.js?v=20260404-programmes-story01";

const pickLeadRow = (rows, valueKey = "registrations") => {
    if (!rows.length) {
        return null;
    }
    return [...rows].sort((left, right) => right[valueKey] - left[valueKey] || left.name.localeCompare(right.name))[0];
};

const setElementText = (element, text) => {
    if (element) {
        element.textContent = text;
    }
};

const setHintMarkup = (element, hints) => {
    if (!element) {
        return;
    }

    element.innerHTML = hints
        .map((hint, index) => `
            <span class="programme-chart-hint${index === 0 ? " is-primary" : ""}">
                ${escapeTooltipHtml(hint)}
            </span>
        `)
        .join("")
        .trim();
};

const VALID_CARD_SEVERITIES = new Set(["stable", "medium", "high"]);
const VALID_CARD_CONFIDENCES = new Set(["low", "medium", "high"]);

export const normalizeCardSeverity = (value) => {
    const normalizedValue = String(value || "stable").trim().toLowerCase();
    return VALID_CARD_SEVERITIES.has(normalizedValue) ? normalizedValue : "stable";
};

export const normalizeCardConfidence = (value) => {
    const normalizedValue = String(value || "medium").trim().toLowerCase();
    return VALID_CARD_CONFIDENCES.has(normalizedValue) ? normalizedValue : "medium";
};

const getSeverityLabel = (severity) => {
    if (severity === "high") {
        return "Priority";
    }
    if (severity === "medium") {
        return "Watch";
    }
    return "Monitor";
};

const getConfidenceLabel = (confidence) => {
    if (confidence === "high") {
        return "High confidence";
    }
    if (confidence === "low") {
        return "Low confidence";
    }
    return "Medium confidence";
};

const buildAiBadgeMarkup = (source, severity = "stable", confidence = "medium") => {
    const providerLabel = source === "google"
        ? "AI-generated with Google Gemini"
        : source === "openai"
            ? "AI-generated with OpenAI"
            : "AI-generated";
    const normalizedSeverity = normalizeCardSeverity(severity);
    const normalizedConfidence = normalizeCardConfidence(confidence);
    const attentionLabel = normalizedSeverity === "high"
        ? "needs attention"
        : normalizedSeverity === "medium"
            ? "watch item"
            : "monitoring";
    const confidenceLabel = getConfidenceLabel(normalizedConfidence).toLowerCase();

    return `
        <span class="programme-ai-badge-group">
            <span class="programme-ai-badge is-${normalizedSeverity}" title="${escapeTooltipHtml(`${providerLabel}; ${attentionLabel}; ${confidenceLabel}`)}" aria-label="${escapeTooltipHtml(`${providerLabel}; ${attentionLabel}; ${confidenceLabel}`)}">
                <span class="programme-ai-badge-icon" aria-hidden="true">
                    <svg viewBox="0 0 20 20" focusable="false">
                        <path d="M7.2 4.1a3.6 3.6 0 0 0-3.6 3.6c0 .8.3 1.6.8 2.2-.3.4-.4.9-.4 1.4 0 1.3.9 2.5 2.2 2.8v.6c0 .8.6 1.4 1.4 1.4h1.1V9.3H7.6a.8.8 0 0 1 0-1.6h1.1V5.1c-.4-.6-.9-1-1.5-1Zm5.6 0c-.6 0-1.1.4-1.5 1v2.6h1.1a.8.8 0 1 1 0 1.6h-1.1v6.8h1.1c.8 0 1.4-.6 1.4-1.4v-.6a2.9 2.9 0 0 0 2.2-2.8c0-.5-.1-1-.4-1.4.5-.6.8-1.4.8-2.2a3.6 3.6 0 0 0-3.6-3.6Z"></path>
                        <path d="M10 6.2h2.1v1.4H10Zm-2.1 4.1H10v1.4H7.9Zm2.1 4.1h2.1v1.4H10Zm4.2-5.1h2.1v1.4h-2.1Z"></path>
                    </svg>
                </span>
                AI
            </span>
            <span class="programme-ai-context" aria-label="${escapeTooltipHtml(`${getSeverityLabel(normalizedSeverity)}. ${getConfidenceLabel(normalizedConfidence)}.`)}">
                ${escapeTooltipHtml(`${getSeverityLabel(normalizedSeverity)} | ${getConfidenceLabel(normalizedConfidence)}`)}
            </span>
        </span>
    `;
};

export const setActionText = (element, text, options = {}) => {
    if (!element) {
        return;
    }

    const showAiBadge = Boolean(options.showAiBadge);
    element.innerHTML = `
        ${showAiBadge ? buildAiBadgeMarkup(options.source, options.severity, options.confidence) : ""}
        <span class="programme-action-text">${escapeTooltipHtml(text)}</span>
    `.trim();
};

export const getProgrammeCardNarrative = (cardNarratives, cardKey, fallback) => {
    const card = cardNarratives?.cards?.[cardKey];
    if (!card || typeof card.insight !== "string" || typeof card.action !== "string") {
        return {
            ...fallback,
            severity: "stable",
            confidence: "medium",
        };
    }

    return {
        insight: card.insight.trim() || fallback.insight,
        action: card.action.trim() || fallback.action,
        severity: normalizeCardSeverity(card.severity),
        confidence: normalizeCardConfidence(card.confidence),
    };
};

const truncateLabel = (value, maxLength = 28) => {
    const text = String(value || "").trim();
    if (text.length <= maxLength) {
        return text;
    }
    return `${text.slice(0, maxLength - 3).trimEnd()}...`;
};

export const renderStoryBanner = (element, topLoadRows, departmentRows, lowPassRows) => {
    if (!element) {
        return;
    }

    const leadProgramme = topLoadRows[0] || null;
    const weakestProgramme = lowPassRows[0] || null;
    const leadDepartment = departmentRows[0] || null;

    if (!leadProgramme && !weakestProgramme && !leadDepartment) {
        element.innerHTML = "";
        element.hidden = true;
        return;
    }

    element.hidden = false;

    const title = leadProgramme
        ? `${leadProgramme.name} currently carries the heaviest visible programme load.`
        : "The programmes dashboard is tracking the strongest visible portfolio signals in the current scope.";
    const copyParts = [];

    if (leadProgramme) {
        copyParts.push(`${leadProgramme.name} represents ${leadProgramme.share_pct}% of visible registrations`);
    }
    if (weakestProgramme) {
        copyParts.push(`${weakestProgramme.name} is the weakest visible pass-rate signal at ${weakestProgramme.pass_rate}`);
    }
    if (leadDepartment) {
        copyParts.push(`${leadDepartment.department} currently anchors ${leadDepartment.share_pct}% of programme load`);
    }

    const summaryCards = [
        leadProgramme && {
            kicker: "Load Leader",
            value: `${leadProgramme.share_pct}% share`,
            copy: `${truncateLabel(leadProgramme.name)} is currently carrying the broadest registration footprint.`,
        },
        weakestProgramme && {
            kicker: "Quality Watch",
            value: weakestProgramme.pass_rate,
            copy: `${truncateLabel(weakestProgramme.name)} is currently the weakest visible pass-rate signal.`,
        },
        leadDepartment && {
            kicker: "Department Focus",
            value: `${leadDepartment.share_pct}% dept share`,
            copy: `${truncateLabel(leadDepartment.department)} currently carries the strongest programme concentration.`,
        },
    ].filter(Boolean);

    element.innerHTML = `
        <p class="programme-banner-kicker">Primary Takeaway</p>
        <h1 class="programme-banner-title">${escapeTooltipHtml(title)}</h1>
        <p class="programme-banner-copy">${escapeTooltipHtml(`${copyParts.join(", ")}.`)}</p>
        <div class="programme-banner-grid">
            ${summaryCards.map((card) => `
                <article class="programme-banner-card">
                    <p class="programme-banner-card-kicker">${escapeTooltipHtml(card.kicker)}</p>
                    <p class="programme-banner-card-value">${escapeTooltipHtml(card.value)}</p>
                    <p class="programme-banner-card-copy">${escapeTooltipHtml(card.copy)}</p>
                </article>
            `).join("")}
        </div>
    `;
};

export const buildLoadOverviewNarrative = (rows) => {
    const leadRow = rows[0] || null;
    const runnerUp = rows[1] || null;

    return {
        insight: leadRow
            ? `${leadRow.name} currently carries ${leadRow.share_pct}% of visible registrations${runnerUp ? `, ahead of ${runnerUp.name}` : ""}.`
            : "No programme-load insight is available for the current filters.",
        action: leadRow
            ? "Use the load chart first to separate the flagship programmes from the wider portfolio before opening the register."
            : "Adjust the current filters to bring the visible programme mix back into view.",
    };
};

export const initialiseLoadNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getProgrammeCardNarrative(cardNarratives, "load", buildLoadOverviewNarrative(rows));

    setElementText(elements.loadCopy, narrative.insight);
    setHintMarkup(elements.loadHints, [
        "Hover bars for counts",
        "Compare share and pass rate together",
    ]);
    setActionText(elements.loadNote, narrative.action, {
        showAiBadge: flags.narrativesAreAi,
        source: flags.narrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

export const buildDepartmentOverviewNarrative = (rows) => {
    const leadRow = rows[0] || null;

    return {
        insight: leadRow
            ? `${leadRow.department} currently anchors ${leadRow.share_pct}% of visible programme registrations across ${leadRow.programme_count} programmes.`
            : "No department concentration insight is available for the current filters.",
        action: leadRow
            ? "Use the department roll-up to see whether the visible programme load is concentrated inside one academic portfolio."
            : "Adjust the current filters to bring department concentration back into view.",
    };
};

export const initialiseDepartmentNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getProgrammeCardNarrative(cardNarratives, "departments", buildDepartmentOverviewNarrative(rows));

    setElementText(elements.departmentsCopy, narrative.insight);
    setHintMarkup(elements.departmentsHints, [
        "Hover bars for portfolio detail",
        "Department bars include programme count context",
    ]);
    setActionText(elements.departmentsNote, narrative.action, {
        showAiBadge: flags.narrativesAreAi,
        source: flags.narrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

export const buildQualityOverviewNarrative = (rows) => {
    const weakestRow = rows[0] || null;
    const underSixty = rows.filter((row) => Number(row.pass_rate_value || 0) < 60).length;

    return {
        insight: weakestRow
            ? `${weakestRow.name} currently has the lowest visible pass rate at ${weakestRow.pass_rate}, with ${formatCount(underSixty)} programmes below 60%.`
            : "No pass-rate quality insight is available for the current filters.",
        action: weakestRow
            ? "Use the quality ranking to decide which programmes should move from monitoring into academic review first."
            : "Adjust the current filters to bring marked programme performance back into view.",
    };
};

export const initialiseQualityNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getProgrammeCardNarrative(cardNarratives, "quality", buildQualityOverviewNarrative(rows));

    setElementText(elements.qualityCopy, narrative.insight);
    setHintMarkup(elements.qualityHints, [
        "Hover bars for full labels",
        "Lower pass rates sit at the top of the ranking",
    ]);
    setActionText(elements.qualityNote, narrative.action, {
        showAiBadge: flags.narrativesAreAi,
        source: flags.narrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

export const buildPerformanceOverviewNarrative = (rows) => {
    const leadRow = pickLeadRow(rows);
    const weakHighLoad = rows.find((row) => Number(row.registrations || 0) >= 50 && Number(row.pass_rate_value || 0) < 60);

    return {
        insight: weakHighLoad
            ? `${weakHighLoad.name} combines ${formatCount(weakHighLoad.registrations)} registrations with a ${weakHighLoad.pass_rate} pass rate.`
            : leadRow
                ? `${leadRow.name} is the largest visible programme at ${formatCount(leadRow.registrations)} registrations and is currently passing at ${leadRow.pass_rate}.`
                : "No performance-map insight is available for the current filters.",
        action: leadRow
            ? "Use the scatter to balance scale against quality before committing support or curriculum review time."
            : "Adjust the current filters to bring the registrations-versus-pass-rate picture back into view.",
    };
};

export const initialisePerformanceNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getProgrammeCardNarrative(cardNarratives, "performance", buildPerformanceOverviewNarrative(rows));

    setElementText(elements.performanceCopy, narrative.insight);
    setHintMarkup(elements.performanceHints, [
        "Hover bubbles for full labels",
        "Bubble size shows student footprint",
    ]);
    setActionText(elements.performanceNote, narrative.action, {
        showAiBadge: flags.narrativesAreAi,
        source: flags.narrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};
