import { escapeTooltipHtml, formatChartLabel } from "./shared.js";

const formatStoryProgrammeName = (value, maxLength = 22) => {
    const cleanedValue = String(value || "")
        .replace(/^(Bachelor|Master(?:s)?) Of\s+/i, "")
        .replace(/\s+Honours Degree$/i, "")
        .trim();
    return formatChartLabel(cleanedValue || value, maxLength);
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

    element.innerHTML = hints.map((hint) => `
        <span class="demographic-chart-hint${hint.kind ? ` is-${hint.kind}` : ""}">
            ${escapeTooltipHtml(hint.label)}
        </span>
    `).join("").trim();
};

const setMetaMarkup = (element, items) => {
    if (!element) {
        return;
    }

    element.innerHTML = items
        .filter((item) => item && item.label && item.value !== undefined && item.value !== null && item.value !== "")
        .map((item) => `
            <span class="demographic-origin-map-pill">
                <span class="demographic-origin-map-pill-label">${escapeTooltipHtml(item.label)}</span>
                <span class="demographic-origin-map-pill-value">${escapeTooltipHtml(item.value)}</span>
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
        <span class="demographic-ai-badge-group">
            <span class="demographic-ai-badge is-${normalizedSeverity}" title="${escapeTooltipHtml(`${providerLabel}; ${attentionLabel}; ${confidenceLabel}`)}" aria-label="${escapeTooltipHtml(`${providerLabel}; ${attentionLabel}; ${confidenceLabel}`)}">
                <span class="demographic-ai-badge-icon" aria-hidden="true">
                    <svg viewBox="0 0 20 20" focusable="false">
                        <path d="M7.2 4.1a3.6 3.6 0 0 0-3.6 3.6c0 .8.3 1.6.8 2.2-.3.4-.4.9-.4 1.4 0 1.3.9 2.5 2.2 2.8v.6c0 .8.6 1.4 1.4 1.4h1.1V9.3H7.6a.8.8 0 0 1 0-1.6h1.1V5.1c-.4-.6-.9-1-1.5-1Zm5.6 0c-.6 0-1.1.4-1.5 1v2.6h1.1a.8.8 0 1 1 0 1.6h-1.1v6.8h1.1c.8 0 1.4-.6 1.4-1.4v-.6a2.9 2.9 0 0 0 2.2-2.8c0-.5-.1-1-.4-1.4.5-.6.8-1.4.8-2.2a3.6 3.6 0 0 0-3.6-3.6Z"></path>
                        <path d="M10 6.2h2.1v1.4H10Zm-2.1 4.1H10v1.4H7.9Zm2.1 4.1h2.1v1.4H10Zm4.2-5.1h2.1v1.4h-2.1Z"></path>
                    </svg>
                </span>
                AI
            </span>
            <span class="demographic-ai-context" aria-label="${escapeTooltipHtml(`${getSeverityLabel(normalizedSeverity)}. ${getConfidenceLabel(normalizedConfidence)}.`)}">
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
        <span class="demographic-action-text">${escapeTooltipHtml(text)}</span>
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

const parseSharePercentage = (value) => {
    const normalizedValue = String(value || "").replace("%", "").trim();
    const numericValue = Number(normalizedValue);
    return Number.isFinite(numericValue) ? numericValue : 0;
};

export const renderStoryBanner = (storyBanner, genderRows, locationRows, programmeRows) => {
    if (!storyBanner) {
        return;
    }

    const visibleGenderRows = genderRows.filter(
        (row) => Number(row.count || 0) > 0 && String(row.label || "").trim().toLowerCase() !== "unspecified",
    );
    const visibleLocationRows = locationRows.filter(
        (row) => Number(row.count || 0) > 0 && String(row.place || "").trim().toLowerCase() !== "unspecified",
    );
    if (!visibleGenderRows.length && !visibleLocationRows.length && !programmeRows.length) {
        storyBanner.innerHTML = `
            <div class="demographic-story-main">
                <p class="demographic-story-kicker">What To Notice</p>
                <h2 class="demographic-story-title">No demographic story is available for the current filters.</h2>
                <p class="demographic-story-copy">Adjust the current search or top filters to bring the visible cohort mix back into view.</p>
            </div>
        `;
        return;
    }

    const sortedGenderRows = [...visibleGenderRows].sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
    const leadGender = sortedGenderRows[0] || null;
    const secondGender = sortedGenderRows[1] || null;
    const leadLocation = visibleLocationRows[0] || null;
    const secondLocation = visibleLocationRows[1] || null;
    const leadProgramme = [...programmeRows].sort((left, right) => right.total - left.total || left.programme.localeCompare(right.programme))[0] || null;
    const leadLocationShare = parseSharePercentage(leadLocation?.share);
    const secondLocationShare = parseSharePercentage(secondLocation?.share);
    const leadGenderShare = parseSharePercentage(leadGender?.share);
    const secondGenderShare = parseSharePercentage(secondGender?.share);
    const topTwoLocationShare = leadLocationShare + secondLocationShare;
    const genderGap = leadGender && secondGender ? Math.abs(leadGenderShare - secondGenderShare) : 0;
    const headline = leadLocation && secondLocation
        ? leadLocationShare >= 30
            ? `${leadLocation.place} is the dominant visible origin point in the current cohort.`
            : topTwoLocationShare >= 45
                ? `${leadLocation.place} and ${secondLocation.place} anchor nearly half of the visible cohort.`
                : "Birth-location representation is visible, but not dominated by a single source."
        : leadLocation
            ? `${leadLocation.place} is the clearest visible origin point in the current cohort.`
            : leadGender
                ? `${leadGender.label} currently leads the visible cohort mix.`
                : "The current filters expose a narrow demographic slice.";
    const headlineCopy = leadLocation && secondLocation
        ? `${leadLocation.place} represents ${leadLocation.share} of visible students, with ${secondLocation.place} following at ${secondLocation.share}. ${leadGender && secondGender ? `${leadGender.label}/${secondGender.label} balance currently sits at ${leadGender.share} to ${secondGender.share}.` : ""}`.trim()
        : leadLocation
            ? `${leadLocation.place} represents ${leadLocation.share} of the visible cohort in the current filter view.`
            : leadGender && secondGender
                ? `${leadGender.label} accounts for ${leadGender.share}, with ${secondGender.label} following at ${secondGender.share}.`
                : leadGender
                    ? `${leadGender.label} accounts for ${leadGender.share} of the visible cohort.`
                    : "No gender mix was available in the current filtered cohort.";
    const concentrationValue = leadLocation
        ? `${leadLocation.place} ${leadLocation.share}`
        : "No concentration";
    const concentrationCopy = leadLocation && secondLocation
        ? `${leadLocation.place} leads ${secondLocation.place} by ${Math.max(leadLocationShare - secondLocationShare, 0)} percentage points in the visible location mix.`
        : leadLocation
            ? `${leadLocation.place} is the largest visible birth-location group in the current cohort.`
            : "Birth-location concentration is not available for the active filters.";
    const cohortValue = leadGender
        ? `${leadGender.label} ${leadGender.share}`
        : "No cohort lead";
    const cohortCopy = leadGender && secondGender
        ? genderGap <= 5
            ? `${leadGender.label} and ${secondGender.label} remain close to balanced in the visible cohort.`
            : `${leadGender.label} leads ${secondGender.label} by ${genderGap} percentage points in the visible cohort.`
        : leadGender
            ? `${leadGender.label} is the only visible gender segment in the current filtered slice.`
            : "Cohort balance is not available for the active filters.";
    const programmeValue = leadProgramme
        ? `${formatStoryProgrammeName(leadProgramme.programme, 18)} ${leadProgramme.total}`
        : "No programme lead";
    const programmeCopy = leadProgramme
        ? `${formatStoryProgrammeName(leadProgramme.programme, 24)} is the programme anchor for this slice, carrying ${leadProgramme.total} visible students.`
        : "Programme mix insight is not available for the active filters.";

    storyBanner.innerHTML = `
        <div class="demographic-story-main">
            <p class="demographic-story-kicker">Primary Takeaway</p>
            <h2 class="demographic-story-title">${escapeTooltipHtml(headline)}</h2>
            <p class="demographic-story-copy">${escapeTooltipHtml(headlineCopy)}</p>
        </div>
        <div class="demographic-story-grid">
            <article class="demographic-story-pill">
                <p class="demographic-story-pill-label">Concentration</p>
                <p class="demographic-story-pill-value">${escapeTooltipHtml(concentrationValue)}</p>
                <p class="demographic-story-pill-copy">${escapeTooltipHtml(concentrationCopy)}</p>
            </article>
            <article class="demographic-story-pill">
                <p class="demographic-story-pill-label">Cohort Balance</p>
                <p class="demographic-story-pill-value">${escapeTooltipHtml(cohortValue)}</p>
                <p class="demographic-story-pill-copy">${escapeTooltipHtml(cohortCopy)}</p>
            </article>
            <article class="demographic-story-pill">
                <p class="demographic-story-pill-label">Programme Anchor</p>
                <p class="demographic-story-pill-value">${escapeTooltipHtml(programmeValue)}</p>
                <p class="demographic-story-pill-copy">${escapeTooltipHtml(programmeCopy)}</p>
            </article>
        </div>
    `;
};

export const buildGenderOverviewNarrative = (rows) => {
    const visibleRows = rows.filter((row) => Number(row.count || 0) > 0);
    const sortedRows = [...visibleRows].sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
    const leadRow = sortedRows[0] || null;
    const secondRow = sortedRows[1] || null;

    return {
        insight: leadRow && secondRow
            ? `${leadRow.label} and ${secondRow.label} define most of the visible cohort, with ${leadRow.label} slightly ahead at ${leadRow.share}.`
            : leadRow
                ? `${leadRow.label} currently accounts for ${leadRow.share} of the visible cohort.`
                : "No gender distribution insight is available for the current filters.",
        action: leadRow
            ? "The donut view keeps the balance question simple first, then the tooltip gives the exact student counts and shares."
            : "Adjust the current filters to bring the gender cohort story back into view.",
    };
};

export const initialiseGenderNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "gender", buildGenderOverviewNarrative(rows));

    setElementText(elements.genderCopy, narrative.insight);
    setHintMarkup(elements.genderHints, [
        { label: "Hover or tap for details", kind: "inspect" },
    ]);
    setActionText(elements.genderNote, narrative.action, {
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

export const buildLocationOverviewNarrative = (rows) => {
    const leadRow = rows[0] || null;
    const secondRow = rows[1] || null;

    return {
        insight: leadRow && secondRow
            ? `${leadRow.place} currently leads the visible birth-location distribution, ahead of ${secondRow.place}.`
            : leadRow
                ? `${leadRow.place} is the clearest location signal in the filtered cohort.`
                : "No birth-location insight is available for the current filters.",
        action: leadRow
            ? "A ranked column chart makes birthplace concentration easy to compare first. Click a column to drill into that location's gender split."
            : "Adjust the current filters to bring the birth-location story back into view.",
    };
};

export const initialiseLocationNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "location", buildLocationOverviewNarrative(rows));

    setElementText(elements.locationCopy, narrative.insight);
    setHintMarkup(elements.locationHints, [
        { label: "Hover or tap columns for values", kind: "inspect" },
        { label: "Click a column to see gender split", kind: "support" },
        { label: "Compare share and count together", kind: "support" },
    ]);
    setActionText(elements.locationNote, narrative.action, {
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

export const buildLocationMixOverviewNarrative = (rows) => {
    const leadRow = rows[0] || null;
    const dominantEntry = leadRow
        ? [
            { label: "Male", count: leadRow.male },
            { label: "Female", count: leadRow.female },
            { label: "Unspecified", count: leadRow.unspecified },
        ].sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))[0]
        : null;

    return {
        insight: leadRow && dominantEntry
            ? `${leadRow.place} is still the strongest visible location cluster, and ${dominantEntry.label.toLowerCase()} students drive the largest share of that location's cohort.`
            : "No location-to-gender mix insight is available for the current filters.",
        action: leadRow
            ? "The heatmap makes concentrated location-by-gender pockets visible in one glance, which is much harder to read from separate totals."
            : "Adjust the current filters to bring the birth-location mix back into view.",
    };
};

