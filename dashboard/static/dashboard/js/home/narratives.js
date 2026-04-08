import { escapeTooltipHtml, formatCount } from "./shared.js?v=20260403-home-story04";

/**
 * Pick the strongest row from a chart dataset for banner and fallback narrative copy.
 */
const pickLeadRow = (rows, fallback = null) => {
    if (!rows.length) {
        return fallback;
    }
    return [...rows].sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))[0];
};

/**
 * Write plain text into an element when a narrative target is present.
 */
const setElementText = (element, text) => {
    if (element) {
        element.textContent = text;
    }
};

/**
 * Render the short hint chips shown under card introductions when needed.
 */
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
const CARD_SEVERITY_RANK = { stable: 0, medium: 1, high: 2 };
const CARD_CONFIDENCE_RANK = { low: 0, medium: 1, high: 2 };

/**
 * Normalize backend severity values before they drive badge styling.
 */
export const normalizeCardSeverity = (value) => {
    const normalizedValue = String(value || "stable").trim().toLowerCase();
    return VALID_CARD_SEVERITIES.has(normalizedValue) ? normalizedValue : "stable";
};

/**
 * Normalize backend confidence values before they drive badge styling.
 */
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

/**
 * Build the primary AI badge shown when a card narrative came from a provider response.
 */
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

/**
 * Build a temporary loading badge while the optional narrative request is in flight.
 */
const buildAiLoadingMarkup = () => `
    <span class="home-ai-badge-group">
        <span class="home-ai-badge is-loading" aria-label="AI narrative loading for this chart">
            <span class="home-ai-badge-icon" aria-hidden="true">
                <svg viewBox="0 0 20 20" focusable="false">
                    <path d="M10 2.5a1 1 0 0 1 1 1v1.5a1 1 0 1 1-2 0V3.5a1 1 0 0 1 1-1Zm0 10.5a1 1 0 0 1 1 1V16a1 1 0 1 1-2 0v-2a1 1 0 0 1 1-1Zm6.5-4a1 1 0 0 1 0 2H15a1 1 0 1 1 0-2h1.5Zm-11.5 0a1 1 0 1 1 0 2H3.5a1 1 0 1 1 0-2H5Zm8.23-4.73a1 1 0 0 1 1.41 1.41l-1.06 1.06a1 1 0 0 1-1.41-1.41l1.06-1.06Zm-7.4 7.4a1 1 0 0 1 1.41 1.41l-1.06 1.06a1 1 0 1 1-1.41-1.41l1.06-1.06Zm8.46 1.06a1 1 0 1 1-1.41 1.41l-1.06-1.06a1 1 0 0 1 1.41-1.41l1.06 1.06Zm-7.4-7.4a1 1 0 0 1-1.41 1.41L4.43 5.7A1 1 0 0 1 5.84 4.3l1.06 1.06Z"></path>
                </svg>
            </span>
            AI loading
        </span>
        <span class="home-ai-context is-loading">Summarising this chart</span>
    </span>
`;

/**
 * Build the deterministic guidance badge used when the page is showing fallback copy.
 */
const buildGuidanceBadgeMarkup = (severity = "stable", confidence = "medium") => {
    const normalizedSeverity = normalizeCardSeverity(severity);
    const normalizedConfidence = normalizeCardConfidence(confidence);

    return `
        <span class="home-ai-badge-group">
            <span class="home-ai-badge is-guidance is-${normalizedSeverity}" aria-label="${escapeTooltipHtml(`Rule-based guidance; ${getSeverityLabel(normalizedSeverity).toLowerCase()}; ${getConfidenceLabel(normalizedConfidence).toLowerCase()}`)}">
                Guidance
            </span>
            <span class="home-ai-context" aria-label="${escapeTooltipHtml(`${getSeverityLabel(normalizedSeverity)}. ${getConfidenceLabel(normalizedConfidence)}.`)}">
                ${escapeTooltipHtml(`${getSeverityLabel(normalizedSeverity)} | ${getConfidenceLabel(normalizedConfidence)}`)}
            </span>
        </span>
    `;
};

