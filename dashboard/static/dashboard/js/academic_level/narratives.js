import {
    PASS_RATE_TARGET,
    VALID_CARD_CONFIDENCES,
    VALID_CARD_SEVERITIES,
    escapeTooltipHtml,
    formatStoryProgrammeName,
    numberFormatter,
} from "./shared.js";

export const getStrongestAndWeakestLevels = (rows) => {
    if (!rows.length) {
        return { strongest: null, weakest: null };
    }

    const sortedRows = [...rows].sort(
        (left, right) =>
            right.pass_rate_value - left.pass_rate_value
            || right.average_mark - left.average_mark
            || left.level.localeCompare(right.level),
    );

    return {
        strongest: sortedRows[0],
        weakest: sortedRows[sortedRows.length - 1],
    };
};

export const renderStoryBanner = (storyBanner, rows, genderData, programmeData) => {
    if (!storyBanner) {
        return;
    }

    if (!rows.length) {
        storyBanner.innerHTML = `
            <div class="level-story-main">
                <p class="level-story-kicker">What To Notice</p>
                <h2 class="level-story-title">No academic-level story is available for the current filters.</h2>
                <p class="level-story-copy">Adjust the current search or filters to bring the pass, cohort, and enrolment narrative back into view.</p>
            </div>
        `;
        return;
    }

    const { strongest, weakest } = getStrongestAndWeakestLevels(rows);
    const belowTargetRows = rows.filter((row) => Number(row.pass_rate_value || 0) < PASS_RATE_TARGET);
    const genderLeaders = genderData
        .filter((row) => Number(row.students || 0) > 0)
        .sort((left, right) => right.student_share_value - left.student_share_value);
    const leadGender = genderLeaders[0] || null;
    const secondGender = genderLeaders[1] || null;
    const topProgramme = [...programmeData].sort(
        (left, right) => right.registrations - left.registrations || left.programme.localeCompare(right.programme),
    )[0] || null;
    const passGap = strongest && weakest ? strongest.pass_rate_value - weakest.pass_rate_value : 0;
    const averagePass = Math.round(
        rows.reduce((total, row) => total + Number(row.pass_rate_value || 0), 0) / Math.max(rows.length, 1),
    );
    const headline = passGap >= 6
        ? `Pass performance spreads by ${passGap} points across the academic journey.`
        : "Pass performance stays relatively tight across the academic journey.";
    const headlineCopy = belowTargetRows.length
        ? `${belowTargetRows.length} of ${rows.length} levels are still below the ${PASS_RATE_TARGET}% pass target, with ${weakest.level} currently the clearest pressure point at ${weakest.pass_rate}.`
        : `All ${rows.length} academic levels are currently at or above the ${PASS_RATE_TARGET}% pass target, with an average pass rate of ${averagePass}%.`;
    const targetWatchValue = belowTargetRows.length
        ? `${belowTargetRows.length} below target`
        : "All on target";
    const targetWatchCopy = belowTargetRows.length
        ? `${belowTargetRows[0].level} is the first level to review at ${belowTargetRows[0].pass_rate}.`
        : `${strongest.level} currently leads the trend at ${strongest.pass_rate}.`;
    const genderGap = leadGender && secondGender
        ? Math.abs((leadGender.student_share_value || 0) - (secondGender.student_share_value || 0))
        : 0;
    const cohortValue = leadGender
        ? `${leadGender.label} ${leadGender.student_share}`
        : "No gender split";
    const cohortCopy = leadGender && secondGender
        ? genderGap <= 5
            ? `${leadGender.label} and ${secondGender.label} are close to balanced in the current cohort.`
            : `${leadGender.label} leads ${secondGender.label} by ${genderGap} percentage points in the current cohort.`
        : "Only one gender segment is represented in the current cohort.";
    const loadValue = topProgramme
        ? `${numberFormatter.format(topProgramme.registrations)} regs`
        : "No load leader";
    const loadCopy = topProgramme
        ? `${formatStoryProgrammeName(topProgramme.programme)} carries the largest current programme load.`
        : "Programme load insight is not available for the current filters.";

    storyBanner.innerHTML = `
        <div class="level-story-main">
            <p class="level-story-kicker">What To Notice</p>
            <h2 class="level-story-title">${escapeTooltipHtml(headline)}</h2>
            <p class="level-story-copy">${escapeTooltipHtml(headlineCopy)}</p>
        </div>
        <div class="level-story-grid">
            <article class="level-story-pill">
                <p class="level-story-pill-label">Target Watch</p>
                <p class="level-story-pill-value">${escapeTooltipHtml(targetWatchValue)}</p>
                <p class="level-story-pill-copy">${escapeTooltipHtml(targetWatchCopy)}</p>
            </article>
            <article class="level-story-pill">
                <p class="level-story-pill-label">Cohort Balance</p>
                <p class="level-story-pill-value">${escapeTooltipHtml(cohortValue)}</p>
                <p class="level-story-pill-copy">${escapeTooltipHtml(cohortCopy)}</p>
            </article>
            <article class="level-story-pill">
                <p class="level-story-pill-label">Load Leader</p>
                <p class="level-story-pill-value">${escapeTooltipHtml(loadValue)}</p>
                <p class="level-story-pill-copy">${escapeTooltipHtml(loadCopy)}</p>
            </article>
        </div>
    `;
};

