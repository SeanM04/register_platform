import { escapeTooltipHtml, formatChartLabel } from "./shared.js";

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
        <span class="risk-chart-hint${hint.kind ? ` is-${hint.kind}` : ""}">
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
        <span class="risk-ai-badge-group">
            <span class="risk-ai-badge is-${normalizedSeverity}" title="${escapeTooltipHtml(`${providerLabel}; ${attentionLabel}; ${confidenceLabel}`)}" aria-label="${escapeTooltipHtml(`${providerLabel}; ${attentionLabel}; ${confidenceLabel}`)}">
                <span class="risk-ai-badge-icon" aria-hidden="true">
                    <svg viewBox="0 0 20 20" focusable="false">
                        <path d="M7.2 4.1a3.6 3.6 0 0 0-3.6 3.6c0 .8.3 1.6.8 2.2-.3.4-.4.9-.4 1.4 0 1.3.9 2.5 2.2 2.8v.6c0 .8.6 1.4 1.4 1.4h1.1V9.3H7.6a.8.8 0 0 1 0-1.6h1.1V5.1c-.4-.6-.9-1-1.5-1Zm5.6 0c-.6 0-1.1.4-1.5 1v2.6h1.1a.8.8 0 1 1 0 1.6h-1.1v6.8h1.1c.8 0 1.4-.6 1.4-1.4v-.6a2.9 2.9 0 0 0 2.2-2.8c0-.5-.1-1-.4-1.4.5-.6.8-1.4.8-2.2a3.6 3.6 0 0 0-3.6-3.6Z"></path>
                        <path d="M10 6.2h2.1v1.4H10Zm-2.1 4.1H10v1.4H7.9Zm2.1 4.1h2.1v1.4H10Zm4.2-5.1h2.1v1.4h-2.1Z"></path>
                    </svg>
                </span>
                AI
            </span>
            <span class="risk-ai-context" aria-label="${escapeTooltipHtml(`${getSeverityLabel(normalizedSeverity)}. ${getConfidenceLabel(normalizedConfidence)}.`)}">
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
        <span class="risk-action-text">${escapeTooltipHtml(text)}</span>
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

export const renderStoryBanner = (storyBanner, distributionRows, driverRows, levelRows, programmeRows) => {
    if (!storyBanner) {
        return;
    }

    const totalVisible = distributionRows.reduce((sum, row) => sum + Number(row.count || 0), 0);
    const totalWatchlist = distributionRows
        .filter((row) => row.key !== "low")
        .reduce((sum, row) => sum + Number(row.count || 0), 0);
    const criticalRow = distributionRows.find((row) => row.key === "critical");
    const highRow = distributionRows.find((row) => row.key === "high");
    const leadDriver = driverRows[0] || null;
    const leadLevel = levelRows[0] || null;
    const leadProgramme = programmeRows[0] || null;

    if (!totalVisible) {
        storyBanner.innerHTML = `
            <div class="risk-story-main">
                <h2 class="risk-story-title">No risk story is available for the current filters.</h2>
                <p class="risk-story-copy">Adjust the current filters to bring the cohort watchlist & its intervention priorities back into view.</p>
            </div>
        `;
        return;
    }

    const headline = Number(criticalRow?.count || 0) > 0
        ? "Critical risk cases are already present in the current cohort."
        : Number(highRow?.count || 0) > 0
            ? "High-risk students are shaping the current watchlist."
            : totalWatchlist > 0
                ? "The current watchlist is still in an early-intervention range."
                : "No at-risk students are visible in the current cohort.";
    const headlineCopy = totalWatchlist > 0
        ? `${totalWatchlist} of ${totalVisible} visible students are currently on the watchlist.${leadDriver ? ` ${leadDriver.label} is the strongest shared driver.` : ""}${leadLevel ? ` ${leadLevel.level} carries the largest flagged level cluster.` : ""}`
        : `All ${totalVisible} visible students currently sit outside the medium and high-risk bands in the active filter view.`;
    const watchlistValue = totalWatchlist > 0
        ? `${totalWatchlist} of ${totalVisible}`
        : `0 of ${totalVisible}`;
    const watchlistCopy = totalWatchlist > 0
        ? `${Math.round((totalWatchlist / totalVisible) * 100)}% of the visible cohort currently needs some level of intervention attention.`
        : "The visible cohort is currently sitting outside the watchlist threshold.";
    const driverValue = leadDriver
        ? `${leadDriver.label} ${leadDriver.count}`
        : "No shared driver";
    const driverCopy = leadDriver
        ? `${leadDriver.count} flagged student${leadDriver.count !== 1 ? "s" : ""} currently show this driver in the watchlist mix.`
        : "The current filters do not expose a shared watchlist driver pattern.";
    const focusValue = leadProgramme
        ? `${formatChartLabel(leadProgramme.programme, 18)} ${leadProgramme.total}`
        : leadLevel
            ? `${leadLevel.level} ${leadLevel.total}`
            : "No clear focus";
    const focusCopy = leadProgramme
        ? `${formatChartLabel(leadProgramme.programme, 26)} is the biggest programme concentration on the watchlist.`
        : leadLevel
            ? `${leadLevel.level} is the biggest academic-level pressure point in the current scope.`
            : "There is no visible concentration point in the current watchlist.";

    storyBanner.innerHTML = `
        <div class="risk-story-main">
            <h2 class="risk-story-title">${escapeTooltipHtml(headline)}</h2>
            <p class="risk-story-copy">${escapeTooltipHtml(headlineCopy)}</p>
        </div>
        <div class="risk-story-grid">
            <article class="risk-story-pill">
                <p class="risk-story-pill-label">Watchlist Size</p>
                <p class="risk-story-pill-value">${escapeTooltipHtml(watchlistValue)}</p>
                <p class="risk-story-pill-copy">${escapeTooltipHtml(watchlistCopy)}</p>
            </article>
            <article class="risk-story-pill">
                <p class="risk-story-pill-label">Lead Driver</p>
                <p class="risk-story-pill-value">${escapeTooltipHtml(driverValue)}</p>
                <p class="risk-story-pill-copy">${escapeTooltipHtml(driverCopy)}</p>
            </article>
            <article class="risk-story-pill">
                <p class="risk-story-pill-label">Focus Area</p>
                <p class="risk-story-pill-value">${escapeTooltipHtml(focusValue)}</p>
                <p class="risk-story-pill-copy">${escapeTooltipHtml(focusCopy)}</p>
            </article>
        </div>
    `;
};

