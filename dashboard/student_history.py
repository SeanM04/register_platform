"""Shared student academic history helpers."""

from collections import defaultdict
import logging
import re


PASS_MARK = 50
MERGE_SIGNAL_TOKENS = ("repeat", "repeated", "carry", "carrying", "supp", "supplementary", "retake")
VISITING_SIGNAL_TOKENS = ("visiting", "exchange", "short")
logger = logging.getLogger(__name__)


def _registration_results(registration):
    """Return course results, preferring prefetched results when present."""

    prefetched_results = getattr(registration, "prefetched_course_results", None)
    if prefetched_results is not None:
        return prefetched_results
    return registration.course_results.all()


def _normalized_text(value):
    """Return a consistently normalized text value."""

    return str(value or "").strip()


def _normalized_attendance_label(value):
    """Return a stable human-readable attendance label."""

    text = _normalized_text(value)
    if not text:
        return ""

    normalized = text.lower()
    if "visit" in normalized or "exchange" in normalized or "short" in normalized:
        return "Visiting"
    if normalized in {"1", "conventional", "regular", "normal"}:
        return "Conventional"
    if normalized in {"2", "visiting", "visitor"}:
        return "Visiting"
    if normalized.startswith("attendance type"):
        if "1" in normalized:
            return "Conventional"
        if "2" in normalized:
            return "Visiting"
    return text.title()


def _registration_attendance_label(registration):
    """Return the most reliable attendance label for a registration."""

    registration_type = _normalized_attendance_label(
        getattr(getattr(registration, "attendance_type_record", None), "name", "")
    )
    if registration_type:
        return registration_type

    for result in _registration_results(registration):
        result_type = _normalized_attendance_label(
            getattr(getattr(result, "attendance_type_record", None), "name", "")
        ) or _normalized_attendance_label(getattr(result, "attendance_type", ""))
        if result_type:
            return result_type

    return ""


def _registration_is_visiting(registration):
    """Return whether the registration follows a visiting/exchange path."""

    attendance_label = _registration_attendance_label(registration).lower()
    return any(token in attendance_label for token in VISITING_SIGNAL_TOKENS)


def _timeline_is_visiting(registrations):
    """Return whether any registration in a timeline shows a visiting path."""

    return any(_registration_is_visiting(registration) for registration in registrations)


def _coerce_int(value, default=None):
    """Return the first integer found in a value."""

    if value is None:
        return default
    if isinstance(value, int):
        return value

    text = str(value).strip()
    if not text:
        return default
    if text.isdigit():
        return int(text)

    match = re.search(r"(\d+)", text)
    if match:
        return int(match.group(1))
    return default


def extract_registration_year_semester(registration):
    """Resolve the canonical programme year and semester for a registration."""

    period = getattr(registration, "period", None)
    year = _coerce_int(getattr(period, "academic_year", None))
    semester = _coerce_int(getattr(period, "semester", None))
    period_name = str(getattr(period, "name", "") or "")

    if year is None:
        year_match = re.search(r"\byear\s*(\d+)\b", period_name, flags=re.IGNORECASE)
        year = int(year_match.group(1)) if year_match else 1

    if semester is None:
        semester_match = re.search(r"\b(?:semester|sem|term)\s*(\d+)\b", period_name, flags=re.IGNORECASE)
        semester = int(semester_match.group(1)) if semester_match else 1

    return max(year or 1, 1), max(semester or 1, 1)


def format_year_label(year):
    return f"Year {int(year)}"


def format_semester_label(semester):
    return f"Semester {int(semester)}"


def format_academic_level_label(year, semester):
    return f"{format_year_label(year)} {format_semester_label(semester)}"


def build_registration_group_key(registration):
    """Return a stable programme-structure key for a registration."""

    year, semester = extract_registration_year_semester(registration)
    return f"{year}:{semester}"


def sort_registrations_by_structure(registrations):
    """Sort registrations chronologically using the source period ordering."""

    return sorted(
        registrations,
        key=lambda registration: (
            getattr(getattr(registration, "period", None), "external_id", 0) or 0,
            registration.id or 0,
        ),
    )