export const setElementText = (element, text) => {
    if (element) {
        element.textContent = text;
    }
};

export const setHintMarkup = (element, hints) => {
    if (!element) {
        return;
    }

    element.innerHTML = hints.map((hint) => `
        <span class="level-chart-hint${hint.kind ? ` is-${hint.kind}` : ""}">
            ${escapeTooltipHtml(hint.label)}
        </span>
    `).join("").trim();
};

export const setGenderHints = (element) => {
    setHintMarkup(element, [
        { label: "Hover or tap for details", kind: "inspect" },
    ]);
};

export const setTopProgrammeHints = (element, isDetail) => {
    setHintMarkup(element, isDetail ? [
        { label: "Hover or tap bars for values", kind: "inspect" },
        { label: "Use Back to top 5 to compare", kind: "support" },
    ] : [
        { label: "Hover or tap for details", kind: "inspect" },
        { label: "Click a slice to drill down", kind: "drill" },
    ]);
};

export const setPassTrendHints = (element, isDetail) => {
    setHintMarkup(element, isDetail ? [
        { label: "Hover or tap bars for values", kind: "inspect" },
        { label: "Use Find in table for exact totals", kind: "support" },
    ] : [
        { label: "Hover or tap for details", kind: "inspect" },
        { label: "Click a point or label to drill down", kind: "drill" },
    ]);
};

export const normalizeCardSeverity = (value) => {
    const normalizedValue = String(value || "stable").trim().toLowerCase();
    return VALID_CARD_SEVERITIES.has(normalizedValue) ? normalizedValue : "stable";
};

export const normalizeCardConfidence = (value) => {
    const normalizedValue = String(value || "medium").trim().toLowerCase();
    return VALID_CARD_CONFIDENCES.has(normalizedValue) ? normalizedValue : "medium";
};

export const getSeverityLabel = (severity) => {
    if (severity === "high") {
        return "Priority";
    }
    if (severity === "medium") {
        return "Watch";
    }
    return "Monitor";
};

export const getConfidenceLabel = (confidence) => {
    if (confidence === "high") {
        return "High confidence";
    }
    if (confidence === "low") {
        return "Low confidence";
    }
    return "Medium confidence";
};

