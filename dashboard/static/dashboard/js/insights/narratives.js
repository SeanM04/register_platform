import { escapeTooltipHtml, formatChartLabel } from "./shared.js?v=20260403-insights-story02";

const setElementText = (element, text) => {
    if (element) {
        element.textContent = text;
    }
};

const setHintMarkup = (element, hints) => {
    if (!element) {
        return;
    }

    element.innerHTML = hints.map((hint) => `
        <span class="insight-chart-hint${hint.kind ? ` is-${hint.kind}` : ""}">
            ${escapeTooltipHtml(hint.label)}
        </span>
    `).join("").trim();
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
        <span class="insight-ai-badge-group">
            <span class="insight-ai-badge is-${normalizedSeverity}" title="${escapeTooltipHtml(`${providerLabel}; ${attentionLabel}; ${confidenceLabel}`)}" aria-label="${escapeTooltipHtml(`${providerLabel}; ${attentionLabel}; ${confidenceLabel}`)}">
                <span class="insight-ai-badge-icon" aria-hidden="true">
                    <svg viewBox="0 0 20 20" focusable="false">
                        <path d="M7.2 4.1a3.6 3.6 0 0 0-3.6 3.6c0 .8.3 1.6.8 2.2-.3.4-.4.9-.4 1.4 0 1.3.9 2.5 2.2 2.8v.6c0 .8.6 1.4 1.4 1.4h1.1V9.3H7.6a.8.8 0 0 1 0-1.6h1.1V5.1c-.4-.6-.9-1-1.5-1Zm5.6 0c-.6 0-1.1.4-1.5 1v2.6h1.1a.8.8 0 1 1 0 1.6h-1.1v6.8h1.1c.8 0 1.4-.6 1.4-1.4v-.6a2.9 2.9 0 0 0 2.2-2.8c0-.5-.1-1-.4-1.4.5-.6.8-1.4.8-2.2a3.6 3.6 0 0 0-3.6-3.6Z"></path>
                        <path d="M10 6.2h2.1v1.4H10Zm-2.1 4.1H10v1.4H7.9Zm2.1 4.1h2.1v1.4H10Zm4.2-5.1h2.1v1.4h-2.1Z"></path>
                    </svg>
                </span>
                AI
            </span>
            <span class="insight-ai-context" aria-label="${escapeTooltipHtml(`${getSeverityLabel(normalizedSeverity)}. ${getConfidenceLabel(normalizedConfidence)}.`)}">
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
        <span class="insight-action-text">${escapeTooltipHtml(text)}</span>
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

export const renderStoryBanner = (storyBanner, distributionRows, facultyLoadRows, facultyPressureRows, driverRows) => {
    if (!storyBanner) {
        return;
    }

    const totalVisible = distributionRows.reduce((sum, row) => sum + Number(row.count || 0), 0);
    const totalWatchlist = distributionRows
        .filter((row) => row.key !== "low")
        .reduce((sum, row) => sum + Number(row.count || 0), 0);
    const criticalRow = distributionRows.find((row) => row.key === "critical");
    const highRow = distributionRows.find((row) => row.key === "high");
    const leadLoad = facultyLoadRows[0] || null;
    const leadPressure = facultyPressureRows[0] || null;
    const leadDriver = driverRows[0] || null;

    if (!totalVisible) {
        storyBanner.innerHTML = `
            <div class="insight-story-main">
                <p class="insight-story-kicker">Primary Takeaway</p>
                <h2 class="insight-story-title">No institutional insight story is available for the current filters.</h2>
                <p class="insight-story-copy">Adjust the current filters to bring the visible institutional pressure signals back into view.</p>
            </div>
        `;
        return;
    }

    const headline = Number(criticalRow?.count || 0) > 0
        ? "Critical institutional pressure is already visible in the current cohort."
        : Number(highRow?.count || 0) > 0
            ? "the current cohort is carrying a visible high-risk intervention load."
            : totalWatchlist > 0
                ? "the current cohort is showing an early watchlist signal rather than a severe risk spike."
                : "No active watchlist pressure is visible in the current cohort.";
    const headlineCopy = totalWatchlist > 0
        ? `${totalWatchlist} of ${totalVisible} visible students are currently flagged. ${leadLoad ? `${leadLoad.label} holds the heaviest registration load at ${leadLoad.share_pct}%.` : ""}${leadDriver ? ` ${leadDriver.label} is the strongest shared trigger across flagged students.` : ""}`.trim()
        : `All ${totalVisible} visible students currently sit outside the medium and high-risk watchlist bands.`;
    const watchlistValue = totalWatchlist > 0
        ? `${totalWatchlist} of ${totalVisible}`
        : `0 of ${totalVisible}`;
    const watchlistCopy = totalWatchlist > 0
        ? `${Math.round((totalWatchlist / totalVisible) * 100)}% of the visible cohort currently needs closer support attention.`
        : "the current visible cohort is sitting outside the watchlist threshold.";
    const loadValue = leadLoad
        ? `${leadLoad.label} ${leadLoad.share_pct}%`
        : "No load cluster";
    const loadCopy = leadLoad
        ? `${leadLoad.label} currently carries ${leadLoad.registrations} registrations in scope, making it the clearest operational load centre.`
        : "No faculty load concentration is visible in the current filters.";
    const driverModuleCount = Number(leadDriver?.label.match(/\d+/)?.[0] || 0);

const driverValue = leadDriver
    ? `${leadDriver.count} students carried ${driverModuleCount} module${driverModuleCount !== 1 ? "s" : ""}`
    : leadPressure
        ? `${leadPressure.label} ${leadPressure.total}`
        : "No pressure lead";
    const driverCopy = leadDriver
        ? `${leadDriver.label} appears in ${leadDriver.count} flagged student records and should shape the next intervention cycle.`
        : leadPressure
            ? `${leadPressure.label} currently holds the largest flagged-student queue in the visible cohort.`
            : "No recurring intervention pattern is visible in the current filters.";

    storyBanner.innerHTML = `
        <div class="insight-story-main">
            <p class="insight-story-kicker">Primary Takeaway</p>
            <h2 class="insight-story-title">${escapeTooltipHtml(headline)}</h2>
            <p class="insight-story-copy">${escapeTooltipHtml(headlineCopy)}</p>
        </div>
        <div class="insight-story-grid">
            <article class="insight-story-pill">
                <p class="insight-story-pill-label">Watchlist</p>
                <p class="insight-story-pill-value">${escapeTooltipHtml(watchlistValue)}</p>
                <p class="insight-story-pill-copy">${escapeTooltipHtml(watchlistCopy)}</p>
            </article>
            <article class="insight-story-pill">
                <p class="insight-story-pill-label">Load Centre</p>
                <p class="insight-story-pill-value">${escapeTooltipHtml(loadValue)}</p>
                <p class="insight-story-pill-copy">${escapeTooltipHtml(loadCopy)}</p>
            </article>
            <article class="insight-story-pill">
                <p class="insight-story-pill-label">Lead Trigger</p>
                <p class="insight-story-pill-value">${escapeTooltipHtml(driverValue)}</p>
                <p class="insight-story-pill-copy">${escapeTooltipHtml(driverCopy)}</p>
            </article>
        </div>
    `;
};

export const buildDistributionOverviewNarrative = (rows) => {
    const totalVisible = rows.reduce((sum, row) => sum + Number(row.count || 0), 0);
    const totalWatchlist = rows.filter((row) => row.key !== "low").reduce((sum, row) => sum + Number(row.count || 0), 0);
    const criticalRow = rows.find((row) => row.key === "critical");
    const highRow = rows.find((row) => row.key === "high");

    return {
        insight: Number(criticalRow?.count || 0) > 0
            ? `${criticalRow.count} student${criticalRow.count !== 1 ? "s are" : " is"} already sitting in the critical institutional-risk band.`
            : Number(highRow?.count || 0) > 0
                ? `${highRow.count} student${highRow.count !== 1 ? "s are" : " is"} already in the high-risk band of the visible cohort.`
                : totalWatchlist > 0
                    ? `${totalWatchlist} of ${totalVisible} visible students are on the watchlist, but the pressure is still concentrated below the most severe band.`
                    : "No institutional risk distribution insight is available for the current filters.",
        action: totalWatchlist > 0
            ? "the band view gives the fastest executive read on whether the current cohort pressure is mainly preventive work or urgent intervention."
            : "Adjust the current filters to bring the institutional risk distribution back into view.",
    };
};

export const initialiseDistributionNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "distribution", buildDistributionOverviewNarrative(rows));

    if (elements.distributionCopy) {
        elements.distributionCopy.innerHTML = `
            <span>${escapeTooltipHtml(narrative.insight)}</span>
            <span class="insight-subtle-note">Counts reflect module-level risk signals per student within each band.</span>
        `.trim();
    }

    setHintMarkup(elements.distributionHints, []);
    setActionText(elements.distributionNote, narrative.action, {
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

export const buildFacultyLoadOverviewNarrative = (rows) => {
    const leadRow = rows[0] || null;
    const secondRow = rows[1] || null;

    return {
        insight: leadRow && secondRow
            ? `${leadRow.label} is carrying the heaviest visible registration load, ahead of ${secondRow.label}.`
            : leadRow
                ? `${leadRow.label} is the clearest visible faculty load centre in the current scope.`
                : "No faculty load insight is available for the current filters.",
        action: leadRow
            ? "Use the faculty load ranking to decide where advising, staffing, and support capacity may need to stretch first."
            : "Adjust the current filters to bring faculty load concentration back into view.",
    };
};

export const initialiseFacultyLoadNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "faculty_load", buildFacultyLoadOverviewNarrative(rows));

    setElementText(elements.facultyLoadCopy, narrative.insight);
    setHintMarkup(elements.facultyLoadHints, []);
    setActionText(elements.facultyLoadNote, narrative.action, {
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

export const buildFacultyPressureOverviewNarrative = (rows) => {
    const leadRow = rows[0] || null;

    return {
        insight: leadRow
            ? `${leadRow.label} currently holds the largest flagged-student queue in the visible cohort.`
            : "No faculty pressure insight is available for the current filters.",
        action: leadRow
            ? "Keep the high-risk and medium-risk mix in one view so the next support queue is easier to prioritise."
            : "Adjust the current filters to bring faculty pressure back into view.",
    };
};

export const initialiseFacultyPressureNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "faculty_pressure", buildFacultyPressureOverviewNarrative(rows));

    setElementText(elements.facultyPressureCopy, narrative.insight);
    setHintMarkup(elements.facultyPressureHints, []);
    setActionText(elements.facultyPressureNote, narrative.action, {
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

export const buildDriversOverviewNarrative = (rows) => {
    const leadRow = rows[0] || null;
    const secondRow = rows[1] || null;

    return {
        insight: leadRow && secondRow
            ? `${leadRow.label} is the strongest recurring watchlist trigger, ahead of ${secondRow.label}.`
            : leadRow
                ? `${leadRow.label} is the clearest recurring trigger in the current intervention queue.`
                : "No driver insight is available for the current filters.",
        action: leadRow
            ? "Start institutional support planning with the lead trigger before moving into student-level follow-up."
            : "Adjust the current filters to bring shared watchlist drivers back into view.",
    };
};

export const initialiseDriversNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "drivers", buildDriversOverviewNarrative(rows));

    setElementText(elements.driversCopy, narrative.insight);
    setHintMarkup(elements.driversHints, []);
    setActionText(elements.driversNote, narrative.action, {
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};