def _registration_course_codes(registration):
    """Return normalized course codes attached to a registration."""

    codes = []
    for result in _registration_results(registration):
        course = getattr(result, "course", None)
        code = str(getattr(course, "code", "") or "").strip()
        if code:
            codes.append(code)
    return codes


def _decision_text(registration):
    """Return a normalized decision label for merge heuristics."""

    return str(getattr(registration, "decision", "") or "").strip().lower()


def _course_progression_band(course_codes):
    """Infer a rough progression band from course codes like CHEP101 or CHEP221."""

    bands = []
    for code in course_codes:
        match = re.search(r"(\d{3})", str(code or ""))
        if not match:
            continue
        bands.append(int(match.group(1)) // 10)

    if not bands:
        return None
    return max(bands)


def _progression_band_to_stage(band):
    """Convert a band like 31 or 42 into a displayed year/semester pair."""

    if band is None:
        return None

    year = max(int(band) // 10, 1)
    semester = 2 if int(band) % 10 >= 2 else 1
    return year, semester


def _programme_stage_cap(programme_name, is_visiting=False):
    """Return the maximum displayed stage index allowed for a programme."""

    normalized = str(programme_name or "").strip().lower()
    if "masters" in normalized or "master" in normalized or "msc" in normalized:
        return 3
    if is_visiting and _programme_is_engineering(programme_name):
        return 8
    if is_visiting:
        return 6
    if _programme_is_engineering(programme_name):
        return 10
    return 8


def _programme_is_engineering(programme_name):
    """Return True when a programme should follow engineering stage rules."""

    normalized = str(programme_name or "").strip().lower()
    return bool(
        "engineering" in normalized
        or "beng" in normalized
        or re.search(r"\beng\b", normalized)
    )


def _group_has_attachment_signal(group):
    """Return True when a group contains attachment/work-related-learning modules."""

    attachment_terms = (
        "attachment",
        "internship",
        "industrial training",
        "work related learning",
        "work-related learning",
        "supervisor's assessment report",
        "supervisors assessment report",
        "academic supervisor's assessment report",
        "academic supervisors assessment report",
        "employer's assessment report",
        "employers assessment report",
    )

    for row in group.get("results", []):
        course_text = " ".join(
            [
                str(row.get("course_code", "") or "").strip().lower(),
                str(row.get("course_name", "") or "").strip().lower(),
            ]
        ).strip()
        if any(term in course_text for term in attachment_terms):
            return True
    return False


def _group_has_work_related_signal(group):
    """Return True when a group contains any work-related module naming."""

    work_related_terms = (
        "work related",
        "work-related",
    )

    for row in group.get("results", []):
        course_text = " ".join(
            [
                str(row.get("course_code", "") or "").strip().lower(),
                str(row.get("course_name", "") or "").strip().lower(),
            ]
        ).strip()
        if any(term in course_text for term in work_related_terms):
            return True
    return False


def _group_signal_row_count(group, predicate):
    """Return how many module rows in a group match a signal predicate."""

    count = 0
    total = 0
    for row in group.get("results", []):
        total += 1
        if predicate(row):
            count += 1
    return count, total


def _row_has_attachment_signal(row):
    """Return True when a single module row looks like attachment/work-related learning."""

    attachment_terms = (
        "attachment",
        "internship",
        "industrial training",
        "work related learning",
        "work-related learning",
        "supervisor's assessment report",
        "supervisors assessment report",
        "academic supervisor's assessment report",
        "academic supervisors assessment report",
        "employer's assessment report",
        "employers assessment report",
    )
    course_text = " ".join(
        [
            str(row.get("course_code", "") or "").strip().lower(),
            str(row.get("course_name", "") or "").strip().lower(),
        ]
    ).strip()
    return any(term in course_text for term in attachment_terms)


def _row_has_work_related_signal(row):
    """Return True when a single module row contains work-related naming."""

    work_related_terms = (
        "work related",
        "work-related",
    )
    course_text = " ".join(
        [
            str(row.get("course_code", "") or "").strip().lower(),
            str(row.get("course_name", "") or "").strip().lower(),
        ]
    ).strip()
    return any(term in course_text for term in work_related_terms)


def _group_is_attachment_style_block(group):
    """Return True when a group is predominantly an attachment/work-related block."""

    signal_count, total_rows = _group_signal_row_count(group, _row_has_attachment_signal)
    if not signal_count or not total_rows:
        return False
    return True


def _group_is_work_related_block(group):
    """Return True when a group is predominantly a work-related block."""

    signal_count, total_rows = _group_signal_row_count(group, _row_has_work_related_signal)
    if not signal_count or not total_rows:
        return False
    return True


def _row_progression_stage_index(row):
    """Return a stage index inferred from a module row's course code."""

    stage = _progression_band_to_stage(
        _course_progression_band([str(row.get("course_code", "") or "").strip()])
    )
    if stage is None:
        return None
    return _stage_to_index(*stage)


def _group_has_lower_stage_non_signal_rows(group, signal_predicate, minimum_stage_index):
    """Return True when mixed ordinary modules still belong to an earlier stage."""

    for row in group.get("results", []):
        if signal_predicate(row):
            continue
        stage_index = _row_progression_stage_index(row)
        if stage_index is not None and stage_index < minimum_stage_index:
            return True
    return False


def _infer_group_display_stage(group):
    """Infer the best display stage from module progression signals."""

    if _group_is_work_related_block(group):
        programme = getattr(group.get("latest_registration"), "programme", None)
        programme_name = getattr(programme, "name", "") or ""
        if _programme_is_engineering(programme_name):
            if _group_has_lower_stage_non_signal_rows(group, _row_has_work_related_signal, _stage_to_index(4, 1)):
                return None
            return 4, 2
        if _group_has_lower_stage_non_signal_rows(group, _row_has_work_related_signal, _stage_to_index(3, 1)):
            return None
        if "masters" not in programme_name.lower() and "master" not in programme_name.lower() and "msc" not in programme_name.lower():
            return 3, 2

    if _group_is_attachment_style_block(group):
        programme = getattr(group.get("latest_registration"), "programme", None)
        programme_name = getattr(programme, "name", "") or ""
        if _programme_is_engineering(programme_name):
            if _group_has_lower_stage_non_signal_rows(group, _row_has_attachment_signal, _stage_to_index(4, 1)):
                return None
            return 4, 2
        if _group_has_lower_stage_non_signal_rows(group, _row_has_attachment_signal, _stage_to_index(3, 1)):
            return None
        if "masters" not in programme_name.lower() and "master" not in programme_name.lower() and "msc" not in programme_name.lower():
            return 3, 2

    return None


def _stage_to_index(year, semester):
    """Convert a year/semester pair into a monotonic semester index."""

    return (max(int(year), 1) - 1) * 2 + max(int(semester), 1)


def _index_to_stage(index):
    """Convert a monotonic semester index back into year/semester."""

    safe_index = max(int(index), 1)
    year = ((safe_index - 1) // 2) + 1
    semester = 2 if safe_index % 2 == 0 else 1
    return year, semester


def _registration_merge_signal_reasons(registration):
    """Return repeat/carry/supp evidence supporting a same-stage merge."""

    reasons = []
    decision_text = _decision_text(registration)
    if any(token in decision_text for token in MERGE_SIGNAL_TOKENS):
        reasons.append(f"decision={decision_text}")
    if int(getattr(registration, "carrying", 0) or 0) > 0:
        reasons.append(f"carrying={int(getattr(registration, 'carrying', 0) or 0)}")

    registration_attendance = _registration_attendance_label(registration).lower()
    if any(token in registration_attendance for token in MERGE_SIGNAL_TOKENS):
        reasons.append(f"attendance={registration_attendance}")

    for result in _registration_results(registration):
        attendance_type = _normalized_text(
            getattr(getattr(result, "attendance_type_record", None), "name", "")
        ) or _normalized_text(getattr(result, "attendance_type", ""))
        normalized_attendance = attendance_type.lower()
        if any(token in normalized_attendance for token in MERGE_SIGNAL_TOKENS):
            reasons.append(
                f"result:{getattr(getattr(result, 'course', None), 'code', '') or result.id}={normalized_attendance}"
            )

    return reasons


def _registration_has_repeat_signal(registration, registration_course_codes):
    """Return True when course-level evidence still supports the same repeated stage."""

    return bool(_registration_merge_signal_reasons(registration))


def _dedupe_tags(tags):
    """Return tags in stable order without duplicates."""

    seen = set()
    ordered_tags = []
    for tag in tags:
        normalized_tag = str(tag or "").strip()
        if not normalized_tag or normalized_tag in seen:
            continue
        seen.add(normalized_tag)
        ordered_tags.append(normalized_tag)
    return ordered_tags


def _log_merge_decision(group, registration, merge_allowed, reasons):
    """Emit a debug log explaining why a registration did or did not merge."""

    logger.debug(
        "student_timeline.merge registration_id=%s period_external_id=%s group_key=%s merge=%s reasons=%s",
        getattr(registration, "id", None),
        getattr(getattr(registration, "period", None), "external_id", None),
        group.get("key"),
        merge_allowed,
        reasons,
    )


def _merge_group_into_display_group(target_group, source_group):
    """Preserve later raw registrations inside the same displayed stage."""

    target_group["registrations"].extend(source_group.get("registrations", []))
    target_group["results"].extend(source_group.get("results", []))
    target_group["course_codes"].update(source_group.get("course_codes", set()))
    target_group["failed_course_codes"].update(source_group.get("failed_course_codes", set()))

    source_band = source_group.get("progression_band")
    target_band = target_group.get("progression_band")
    if source_band is not None:
        target_group["progression_band"] = (
            source_band
            if target_band is None
            else max(target_band, source_band)
        )

    for period_name in source_group.get("period_names", []):
        if period_name and period_name not in target_group["period_names"]:
            target_group["period_names"].append(period_name)

    source_sort_key = source_group.get("sort_key", (0, 0))
    target_sort_key = target_group.get("sort_key", (0, 0))
    if source_sort_key >= target_sort_key:
        target_group["latest_registration"] = source_group.get("latest_registration")
        target_group["sort_key"] = source_sort_key

    target_group["merged_display_overflow"] = True


def _should_merge_with_group(group, registration, year, semester, registration_course_codes):
    """Decide whether a registration continues the current displayed semester."""

    if group["raw_year"] != year or group["raw_semester"] != semester:
        _log_merge_decision(
            group,
            registration,
            False,
            [
                f"raw_stage_changed={group['raw_year']}:{group['raw_semester']}->{year}:{semester}",
            ],
        )
        return False

    if not registration_course_codes:
        _log_merge_decision(group, registration, False, ["no_registration_modules"])
        return False

    registration_band = _course_progression_band(registration_course_codes)
    group_band = group.get("progression_band")
    if (
        registration_band is not None
        and group_band is not None
        and registration_band > group_band
        and not group["course_codes"].intersection(registration_course_codes)
    ):
        _log_merge_decision(
            group,
            registration,
            False,
            [
                f"progression_band_advanced={group_band}->{registration_band}",
                "no_course_overlap",
            ],
        )
        return False

    overlap = group["course_codes"].intersection(registration_course_codes)
    repeat_overlap = group.get("failed_course_codes", set()).intersection(registration_course_codes)
    explicit_repeat_reasons = _registration_merge_signal_reasons(registration)
    new_course_codes = set(registration_course_codes) - overlap

    if not explicit_repeat_reasons:
        _log_merge_decision(
            group,
            registration,
            False,
            [
                "same_raw_stage_but_no_repeat_signal",
                f"overlap={sorted(overlap)}" if overlap else "overlap=[]",
            ],
        )
        return False

    if not overlap:
        _log_merge_decision(
            group,
            registration,
            False,
            [*explicit_repeat_reasons, "no_shared_course_codes"],
        )
        return False

    if len(new_course_codes) > len(overlap):
        _log_merge_decision(
            group,
            registration,
            False,
            [
                *explicit_repeat_reasons,
                f"mostly_new_modules={sorted(new_course_codes)}",
                f"overlap={sorted(overlap)}",
            ],
        )
        return False

    merge_reasons = [
        *explicit_repeat_reasons,
        f"overlap={sorted(overlap)}",
    ]
    if repeat_overlap:
        merge_reasons.append(f"failed_overlap={sorted(repeat_overlap)}")
    _log_merge_decision(group, registration, True, merge_reasons)
    return True


def build_student_timeline(registrations):
    """
    Build a structure-based academic timeline.

    Repeated registrations in the same official year/semester collapse into one
    semester container, while every course attempt remains visible for audit and
    transcript history.
    """

    ordered_registrations = sort_registrations_by_structure(registrations)
    is_visiting_timeline = _timeline_is_visiting(ordered_registrations)
    groups = []
    course_attempts = defaultdict(list)

    for registration in ordered_registrations:
        year, semester = extract_registration_year_semester(registration)
        registration_course_codes = _registration_course_codes(registration)
        group = (
            groups[-1]
            if groups and _should_merge_with_group(groups[-1], registration, year, semester, registration_course_codes)
            else None
        )
        if group is None:
            group = {
                "key": f"slot-{len(groups) + 1}",
                "year": year,
                "semester": semester,
                "raw_year": year,
                "raw_semester": semester,
                "year_label": format_year_label(year),
                "semester_label": format_semester_label(semester),
                "academic_level_label": format_academic_level_label(year, semester),
                "period_names": [],
                "registrations": [],
                "results": [],
                "course_codes": set(),
                "failed_course_codes": set(),
                "latest_registration": registration,
                "progression_band": _course_progression_band(registration_course_codes),
                "sort_key": (
                    getattr(getattr(registration, "period", None), "external_id", 0) or 0,
                    registration.id or 0,
                ),
            }
            groups.append(group)
            logger.debug(
                "student_timeline.new_group registration_id=%s raw_stage=%s:%s period_external_id=%s",
                getattr(registration, "id", None),
                year,
                semester,
                getattr(getattr(registration, "period", None), "external_id", None),
            )
        else:
            logger.debug(
                "student_timeline.group_merged registration_id=%s into_group=%s raw_stage=%s:%s",
                getattr(registration, "id", None),
                group["key"],
                year,
                semester,
            )

        group["registrations"].append(registration)
        group["course_codes"].update(registration_course_codes)
        registration_band = _course_progression_band(registration_course_codes)
        if registration_band is not None:
            existing_band = group.get("progression_band")
            group["progression_band"] = (
                registration_band
                if existing_band is None
                else max(existing_band, registration_band)
            )
        period_name = str(getattr(getattr(registration, "period", None), "name", "") or "").strip()
        if period_name and period_name not in group["period_names"]:
            group["period_names"].append(period_name)
        if (
            getattr(getattr(registration, "period", None), "external_id", 0) or 0,
            registration.id or 0,
        ) >= (
            getattr(getattr(group["latest_registration"], "period", None), "external_id", 0) or 0,
            group["latest_registration"].id or 0,
        ):
            group["latest_registration"] = registration
            group["sort_key"] = (
                getattr(getattr(registration, "period", None), "external_id", 0) or 0,
                registration.id or 0,
            )

        registration_results = sorted(
            _registration_results(registration),
            key=lambda result: (
                getattr(getattr(result, "course", None), "code", "") or "",
                getattr(getattr(result, "course", None), "name", "") or "",
                result.id or 0,
            ),
        )
        for result in registration_results:
            course = getattr(result, "course", None)
            course_code = str(getattr(course, "code", "") or "").strip() or f"COURSE-{result.id}"
            previous_attempts = course_attempts[course_code]
            attempt_number = len(previous_attempts) + 1
            mark_value = round(float(result.mark)) if result.mark is not None else None
            is_pass = mark_value is not None and mark_value >= PASS_MARK
            prior_failures = [attempt for attempt in previous_attempts if attempt["mark_value"] is not None and not attempt["is_pass"]]
            original_attempt = previous_attempts[0] if previous_attempts else None

            is_repeat_attempt = attempt_number > 1
            is_carried_attempt = bool(prior_failures) and bool(original_attempt) and (
                original_attempt["year"] != year or original_attempt["semester"] != semester
            )
            supplementary_text = (
                _normalized_text(getattr(getattr(result, "attendance_type_record", None), "name", ""))
                or _normalized_text(getattr(result, "attendance_type", ""))
            ).lower()
            is_supplementary_attempt = any(token in supplementary_text for token in ("supp", "supplementary"))

            attempt_tags = []
            if attempt_number > 1:
                attempt_tags.append(f"Attempt {attempt_number}")
            if is_carried_attempt:
                attempt_tags.append("Carried")
            elif is_repeat_attempt:
                attempt_tags.append("Repeated")
            if is_supplementary_attempt:
                attempt_tags.append("Supplementary")
            attempt_tags = _dedupe_tags(attempt_tags)

            suffix = f" ({', '.join(attempt_tags)})" if attempt_tags else ""
            attempt_row = {
                "group_key": group["key"],
                "year": year,
                "semester": semester,
                "academic_year": format_year_label(year),
                "period": format_semester_label(semester),
                "semester_label": format_semester_label(semester),
                "academic_level_label": format_academic_level_label(year, semester),
                "display_year": year,
                "display_semester": semester,
                "display_academic_year": format_year_label(year),
                "display_period": format_semester_label(semester),
                "display_semester_label": format_semester_label(semester),
                "display_academic_level_label": format_academic_level_label(year, semester),
                "period_name": period_name or format_semester_label(semester),
                "course_code": course_code,
                "course_name": str(getattr(course, "name", "") or "Unknown"),
                "course_display_name": f"{str(getattr(course, 'name', '') or 'Unknown')}{suffix}",
                "mark_value": mark_value,
                "mark": f"{mark_value}%" if mark_value is not None else "--",
                "is_pass": is_pass,
                "is_failing": mark_value is not None and mark_value < PASS_MARK,
                "attempt_number": attempt_number,
                "is_repeat_attempt": is_repeat_attempt,
                "is_carried_attempt": is_carried_attempt,
                "is_supplementary_attempt": is_supplementary_attempt,
                "attempt_tags": attempt_tags,
                "original_year": original_attempt["year"] if original_attempt else year,
                "original_semester": original_attempt["semester"] if original_attempt else semester,
                "registration_id": getattr(registration, "id", None),
                "registration_external_id": getattr(registration, "external_id", None),
                "registration": registration,
                "result": result,
            }
            group["results"].append(attempt_row)
            previous_attempts.append(attempt_row)
            if attempt_row["is_failing"]:
                group["failed_course_codes"].add(course_code)
            logger.debug(
                "student_timeline.module_row registration_id=%s course_code=%s raw_stage=%s:%s attempt_number=%s tags=%s repeat=%s carried=%s supplementary=%s",
                getattr(registration, "id", None),
                course_code,
                year,
                semester,
                attempt_number,
                attempt_tags,
                is_repeat_attempt,
                is_carried_attempt,
                is_supplementary_attempt,
            )

    groups.sort(key=lambda group: group["sort_key"])

    # Imported stage labels can be offset or skip semesters entirely.
    # Rebase the student-facing timeline using module progression signals first,
    # then preserve chronological raw-stage gaps when the import is sparse.
    previous_display_stage = None
    stage_occurrence_counts = defaultdict(int)
    finalized_groups = []
    for index, group in enumerate(groups):
        raw_year = group["raw_year"]
        raw_semester = group["raw_semester"]
        programme = getattr(group.get("latest_registration"), "programme", None)
        programme_name = getattr(programme, "name", "") or ""
        max_stage_index = _programme_stage_cap(programme_name, is_visiting=is_visiting_timeline)
        inferred_stage = _infer_group_display_stage(group)
        if inferred_stage is not None:
            display_year, display_semester = inferred_stage
            stage_reason = f"override={display_year}:{display_semester}"
        elif previous_display_stage is None:
            display_year, display_semester = 1, 1
            stage_reason = "timeline_start=1:1"
        else:
            previous_display_index = _stage_to_index(*previous_display_stage)
            display_year, display_semester = _index_to_stage(
                previous_display_index + 1
            )
            stage_reason = (
                f"sequential_advance previous_display={previous_display_stage[0]}:{previous_display_stage[1]} "
                f"next_index={previous_display_index + 1}"
            )
        display_stage_index = min(_stage_to_index(display_year, display_semester), max_stage_index)
        display_year, display_semester = _index_to_stage(display_stage_index)
        stage_reason = f"{stage_reason} capped_to={display_year}:{display_semester} max_stage_index={max_stage_index}"
        previous_display_stage = (display_year, display_semester)

        if (
            finalized_groups
            and display_stage_index == max_stage_index
            and finalized_groups[-1]["year"] == display_year
            and finalized_groups[-1]["semester"] == display_semester
        ):
            _merge_group_into_display_group(finalized_groups[-1], group)
            logger.debug(
                "student_timeline.stage_assignment_overflow merged_into=%s raw_stage=%s:%s display_stage=%s:%s reason=%s registrations=%s",
                finalized_groups[-1]["key"],
                raw_year,
                raw_semester,
                display_year,
                display_semester,
                stage_reason,
                [getattr(registration, "id", None) for registration in group["registrations"]],
            )
            continue

        base_group_key = f"{display_year}:{display_semester}"
        stage_occurrence_counts[base_group_key] += 1
        group["key"] = (
            base_group_key
            if stage_occurrence_counts[base_group_key] == 1
            else f"{base_group_key}:{stage_occurrence_counts[base_group_key]}"
        )
        group["year"] = display_year
        group["semester"] = display_semester
        group["year_label"] = format_year_label(display_year)
        group["semester_label"] = format_semester_label(display_semester)
        group["academic_level_label"] = format_academic_level_label(display_year, display_semester)
        logger.debug(
            "student_timeline.stage_assignment group_key=%s raw_stage=%s:%s display_stage=%s:%s reason=%s registrations=%s",
            group["key"],
            raw_year,
            raw_semester,
            display_year,
            display_semester,
            stage_reason,
            [getattr(registration, "id", None) for registration in group["registrations"]],
        )
        finalized_groups.append(group)

    groups = finalized_groups
    for group in groups:
        group["results"].sort(
            key=lambda row: (
                row["course_code"],
                -row["attempt_number"],
                row["course_name"],
            )
        )

        for row in group["results"]:
            row["raw_year"] = row["year"]
            row["raw_semester"] = row["semester"]
            row["group_key"] = group["key"]
            row["display_year"] = display_year
            row["display_semester"] = display_semester
            row["display_academic_year"] = format_year_label(display_year)
            row["display_period"] = format_semester_label(display_semester)
            row["display_semester_label"] = format_semester_label(display_semester)
            row["display_academic_level_label"] = format_academic_level_label(display_year, display_semester)

        has_repeat_history = any(row["is_repeat_attempt"] for row in group["results"])
        latest_period_name = str(
            getattr(getattr(group["latest_registration"], "period", None), "name", "") or ""
        ).strip()
        if (has_repeat_history or group.get("merged_display_overflow")) and group["period_names"]:
            group["period_display"] = " / ".join(group["period_names"])
        else:
            group["period_display"] = latest_period_name or (group["period_names"][-1] if group["period_names"] else group["semester_label"])
        group.pop("course_codes", None)
        group.pop("failed_course_codes", None)
        group.pop("progression_band", None)
        group.pop("merged_display_overflow", None)

    for attempts in course_attempts.values():
        if len(attempts) > 1:
            first_attempt = attempts[0]
            if "First Attempt" not in first_attempt["attempt_tags"]:
                first_attempt["attempt_tags"] = _dedupe_tags(["First Attempt", *first_attempt["attempt_tags"]])
                first_attempt["course_display_name"] = (
                    f"{first_attempt['course_name']} ({', '.join(first_attempt['attempt_tags'])})"
                )
        for attempt in attempts:
            if attempt["mark_value"] is None:
                attempt["status_label"] = "Awaiting"
            else:
                attempt["status_label"] = "Passed" if attempt["is_pass"] else "Failed"
            logger.debug(
                "student_timeline.attempt_history course_code=%s registration_id=%s tags=%s status=%s original_stage=%s:%s display_stage=%s:%s",
                attempt["course_code"],
                attempt.get("registration_id"),
                attempt["attempt_tags"],
                attempt["status_label"],
                attempt["year"],
                attempt["semester"],
                attempt["display_year"],
                attempt["display_semester"],
            )

    return {
        "groups": groups,
        "groups_by_key": {group["key"]: group for group in groups},
    }


def build_registration_display_level_index(registrations):
    """Map each registration to the student-facing academic level used in detail views."""

    registrations_by_student = defaultdict(list)
    for registration in registrations:
        registrations_by_student[registration.student_id].append(registration)

    level_index = {}
    for student_registrations in registrations_by_student.values():
        timeline = build_student_timeline(student_registrations)
        for group in timeline["groups"]:
            level_meta = {
                "display_year": group["year"],
                "display_semester": group["semester"],
                "academic_level_label": group["academic_level_label"],
            }
            for registration in group["registrations"]:
                level_index[registration.id] = level_meta

    return level_index


def build_registration_display_level_index_for_student_ids(student_ids, faculty_name=""):
    """Load registration history for students and map each registration to its display level."""

    if not student_ids:
        return {}

    from django.db.models import Prefetch

    from .models import CourseResult, Registration

    registrations = (
        Registration.objects.filter(student_id__in=student_ids)
        .select_related("student", "programme__department__faculty", "period", "attendance_type_record")
        .prefetch_related(
            Prefetch(
                "course_results",
                queryset=CourseResult.objects.select_related("course", "attendance_type_record").only(
                    "registration_id",
                    "mark",
                    "attendance_type",
                    "attendance_type_record__name",
                    "course__code",
                    "course__name",
                ),
                to_attr="prefetched_course_results",
            )
        )
        .order_by("student_id", "period__external_id", "id")
    )
    if faculty_name:
        registrations = registrations.filter(programme__department__faculty__name=faculty_name)

    return build_registration_display_level_index(list(registrations))


def calculate_cumulative_average(groups, selected_group_key=None):
    """Return a non-duplicated cumulative average using each course's latest attempt."""

    if not groups:
        return 0

    latest_results_by_course = {}
    for group in groups:
        for row in group["results"]:
            latest_results_by_course[row["course_code"]] = row
        if selected_group_key and group["key"] == selected_group_key:
            break

    marks = [row["mark_value"] for row in latest_results_by_course.values() if row["mark_value"] is not None]
    if not marks:
        return 0
    return round(sum(marks) / len(marks), 1)


def build_transcript_summary(groups):
    """Build summary totals from the latest attempt per course."""

    latest_results_by_course = {}
    for group in groups:
        for row in group["results"]:
            latest_results_by_course[row["course_code"]] = row

    latest_rows = list(latest_results_by_course.values())
    marks = [row["mark_value"] for row in latest_rows if row["mark_value"] is not None]
    total_courses = len(latest_rows)
    total_passed = sum(1 for row in latest_rows if row["is_pass"])
    total_failed = sum(1 for row in latest_rows if row["mark_value"] is not None and not row["is_pass"])
    average_mark = round(sum(marks) / len(marks), 1) if marks else 0

    return {
        "total_courses": total_courses,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "average_mark": f"{average_mark}%",
        "pass_rate": f"{round((total_passed / total_courses) * 100, 1) if total_courses else 0}%",
        "completion_rate": f"{round((len(marks) / total_courses) * 100, 1) if total_courses else 0}%",
    }