export const buildAiBadgeMarkup = (source, severity = "stable", confidence = "medium") => {
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
        <span class="level-ai-badge-group">
            <span class="level-ai-badge is-${normalizedSeverity}" title="${escapeTooltipHtml(`${providerLabel}; ${attentionLabel}; ${confidenceLabel}`)}" aria-label="${escapeTooltipHtml(`${providerLabel}; ${attentionLabel}; ${confidenceLabel}`)}">
                <span class="level-ai-badge-icon" aria-hidden="true">
                    <svg viewBox="0 0 20 20" focusable="false">
                        <path d="M7.2 4.1a3.6 3.6 0 0 0-3.6 3.6c0 .8.3 1.6.8 2.2-.3.4-.4.9-.4 1.4 0 1.3.9 2.5 2.2 2.8v.6c0 .8.6 1.4 1.4 1.4h1.1V9.3H7.6a.8.8 0 0 1 0-1.6h1.1V5.1c-.4-.6-.9-1-1.5-1Zm5.6 0c-.6 0-1.1.4-1.5 1v2.6h1.1a.8.8 0 1 1 0 1.6h-1.1v6.8h1.1c.8 0 1.4-.6 1.4-1.4v-.6a2.9 2.9 0 0 0 2.2-2.8c0-.5-.1-1-.4-1.4.5-.6.8-1.4.8-2.2a3.6 3.6 0 0 0-3.6-3.6Z"></path>
                        <path d="M10 6.2h2.1v1.4H10Zm-2.1 4.1H10v1.4H7.9Zm2.1 4.1h2.1v1.4H10Zm4.2-5.1h2.1v1.4h-2.1Z"></path>
                    </svg>
                </span>
                AI
            </span>
            <span class="level-ai-context" aria-label="${escapeTooltipHtml(`${getSeverityLabel(normalizedSeverity)}. ${getConfidenceLabel(normalizedConfidence)}.`)}">
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
        <span class="level-action-text">${escapeTooltipHtml(text)}</span>
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

export const buildGenderNarrative = (rows) => {
    const visibleRows = rows
        .filter((row) => Number(row.students || 0) > 0 && row.key !== "unspecified")
        .sort((left, right) => right.student_share_value - left.student_share_value);
    if (!visibleRows.length) {
        return {
            insight: "No gender balance insight is available for the current filters.",
            action: "Action: Adjust the current filters to bring the cohort balance story back into view.",
        };
    }

    const leadRow = visibleRows[0];
    const trailingRow = visibleRows[1] || null;
    const representationGap = trailingRow
        ? Math.abs((leadRow.student_share_value || 0) - (trailingRow.student_share_value || 0))
        : 0;
    const byPassRate = [...visibleRows].sort(
        (left, right) => right.pass_rate_value - left.pass_rate_value || left.label.localeCompare(right.label),
    );
    const strongestPass = byPassRate[0];
    const weakestPass = byPassRate[byPassRate.length - 1];
    const passGap = Math.abs((strongestPass?.pass_rate_value || 0) - (weakestPass?.pass_rate_value || 0));

    const insight = trailingRow
        ? representationGap <= 5
            ? `${leadRow.label} and ${trailingRow.label} representation is close to balanced, with ${leadRow.label} slightly ahead at ${leadRow.student_share}.`
            : `${leadRow.label} currently leads the cohort at ${leadRow.student_share}, ${representationGap} points ahead of ${trailingRow.label}.`
        : `${leadRow.label} accounts for ${leadRow.student_share} of the visible cohort in the current filter view.`;
    const action = trailingRow && strongestPass && weakestPass && strongestPass.label !== weakestPass.label && passGap >= 5
        ? `Action: Compare ${weakestPass.label} against ${strongestPass.label} in the tooltip first to see whether the pass-rate gap needs intervention.`
        : "Action: Use the tooltip to confirm whether pass rate and average mark stay aligned across the visible gender groups.";

    return { insight, action };
};

export const buildTopProgrammeOverviewNarrative = (rows) => {
    if (!rows.length) {
        return {
            insight: "No top-enrolment insight is available for the current filters.",
            action: "Action: Adjust the current filters to bring the programme-load story back into view.",
        };
    }

    const totalRegistrations = rows.reduce((total, row) => total + Number(row.registrations || 0), 0);
    const topRow = [...rows].sort(
        (left, right) => right.registrations - left.registrations || left.programme.localeCompare(right.programme),
    )[0];
    const topShare = totalRegistrations ? Math.round((topRow.registrations / totalRegistrations) * 100) : 0;
    const programmeName = formatStoryProgrammeName(topRow.programme);

    const insight = topShare >= 25
        ? `${programmeName} carries ${topShare}% of the top-five enrolment load, so the current intake is concentrated in a small number of programmes.`
        : `${programmeName} leads the top-five view, but enrolment is still relatively spread across the biggest programmes.`;
    const action = `Action: Click ${programmeName} first to see which academic levels are carrying most of that programme's current load.`;

    return { insight, action };
};

export const buildTopProgrammeDetailNarrative = (programme) => {
    if (!programme || !programme.level_breakdown?.length) {
        return {
            insight: "No programme drilldown insight is available for the current selection.",
            action: "Action: Go back to the top-five view and select another programme slice.",
        };
    }

    const highestLoadLevel = [...programme.level_breakdown].sort(
        (left, right) => right.registrations - left.registrations || left.level.localeCompare(right.level),
    )[0];
    const weakestPassLevel = [...programme.level_breakdown].sort(
        (left, right) => left.pass_rate_value - right.pass_rate_value || left.level.localeCompare(right.level),
    )[0];
    const programmeName = formatStoryProgrammeName(programme.programme);

    const insight = highestLoadLevel.level === weakestPassLevel.level
        ? `${programmeName} is heaviest in ${highestLoadLevel.level}, and that same level is also its weakest pass-conversion point at ${weakestPassLevel.pass_rate}.`
        : `${programmeName} is heaviest in ${highestLoadLevel.level}, while ${weakestPassLevel.level} is the weakest pass-conversion point at ${weakestPassLevel.pass_rate}.`;
    const action = `Action: Review ${weakestPassLevel.level} first, then use Back to compare that pressure point against the other top-enrolment programmes.`;

    return { insight, action };
};

export const buildPassOverviewNarrative = (rows) => {
    if (!rows.length) {
        return {
            insight: "No pass-trend insight is available for the current filters.",
            action: "Action: Adjust the current filters to bring the academic-level pass story back into view.",
        };
    }

    const { strongest, weakest } = getStrongestAndWeakestLevels(rows);
    const belowTargetRows = rows.filter((row) => Number(row.pass_rate_value || 0) < PASS_RATE_TARGET);
    const focusRow = belowTargetRows[0] || weakest;

    const insight = belowTargetRows.length
        ? `${weakest.level} is the clearest pass-rate pressure point at ${weakest.pass_rate}, and ${belowTargetRows.length} level${belowTargetRows.length === 1 ? "" : "s"} still sit below the ${PASS_RATE_TARGET}% target.`
        : `All visible levels are above the ${PASS_RATE_TARGET}% target, with ${strongest.level} currently leading the pass trend at ${strongest.pass_rate}.`;
    const action = belowTargetRows.length
        ? `Action: Click ${focusRow.level} first to see which programmes are holding that level below target.`
        : `Action: Click ${weakest.level} first if you want to inspect the softest point in an otherwise healthy pass trend.`;

    return { insight, action };
};

export const buildPassDetailNarrative = (levelRow) => {
    const rows = levelRow?.programme_breakdown || [];
    if (!levelRow || !rows.length) {
        return {
            insight: "No programme detail insight is available for the selected level.",
            action: "Action: Return to the pass trend and choose another academic level.",
        };
    }

    const highestLoadProgramme = [...rows].sort(
        (left, right) => right.registrations - left.registrations || left.programme.localeCompare(right.programme),
    )[0];
    const weakestProgramme = [...rows].sort(
        (left, right) =>
            left.pass_rate_value - right.pass_rate_value
            || left.average_mark - right.average_mark
            || left.programme.localeCompare(right.programme),
    )[0];
    const highestLoadName = formatStoryProgrammeName(highestLoadProgramme.programme);
    const weakestName = formatStoryProgrammeName(weakestProgramme.programme);

    const insight = highestLoadProgramme.programme === weakestProgramme.programme
        ? `${highestLoadName} carries the heaviest load in ${levelRow.level}, and it is also the weakest outcome point at ${weakestProgramme.pass_rate}.`
        : `${highestLoadName} carries the heaviest load in ${levelRow.level}, while ${weakestName} has the weakest pass-rate outcome at ${weakestProgramme.pass_rate}.`;
    const action = `Action: Hover ${weakestName} first for the full values, then use Find in table to confirm the level totals below.`;

    return { insight, action };
};
