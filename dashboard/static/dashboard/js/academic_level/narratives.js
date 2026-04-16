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
                <p class="level-story-pill-label">${topProgramme ? formatStoryProgrammeName(topProgramme.programme) : "Load Leader"}</p>
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
    setHintMarkup(element, []);
};

export const setTopProgrammeHints = (element, isDetail) => {
    setHintMarkup(element, isDetail ? [
        { label: "Use Back to top 5 to compare", kind: "support" },
    ] : [
        { label: "Click a slice to drill down", kind: "drill" },
    ]);
};

export const setPassTrendHints = (element, isDetail) => {
    setHintMarkup(element, isDetail ? [
        { label: "Use Find in table for exact totals", kind: "support" },
    ] : [
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
            ? `${leadRow.label} and ${trailingRow.label} are close to balanced in the current cohort, with ${leadRow.label} holding a narrow ${representationGap}-point edge at ${leadRow.student_share}.`
            : `${leadRow.label} leads the visible cohort at ${leadRow.student_share}, opening a ${representationGap}-point gap over ${trailingRow.label}.`
        : `${leadRow.label} accounts for ${leadRow.student_share} of the visible cohort in the current filters.`;
    const action = trailingRow && passGap >= 4
        ? `Compare ${strongestPass.label} and ${weakestPass.label} next, because their pass rates are ${passGap} points apart within the current gender mix.`
        : trailingRow
            ? `Keep tracking the balance between ${leadRow.label} and ${trailingRow.label} so the cohort mix stays steady as enrolment shifts.`
            : "Broaden the current filters if you want to compare this cohort against an additional gender segment.";

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
    const runnerUp = [...rows].sort(
        (left, right) => right.registrations - left.registrations || left.programme.localeCompare(right.programme),
    )[1] || null;
    const topShare = totalRegistrations ? Math.round((topRow.registrations / totalRegistrations) * 100) : 0;
    const programmeName = formatStoryProgrammeName(topRow.programme);

    const insight = `${programmeName} currently carries ${numberFormatter.format(topRow.registrations)} registrations, which is about ${topShare}% of the visible top-five programme load.`;
    const action = runnerUp
        ? `Drill into ${programmeName} first to see which academic levels are absorbing that load before comparing it with the next programme behind it.`
        : "Widen the current filters if you want a broader programme comparison across the cohort.";

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

    const insight = `${programmeName} is most concentrated in ${highestLoadLevel.level}, where it currently holds ${numberFormatter.format(highestLoadLevel.registrations)} registrations.`;
    const action = `Watch ${weakestPassLevel.level} next, because it is the weakest pass-rate point for ${programmeName} at ${weakestPassLevel.pass_rate}.`;

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
    const passGap = strongest && weakest ? Math.round(strongest.pass_rate_value - weakest.pass_rate_value) : 0;

    const insight = belowTargetRows.length
        ? `${belowTargetRows.length} academic level${belowTargetRows.length === 1 ? "" : "s"} ${belowTargetRows.length === 1 ? "is" : "are"} still below the ${PASS_RATE_TARGET}% target, with ${focusRow.level} currently the clearest pressure point at ${focusRow.pass_rate}.`
        : `${strongest.level} currently leads the academic journey at ${strongest.pass_rate}, and every visible level is holding at or above the ${PASS_RATE_TARGET}% target.`;
    const action = passGap >= 5
        ? `Review the gap between ${strongest.level} and ${weakest.level} next, because pass performance is spread by ${passGap} points across the current levels.`
        : `Track ${focusRow.level} next to keep the pass trend stable across the current academic journey.`;

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

    const insight = `${levelRow.level} is currently anchored by ${highestLoadName}, which carries the largest programme load in this level at ${numberFormatter.format(highestLoadProgramme.registrations)} registrations.`;
    const action = `Compare ${weakestName} next, because it is the weakest pass-rate pocket inside ${levelRow.level} at ${weakestProgramme.pass_rate}.`;

    return { insight, action };
};
