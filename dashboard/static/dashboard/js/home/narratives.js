import { escapeTooltipHtml, formatCount } from "./shared.js?v=20260403-home-story04";

const pickLeadRow = (rows, fallback = null) => {
    if (!rows.length) {
        return fallback;
    }
    return [...rows].sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))[0];
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
            <span class="home-chart-hint${index === 0 ? " is-primary" : ""}">
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
        <span class="home-ai-badge-group">
            <span class="home-ai-badge is-${normalizedSeverity}" title="${escapeTooltipHtml(`${providerLabel}; ${attentionLabel}; ${confidenceLabel}`)}" aria-label="${escapeTooltipHtml(`${providerLabel}; ${attentionLabel}; ${confidenceLabel}`)}">
                <span class="home-ai-badge-icon" aria-hidden="true">
                    <svg viewBox="0 0 20 20" focusable="false">
                        <path d="M7.2 4.1a3.6 3.6 0 0 0-3.6 3.6c0 .8.3 1.6.8 2.2-.3.4-.4.9-.4 1.4 0 1.3.9 2.5 2.2 2.8v.6c0 .8.6 1.4 1.4 1.4h1.1V9.3H7.6a.8.8 0 0 1 0-1.6h1.1V5.1c-.4-.6-.9-1-1.5-1Zm5.6 0c-.6 0-1.1.4-1.5 1v2.6h1.1a.8.8 0 1 1 0 1.6h-1.1v6.8h1.1c.8 0 1.4-.6 1.4-1.4v-.6a2.9 2.9 0 0 0 2.2-2.8c0-.5-.1-1-.4-1.4.5-.6.8-1.4.8-2.2a3.6 3.6 0 0 0-3.6-3.6Z"></path>
                        <path d="M10 6.2h2.1v1.4H10Zm-2.1 4.1H10v1.4H7.9Zm2.1 4.1h2.1v1.4H10Zm4.2-5.1h2.1v1.4h-2.1Z"></path>
                    </svg>
                </span>
                AI
            </span>
            <span class="home-ai-context" aria-label="${escapeTooltipHtml(`${getSeverityLabel(normalizedSeverity)}. ${getConfidenceLabel(normalizedConfidence)}.`)}">
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
        <span class="home-action-text">${escapeTooltipHtml(text)}</span>
    `.trim();
};

export const getOverviewCardNarrative = (cardNarratives, cardKey, fallback) => {
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

const truncateLabel = (value, maxLength = 22) => {
    const text = String(value || "").trim();
    if (text.length <= maxLength) {
        return text;
    }
    return `${text.slice(0, maxLength - 3).trimEnd()}...`;
};

export const renderStoryBanner = (element, outcomeRows, riskRows, facultyRows, progressRows) => {
    if (!element) {
        return;
    }

    const leadFaculty = facultyRows[0] || null;
    const proceedRow = progressRows.find((row) => row.key === "proceed") || null;
    const hotRiskCount = riskRows
        .filter((row) => row.key === "critical" || row.key === "high")
        .reduce((total, row) => total + Number(row.count || 0), 0);
    const leadOutcome = pickLeadRow(outcomeRows);

    if (!leadFaculty && !leadOutcome && !hotRiskCount) {
        element.innerHTML = "";
        element.hidden = true;
        return;
    }

    element.hidden = false;

    const title = leadFaculty
        ? `${leadFaculty.label} currently carries the heaviest visible institutional load.`
        : "The landing page is tracking the strongest visible academic signals in the current scope.";
    const copyParts = [];

    if (leadFaculty) {
        copyParts.push(`${leadFaculty.label} accounts for ${leadFaculty.share_pct}% of registrations`);
    }
    if (hotRiskCount) {
        copyParts.push(`${formatCount(hotRiskCount)} students are already in the high-pressure risk bands`);
    }
    if (proceedRow) {
        copyParts.push(`Proceed decisions currently cover ${proceedRow.share_pct}% of registrations`);
    } else if (leadOutcome) {
        copyParts.push(`${leadOutcome.percent}% of visible assessment outcomes are currently ${leadOutcome.label.toLowerCase()}`);
    }

    const summaryCards = [
        leadFaculty && {
            kicker: "Load Leader",
            value: `${leadFaculty.share_pct}% share`,
            copy: `${truncateLabel(leadFaculty.label, 28)} is carrying the broadest visible registration load.`,
        },
        {
            kicker: "Risk Watch",
            value: hotRiskCount ? formatCount(hotRiskCount) : "Stable",
            copy: hotRiskCount
                ? "Critical and high-risk students already justify closer attention."
                : "High-pressure risk bands are currently light in this scope.",
        },
        (proceedRow || leadOutcome) && {
            kicker: "Momentum Signal",
            value: proceedRow ? `${proceedRow.share_pct}% proceed` : `${leadOutcome.percent}% ${leadOutcome.label.toLowerCase()}`,
            copy: proceedRow
                ? "Registration decisions still lean toward forward movement."
                : "Assessment outcomes are currently the clearest stability signal.",
        },
    ].filter(Boolean);

    element.innerHTML = `
        <p class="home-banner-kicker">Primary Takeaway</p>
        <h1 class="home-banner-title">${escapeTooltipHtml(title)}</h1>
        <p class="home-banner-copy">${escapeTooltipHtml(`${copyParts.join(", ")}.`)}</p>
        <div class="home-banner-grid">
            ${summaryCards.map((card) => `
                <article class="home-banner-card">
                    <p class="home-banner-card-kicker">${escapeTooltipHtml(card.kicker)}</p>
                    <p class="home-banner-card-value">${escapeTooltipHtml(card.value)}</p>
                    <p class="home-banner-card-copy">${escapeTooltipHtml(card.copy)}</p>
                </article>
            `).join("")}
        </div>
    `;
};

export const buildOutcomeOverviewNarrative = (rows) => {
    const leadRow = pickLeadRow(rows);
    const passedRow = rows.find((row) => row.key === "passed");
    const failedRow = rows.find((row) => row.key === "failed");
    const awaitingRow = rows.find((row) => row.key === "awaiting");
    const markedTotal = Number(passedRow?.count || 0) + Number(failedRow?.count || 0);
    const passRate = markedTotal ? Math.round((Number(passedRow?.count || 0) / markedTotal) * 100) : 0;

    return {
        insight: awaitingRow
            ? `Passed results currently represent ${passRate}% of marked outcomes, with ${formatCount(awaitingRow.count)} results still awaiting marks.`
            : leadRow
                ? `${leadRow.label} results currently account for ${leadRow.percent}% of visible assessment outcomes.`
                : "No assessment outcome insight is available for the current filters.",
        action: leadRow
            ? "Use the outcome donut first to separate academic health from marking backlog before opening a specialist page."
            : "Adjust the current filters to bring the assessment picture back into view.",
    };
};

export const initialiseOutcomeNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "outcomes", buildOutcomeOverviewNarrative(rows));

    setElementText(elements.outcomesCopy, narrative.insight);
    setHintMarkup(elements.outcomesHints, [
        "Hover slices for counts",
        "Assessment outcomes come from module results",
    ]);
    setActionText(elements.outcomesNote, narrative.action, {
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

export const buildRiskOverviewNarrative = (rows) => {
    const hotRiskCount = rows
        .filter((row) => row.key === "critical" || row.key === "high")
        .reduce((total, row) => total + Number(row.count || 0), 0);
    const stableRow = rows.find((row) => row.key === "stable");
    const moderateRow = rows.find((row) => row.key === "moderate");

    return {
        insight: hotRiskCount
            ? `${formatCount(hotRiskCount)} students are already in the high or critical bands, while ${stableRow ? `${stableRow.percent}% remain in the stable band` : "the rest of the cohort sits outside the highest pressure range"}.`
            : moderateRow
                ? `The visible cohort is mostly stable, but ${formatCount(moderateRow.count)} students are already in the moderate watch band.`
                : "No risk distribution insight is available for the current filters.",
        action: hotRiskCount || moderateRow
            ? "Use the risk mix first to judge whether the landing-page story is still preventive work or already urgent intervention."
            : "Adjust the current filters to bring the risk distribution story back into view.",
    };
};

export const initialiseRiskNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "risk", buildRiskOverviewNarrative(rows));

    setElementText(elements.riskCopy, narrative.insight);
    setHintMarkup(elements.riskHints, [
        "Hover bars for counts",
        "Risk bands combine marks, fails, carrying, and decisions",
    ]);
    setActionText(elements.riskNote, narrative.action, {
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

export const buildFacultyOverviewNarrative = (rows) => {
    const leadFaculty = rows[0] || null;
    const secondFaculty = rows[1] || null;

    return {
        insight: leadFaculty
            ? `${leadFaculty.label} currently carries ${leadFaculty.share_pct}% of visible registrations${secondFaculty ? `, ahead of ${secondFaculty.label}` : ""}.`
            : "No faculty-load insight is available for the current filters.",
        action: leadFaculty
            ? "Use faculty load as the quick capacity signal before opening the deeper insights workspace."
            : "Adjust the current filters to bring visible registration concentration back into view.",
    };
};

export const initialiseFacultyNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "faculty", buildFacultyOverviewNarrative(rows));

    setElementText(elements.facultyCopy, narrative.insight);
    setHintMarkup(elements.facultyHints, [
        "Hover bars for share",
        "Compare where visible demand is pooling first",
    ]);
    setActionText(elements.facultyNote, narrative.action, {
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

export const buildProgressOverviewNarrative = (rows) => {
    const leadRow = [...rows].sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))[0];

    return {
        insight: leadRow
            ? `${leadRow.label} currently represents ${leadRow.share_pct}% of visible registration decisions.`
            : "No registration-momentum insight is available for the current filters.",
        action: leadRow
            ? "Use the decision chart to judge whether the visible cohort is moving forward or building rework and review pressure."
            : "Adjust the current filters to bring the registration decision story back into view.",
    };
};

export const initialiseProgressNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "progress", buildProgressOverviewNarrative(rows));

    setElementText(elements.progressCopy, narrative.insight);
    setHintMarkup(elements.progressHints, [
        "Hover columns for counts",
        "Decision labels come directly from registration records",
    ]);
    setActionText(elements.progressNote, narrative.action, {
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};