/**
 * Update the compact AI state element that sits above each chart-card introduction.
 */
const setCardAiState = (element, options = {}) => {
    if (!element) {
        return;
    }

    const pending = Boolean(options.pending);
    const showAiBadge = Boolean(options.showAiBadge);
    if (!pending && !showAiBadge) {
        element.hidden = true;
        element.innerHTML = "";
        return;
    }

    element.hidden = false;
    element.innerHTML = pending
        ? buildAiLoadingMarkup()
        : buildAiBadgeMarkup(options.source, options.severity, options.confidence);
};

/**
 * Render the chart footer guidance row, including AI or rule-based status badges.
 */
export const setActionText = (element, text, options = {}) => {
    if (!element) {
        return;
    }

    const showAiBadge = Boolean(options.showAiBadge);
    const showLoadingBadge = Boolean(options.pending);
    const showGuidanceBadge = Boolean(options.showGuidanceBadge);
    element.innerHTML = `
        ${showLoadingBadge
            ? buildAiLoadingMarkup()
            : showAiBadge
                ? buildAiBadgeMarkup(options.source, options.severity, options.confidence)
                : showGuidanceBadge
                    ? buildGuidanceBadgeMarkup(options.severity, options.confidence)
                    : ""}
        <span class="home-action-text">${escapeTooltipHtml(text)}</span>
    `.trim();
};

/**
 * Render the chapter-level summary block shown beneath each chapter heading.
 */
const setSummaryText = (element, text, options = {}) => {
    if (!element) {
        return;
    }

    const trimmedText = String(text || "").trim();
    if (!trimmedText) {
        element.hidden = true;
        element.innerHTML = "";
        return;
    }

    const showAiBadge = Boolean(options.showAiBadge);
    element.hidden = false;
    element.innerHTML = `
        ${showAiBadge ? buildAiBadgeMarkup(options.source, options.severity, options.confidence) : ""}
        <p class="home-flow-summary-copy">${escapeTooltipHtml(trimmedText)}</p>
    `.trim();
};

/**
 * Resolve a narrative for one card, falling back to local deterministic copy when needed.
 */
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

/**
 * Keep long labels compact in the story banner's supporting summary cards.
 */
const truncateLabel = (value, maxLength = 22) => {
    const text = String(value || "").trim();
    if (text.length <= maxLength) {
        return text;
    }
    return `${text.slice(0, maxLength - 3).trimEnd()}...`;
};

/**
 * Render the deterministic hero banner that frames the visible cohort story.
 */
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

/**
 * Build the local fallback narrative for the assessment-outcomes chart.
 */
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

/**
 * Apply the outcome-card intro copy, AI state chip, and footer guidance.
 */