export const buildDistributionOverviewNarrative = (rows) => {
    const criticalRow = rows.find((row) => row.key === "critical");
    const highRow = rows.find((row) => row.key === "high");
    const totalVisible = rows.reduce((sum, row) => sum + Number(row.count || 0), 0);
    const totalWatchlist = rows.filter((row) => row.key !== "low").reduce((sum, row) => sum + Number(row.count || 0), 0);

    return {
        insight: Number(criticalRow?.count || 0) > 0
            ? `${criticalRow.count} student${criticalRow.count !== 1 ? "s" : ""} are already sitting in the critical band of the current cohort.`
            : Number(highRow?.count || 0) > 0
                ? `The current watchlist is anchored by ${highRow.count} high-risk student${highRow.count !== 1 ? "s" : ""} who need the fastest response.`
                : totalWatchlist > 0
                    ? `${totalWatchlist} of ${totalVisible} visible students are on the watchlist, but the pressure is still mostly outside the highest-severity band.`
                    : "No risk distribution insight is available for the current filters.",
        action: totalWatchlist > 0
            ? "The band chart gives the quickest read on whether the current risk story is mostly preventive work or urgent intervention."
            : "Adjust the current filters to bring the risk distribution story back into view.",
    };
};

export const initialiseDistributionNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "distribution", buildDistributionOverviewNarrative(rows));

   if (elements.distributionCopy) {
    const noteText = "Counts reflect module-level risk signals per student within each band.";
    const insightText = String(narrative.insight || "").trim();

    elements.distributionCopy.innerHTML = `
        <span>${escapeTooltipHtml(insightText)}</span>
        <span class="risk-subtle-note">${escapeTooltipHtml(noteText)}</span>
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

export const buildDriversOverviewNarrative = (rows) => {
    const leadRow = rows[0] || null;
    const secondRow = rows[1] || null;

    return {
        insight: leadRow && secondRow
            ? `${leadRow.label} is the strongest shared watchlist driver, ahead of ${secondRow.label}.`
            : leadRow
                ? `${leadRow.label} is the clearest visible risk driver in the current watchlist.`
                : "No risk-driver insight is available for the current filters.",
        action: leadRow
            ? "This ranking separates the most common intervention trigger from the less common supporting drivers."
            : "Adjust the current filters to bring the risk-driver story back into view.",
    };
};

export const initialiseDriversNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "drivers", buildDriversOverviewNarrative(rows));

    setElementText(elements.driversCopy, narrative.insight);
    setHintMarkup(elements.driversHints, [
        { label: "Hover bars for counts", kind: "inspect" },
        { label: "Compare intervention triggers", kind: "support" },
    ]);
    setActionText(elements.driversNote, narrative.action, {
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

export const buildLevelsOverviewNarrative = (rows) => {
    const leadRow = rows[0] || null;

    return {
        insight: leadRow
            ? `${leadRow.level} currently holds the largest visible at-risk cluster in the current scope.`
            : "No academic-level concentration insight is available for the current filters.",
        action: leadRow
            ? "The stacked level view shows whether pressure is building as medium-risk cases or already hardening into high-risk cases."
            : "Adjust the current filters to bring academic-level pressure back into view.",
    };
};

export const initialiseLevelsNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "levels", buildLevelsOverviewNarrative(rows));

    setElementText(elements.levelsCopy, narrative.insight);
    setHintMarkup(elements.levelsHints, [
        { label: "Hover stacks for counts", kind: "inspect" },
        { label: "Compare medium vs high pressure", kind: "support" },
    ]);
    setActionText(elements.levelsNote, narrative.action, {
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

export const buildProgrammesOverviewNarrative = (rows) => {
    const leadRow = rows[0] || null;

    return {
        insight: leadRow
            ? `${formatChartLabel(leadRow.programme, 28)} currently carries the largest flagged programme cluster.`
            : "No programme concentration insight is available for the current filters.",
        action: leadRow
            ? "This chart keeps programme concentration & severity mix in the same view so intervention planning stays operational."
            : "Adjust the current filters to bring programme concentration back into view.",
    };
};

export const initialiseProgrammesNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "programmes", buildProgrammesOverviewNarrative(rows));

    setElementText(elements.programmesCopy, narrative.insight);
    setHintMarkup(elements.programmesHints, [
        { label: "Hover columns for full labels", kind: "inspect" },
        { label: "Compare concentration & severity", kind: "support" },
    ]);
    setActionText(elements.programmesNote, narrative.action, {
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};
