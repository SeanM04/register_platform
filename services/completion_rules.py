"""Shared rules for completion and cohort-shift calculations."""

from dataclasses import dataclass
from typing import Iterable, Optional

PASS_MARK = 50.0
MAX_FAILS = 3


@dataclass(frozen=True)
class ZeroCompletionDecision:
    """Describe a decision that forces zero completion and shifts cohort timing."""

    key: str
    label: str
    shift_semesters: int
    match_terms: tuple[str, ...]


ZERO_COMPLETION_DECISIONS = (
    ZeroCompletionDecision(
        key="repeat_level_shift",
        label="Repeat level shift",
        shift_semesters=1,
        match_terms=("repeat level",),
    ),
    ZeroCompletionDecision(
        key="repeat_shift",
        label="Repeat shift",
        shift_semesters=1,
        match_terms=("repeat",),
    ),
    ZeroCompletionDecision(
        key="deferred_shift",
        label="Deferred shift",
        shift_semesters=1,
        match_terms=("deferred", "defer"),
    ),
    ZeroCompletionDecision(
        key="discontinue_shift",
        label="Discontinue shift",
        shift_semesters=1,
        match_terms=("discontinue", "discontinued"),
    ),
    ZeroCompletionDecision(
        key="expelled_shift",
        label="Expelled shift",
        shift_semesters=1,
        match_terms=("expelled", "expulsion"),
    ),
    ZeroCompletionDecision(
        key="results_nullified_shift",
        label="Results nullified shift",
        shift_semesters=1,
        match_terms=("results nullified", "nullified"),
    ),
    ZeroCompletionDecision(
        key="results_suppressed_shift",
        label="Results suppressed shift",
        shift_semesters=1,
        match_terms=("results suppressed", "suppressed"),
    ),
    ZeroCompletionDecision(
        key="suspended_two_semesters_shift",
        label="Suspended for two semesters shift",
        shift_semesters=2,
        match_terms=(
            "suspended for two semesters",
            "suspended 2 semesters",
            "suspended for 2 semesters",
            "suspended for two semester",
            "suspended 2 semester",
            "suspended for 2 semester",
        ),
    ),
)


def normalize_decision_text(decision: str) -> str:
    """Normalize a free-text decision for matching."""

    return " ".join(str(decision or "").strip().lower().split())


def get_zero_completion_decision(decision: str) -> Optional[ZeroCompletionDecision]:
    """Return the zero-completion decision rule when the decision matches one."""

    normalized = normalize_decision_text(decision)
    if not normalized:
        return None

    for rule in ZERO_COMPLETION_DECISIONS:
        if any(term in normalized for term in rule.match_terms):
            return rule
    return None


def student_completion_percentage(
    marks: Iterable[float],
    decision: str = "",
    pass_mark: float = PASS_MARK,
    max_fails: int = MAX_FAILS,
) -> float:
    """Calculate semester completion using the documented completion rules."""

    if get_zero_completion_decision(decision):
        return 0.0

    clean_marks = [float(mark) for mark in marks if mark is not None]
    total_courses = len(clean_marks)
    if not total_courses:
        return 0.0

    passed_courses = sum(1 for mark in clean_marks if mark >= pass_mark)
    failed_courses = total_courses - passed_courses
    if failed_courses >= (max_fails + 1):
        return 0.0

    return round((passed_courses / total_courses) * 100.0)