export const initialiseLocationMixNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "location_mix", buildLocationMixOverviewNarrative(rows));

    setElementText(elements.locationMixCopy, narrative.insight);
    setHintMarkup(elements.locationMixHints, [
        { label: "Hover or tap cells for details", kind: "inspect" },
        { label: "Darker cells mean larger cohorts", kind: "support" },
    ]);
    setActionText(elements.locationMixNote, narrative.action, {
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};

export const buildOriginMapOverviewNarrative = (rows, mapMeta = {}) => {
    const leadRow = rows[0] || null;
    const secondRow = rows[1] || null;
    const hasMappedCoverage = Number(mapMeta.mapped_students || 0) > 0;
    const unmappedPreview = Array.isArray(mapMeta.unmapped_labels) && mapMeta.unmapped_labels.length
        ? mapMeta.unmapped_labels.join(", ")
        : "";

    return {
        insight: leadRow && secondRow
            ? `${leadRow.place} anchors the strongest mapped origin cluster, with ${secondRow.place} the next clearest visible source on the map.`
            : leadRow
                ? `${leadRow.place} is the clearest mapped origin signal in the visible cohort.`
                : "No mappable birth-location insight is available for the current filters.",
        action: hasMappedCoverage
            ? `${mapMeta.mapped_students} visible students are currently represented on an interactive Zimbabwe map. The markers use approximate district or city anchors from the recorded birth-location labels.${mapMeta.unmapped_students ? ` ${mapMeta.unmapped_students} students remain off-map because those labels do not yet have a coordinate match${unmappedPreview ? `, including ${unmappedPreview}` : ""}.` : ""}`
            : "Adjust the current filters to bring mapped birth-location coverage back into view.",
    };
};

export const initialiseOriginMapNarrative = (elements, rows, mapMeta = {}, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "origin_map", buildOriginMapOverviewNarrative(rows, mapMeta));

    setElementText(elements.originMapCopy, narrative.insight);
    setHintMarkup(elements.originMapHints, [
        { label: "Click markers for details", kind: "inspect" },
        { label: "Bubble size shows student count", kind: "support" },
        { label: "Pan and zoom the map", kind: "support" },
        { label: "Markers use approximate birth-location anchors", kind: "support" },
    ]);
    setActionText(elements.originMapNote, narrative.action, {
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
    setMetaMarkup(elements.originMapMeta, [
        { label: "Mapped students", value: mapMeta.mapped_students || 0 },
        { label: "Mapped places", value: mapMeta.mapped_places || 0 },
        ...(mapMeta.unmapped_students ? [{ label: "Off-map students", value: mapMeta.unmapped_students }] : []),
    ]);
};

export const buildProgrammeOverviewNarrative = (rows) => {
    const sortedRows = [...rows].sort((left, right) => right.total - left.total || left.programme.localeCompare(right.programme));
    const leadRow = sortedRows[0] || null;

    return {
        insight: leadRow
            ? `${formatStoryProgrammeName(leadRow.programme, 24)} currently carries the largest visible programme cohort, and the stacked bars show how the gender mix changes by programme.`
            : "No programme-mix insight is available for the current filters.",
        action: leadRow
            ? "The stacked view keeps total size and gender composition visible at the same time, so the programme mix stays readable in one glance."
            : "Adjust the current filters to bring the programme mix story back into view.",
    };
};

export const initialiseProgrammeNarrative = (elements, rows, cardNarratives = {}, flags = {}) => {
    const narrative = getOverviewCardNarrative(cardNarratives, "programme", buildProgrammeOverviewNarrative(rows));

    setElementText(elements.programmeCopy, narrative.insight);
    setHintMarkup(elements.programmeHints, [
        { label: "Hover or tap stacks for details", kind: "inspect" },
        { label: "Compare segment balance across programmes", kind: "support" },
    ]);
    setActionText(elements.programmeNote, narrative.action, {
        showAiBadge: flags.overviewNarrativesAreAi,
        source: flags.overviewNarrativeSource,
        severity: narrative.severity,
        confidence: narrative.confidence,
    });
};