export const initialiseOutcomeNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "outcomes", buildOutcomeOverviewNarrative(rows));

    setCardAiState(elements.outcomesAiState, {
        pending: flags.overviewNarrativesPending,
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
    setElementText(elements.outcomesCopy, narrative.insight);
    setHintMarkup(elements.outcomesHints, [
    ]);
    setActionText(elements.outcomesNote, narrative.action, {
        pending: flags.overviewNarrativesPending,
        showAiBadge: flags.overviewNarrativesAreAi,
        showGuidanceBadge: !flags.overviewNarrativesPending,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

/**
 * Build the local fallback narrative for the student-risk distribution chart.
 */
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

/**
 * Apply the risk-card intro copy, AI state chip, and footer guidance.
 */
export const initialiseRiskNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "risk", buildRiskOverviewNarrative(rows));

    setCardAiState(elements.riskAiState, {
        pending: flags.overviewNarrativesPending,
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
    setElementText(elements.riskCopy, narrative.insight);
    setHintMarkup(elements.riskHints, [
    ]);
    setActionText(elements.riskNote, narrative.action, {
        pending: flags.overviewNarrativesPending,
        showAiBadge: flags.overviewNarrativesAreAi,
        showGuidanceBadge: !flags.overviewNarrativesPending,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

/**
 * Collapse multiple card severities into one chapter-level summary severity.
 */
const getCombinedChapterSeverity = (narratives = []) => narratives.reduce((highestSeverity, narrative) => {
    const severity = normalizeCardSeverity(narrative?.severity);
    return CARD_SEVERITY_RANK[severity] > CARD_SEVERITY_RANK[highestSeverity] ? severity : highestSeverity;
}, "stable");

/**
 * Use the lowest underlying confidence so chapter badges stay conservative.
 */
const getCombinedChapterConfidence = (narratives = []) => narratives.reduce((lowestConfidence, narrative) => {
    const confidence = normalizeCardConfidence(narrative?.confidence);
    return CARD_CONFIDENCE_RANK[confidence] < CARD_CONFIDENCE_RANK[lowestConfidence] ? confidence : lowestConfidence;
}, "high");

/**
 * Render the combined summary block for Chapter 1.
 */
export const initialiseChapterOneNarrative = (elements, rows = {}, cardNarratives = {}, flags = {}) => {
    const outcomesNarrative = getOverviewCardNarrative(
        cardNarratives,
        "outcomes",
        buildOutcomeOverviewNarrative(rows.outcomeRows || []),
    );
    const riskNarrative = getOverviewCardNarrative(
        cardNarratives,
        "risk",
        buildRiskOverviewNarrative(rows.riskRows || []),
    );
    const chapterNarratives = [riskNarrative, outcomesNarrative];

    setSummaryText(
        elements.chapterOneSummary,
        `${riskNarrative.insight} ${outcomesNarrative.insight}`,
        {
            showAiBadge: flags.overviewNarrativesAreAi,
            source: flags.overviewNarrativeSource,
            severity: getCombinedChapterSeverity(chapterNarratives),
            confidence: getCombinedChapterConfidence(chapterNarratives),
        },
    );
};

/**
 * Build the local fallback narrative for the faculty-load chart.
 */
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

/**
 * Apply the faculty-card intro copy, AI state chip, and footer guidance.
 */
export const initialiseFacultyNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "faculty", buildFacultyOverviewNarrative(rows));

    setCardAiState(elements.facultyAiState, {
        pending: flags.overviewNarrativesPending,
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
    setElementText(elements.facultyCopy, narrative.insight);
    setHintMarkup(elements.facultyHints, [
    ]);
    setActionText(elements.facultyNote, narrative.action, {
        pending: flags.overviewNarrativesPending,
        showAiBadge: flags.overviewNarrativesAreAi,
        showGuidanceBadge: !flags.overviewNarrativesPending,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

/**
 * Build the local fallback narrative for the registration-decision chart.
 */
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

/**
 * Apply the progress-card intro copy, AI state chip, and footer guidance.
 */
export const initialiseProgressNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "progress", buildProgressOverviewNarrative(rows));

    setCardAiState(elements.progressAiState, {
        pending: flags.overviewNarrativesPending,
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
    setElementText(elements.progressCopy, narrative.insight);
    setHintMarkup(elements.progressHints, [
    ]);
    setActionText(elements.progressNote, narrative.action, {
        pending: flags.overviewNarrativesPending,
        showAiBadge: flags.overviewNarrativesAreAi,
        showGuidanceBadge: !flags.overviewNarrativesPending,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

/**
 * Render the combined summary block for Chapter 2.
 */
export const initialiseChapterTwoNarrative = (elements, rows = {}, cardNarratives = {}, flags = {}) => {
    const facultyNarrative = getOverviewCardNarrative(
        cardNarratives,
        "faculty",
        buildFacultyOverviewNarrative(rows.facultyRows || []),
    );
    const progressNarrative = getOverviewCardNarrative(
        cardNarratives,
        "progress",
        buildProgressOverviewNarrative(rows.progressRows || []),
    );
    const chapterNarratives = [facultyNarrative, progressNarrative];

    setSummaryText(
        elements.chapterTwoSummary,
        `${facultyNarrative.insight} ${progressNarrative.insight}`,
        {
            showAiBadge: flags.overviewNarrativesAreAi,
            source: flags.overviewNarrativeSource,
            severity: getCombinedChapterSeverity(chapterNarratives),
            confidence: getCombinedChapterConfidence(chapterNarratives),
        },
    );
};
