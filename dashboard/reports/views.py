"""
Custom report generation views for the UniStudio platform.

Reports available
-----------------
enrolment       — student and registration counts by faculty / programme / period
pass_rate       — pass rate analysis by programme / faculty
at_risk         — students with average mark below a configurable threshold
programme       — programme-level performance summary
demographic     — gender breakdown by faculty

Row limit
---------
All generators cap results at MAX_ROWS rows.  If the DB result exceeds that
cap the response includes "truncated": true so the client can show a banner.
"""

from collections import defaultdict

from django.db.models import Avg, Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.decorators import ajax_login_required, platform_admin_required
from dashboard.models import AcademicPeriod, CourseResult, Faculty, Registration
from dashboard.views import build_layout_context

MAX_ROWS         = 500
DEFAULT_THRESHOLD = 50


# ---------------------------------------------------------------------------
# Page view
# ---------------------------------------------------------------------------

@platform_admin_required
def reports_view(request):
    """Render the admin-only custom reports workspace."""
    context = build_layout_context(request, "reports")

    years = sorted(
        {p.academic_year for p in AcademicPeriod.objects.all() if p.academic_year},
        reverse=True,
    )
    periods  = list(AcademicPeriod.objects.values_list("name", flat=True).order_by("name"))
    faculties = list(Faculty.objects.values_list("name", flat=True).order_by("name"))

    context.update({
        "page_title":        "Reports",
        "hide_filters":      True,
        "years":             years,
        "periods":           periods,
        "faculties":         faculties,
        "selected_year":     request.GET.get("year", ""),
        "selected_period":   request.GET.get("period", ""),
        "selected_faculty":  request.GET.get("faculty", ""),
        "default_threshold": DEFAULT_THRESHOLD,
        "report_types": [
            {"key": "enrolment",   "label": "Enrolment Summary"},
            {"key": "pass_rate",   "label": "Pass Rate Analysis"},
            {"key": "at_risk",     "label": "At-Risk Students"},
            {"key": "programme",   "label": "Programme Performance"},
            {"key": "demographic", "label": "Demographic Breakdown"},
        ],
    })
    return render(request, "dashboard/reports.html", context)


# ---------------------------------------------------------------------------
# Cascading filter
# ---------------------------------------------------------------------------

@ajax_login_required
@require_GET
def reports_periods_by_year(request):
    """Return period names for a given academic year."""
    year = request.GET.get("year", "").strip()
    qs   = AcademicPeriod.objects.order_by("name")
    if year:
        qs = qs.filter(academic_year=year)
    return JsonResponse({"periods": list(qs.values_list("name", flat=True))})


# ---------------------------------------------------------------------------
# JSON payload
# ---------------------------------------------------------------------------

@ajax_login_required
@require_GET
def reports_generate(request):
    """Return report data as JSON."""
    report_type = request.GET.get("report_type", "enrolment").strip()
    year        = request.GET.get("year",    "").strip()
    period      = request.GET.get("period",  "").strip()
    faculty     = request.GET.get("faculty", "").strip()
    threshold   = _parse_threshold(request.GET.get("threshold", ""))

    generators = {
        "enrolment":   _report_enrolment,
        "pass_rate":   _report_pass_rate,
        "at_risk":     _report_at_risk,
        "programme":   _report_programme,
        "demographic": _report_demographic,
    }
    generator = generators.get(report_type)
    if generator is None:
        return JsonResponse({"error": f"Unknown report type: {report_type}"}, status=400)

    try:
        columns, rows, summary, chart_data, total_db_rows = generator(
            year, period, faculty, threshold
        )
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse({
        "report_type":   report_type,
        "columns":       columns,
        "rows":          rows,
        "summary":       summary,
        "chart_data":    chart_data,
        "total_rows":    len(rows),
        "total_db_rows": total_db_rows,
        "truncated":     total_db_rows > MAX_ROWS,
        "max_rows":      MAX_ROWS,
    })


# ---------------------------------------------------------------------------
# Excel export — uncapped, styled workbook
# ---------------------------------------------------------------------------

REPORT_LABELS = {
    "enrolment":   "Enrolment Summary",
    "pass_rate":   "Pass Rate Analysis",
    "at_risk":     "At-Risk Students",
    "programme":   "Programme Performance",
    "demographic": "Demographic Breakdown",
}


# ---------------------------------------------------------------------------
# Excel helpers — module-level so each function stays under 50 lines.
# All cell access uses ws.cell(row, col) — never ws.columns — to avoid
# MergedCell attribute errors.
# ---------------------------------------------------------------------------
_XL_NAVY  = "0D325D"
_XL_SKY   = "4FB0D1"
_XL_WHITE = "FFFFFF"
_XL_ALT   = "EEF4FA"
_XL_SUMM  = "F0F7FF"
_XL_WIDE  = ("programme", "name", "student", "faculty", "period", "gender")
_XL_PCT   = ("%", "rate", "pass")
_XL_MARK  = ("mark", "avg", "average", "score")


def _xl_fill(h):
    from openpyxl.styles import PatternFill
    return PatternFill("solid", fgColor=h)


def _xl_font(bold=False, size=9, color=_XL_NAVY, italic=False):
    from openpyxl.styles import Font
    return Font(bold=bold, size=size, color=color, italic=italic, name="Segoe UI")


def _xl_align(h="left", v="center", wrap=False):
    from openpyxl.styles import Alignment
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)


def _xl_border():
    from openpyxl.styles import Border, Side
    t = Side(style="thin", color="D0DCE8")
    return Border(left=t, right=t, top=t, bottom=t)


def _xl_title_rows(ws, label, meta_parts, ncols):
    ws.cell(1, 1, label)
    ws.cell(1, 1).font, ws.cell(1, 1).fill, ws.cell(1, 1).alignment = (
        _xl_font(True, 14, _XL_WHITE), _xl_fill(_XL_NAVY), _xl_align()
    )
    ws.row_dimensions[1].height = 30
    if ncols > 1:
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    ws.cell(2, 1, " · ".join(meta_parts))
    ws.cell(2, 1).font, ws.cell(2, 1).fill, ws.cell(2, 1).alignment = (
        _xl_font(False, 9, _XL_WHITE, italic=True), _xl_fill(_XL_SKY), _xl_align()
    )
    ws.row_dimensions[2].height = 18
    if ncols > 1:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)


def _xl_summary_rows(ws, summary_items, ncols):
    """Rows 3-5: KPI cards merged evenly across all columns."""
    bdr = _xl_border()
    n   = min(len(summary_items), 4)
    blk = max(ncols // max(n, 1), 2)
    for idx, (lbl, val) in enumerate(summary_items[:n]):
        cs = idx * blk + 1
        ce = min(cs + blk - 1, ncols)
        c3 = ws.cell(3, cs, lbl)
        c3.font, c3.fill, c3.alignment, c3.border = (
            _xl_font(False, 8, "5A7896"), _xl_fill(_XL_SUMM), _xl_align("center"), bdr
        )
        c4 = ws.cell(4, cs, str(val))
        c4.font, c4.fill, c4.alignment, c4.border = (
            _xl_font(True, 13, _XL_NAVY), _xl_fill(_XL_SUMM), _xl_align("center"), bdr
        )
        if ce > cs:
            ws.merge_cells(start_row=3, start_column=cs, end_row=3, end_column=ce)
            ws.merge_cells(start_row=4, start_column=cs, end_row=4, end_column=ce)
        for mc in range(cs + 1, ce + 1):
            ws.cell(3, mc).fill = _xl_fill(_XL_SUMM)
            ws.cell(4, mc).fill = _xl_fill(_XL_SUMM)
    ws.row_dimensions[3].height = 16
    ws.row_dimensions[4].height = 26
    ws.row_dimensions[5].height = 6


def _xl_header_row(ws, columns):
    bdr = _xl_border()
    for ci, col in enumerate(columns, start=1):
        c = ws.cell(6, ci, col)
        c.font, c.fill, c.alignment, c.border = (
            _xl_font(True, 9, _XL_WHITE), _xl_fill(_XL_NAVY), _xl_align(), bdr
        )
    ws.row_dimensions[6].height = 22


def _xl_data_rows(ws, rows, cols_lc):
    bdr = _xl_border()
    for ri, row in enumerate(rows):
        r_num = ri + 7
        bg    = _XL_ALT if ri % 2 == 0 else _XL_WHITE
        for ci, value in enumerate(row, start=1):
            col_h  = cols_lc[ci - 1]
            c      = ws.cell(r_num, ci, value)
            c.fill, c.border = _xl_fill(bg), bdr
            is_num = isinstance(value, (int, float))
            c.font      = _xl_font(bold=(ci == 1 and not is_num))
            c.alignment = _xl_align("right" if is_num else "left")
            if is_num and isinstance(value, float):
                if any(kw in col_h for kw in _XL_PCT):
                    c.number_format = '0.0"%"'
                elif any(kw in col_h for kw in _XL_MARK):
                    c.number_format = "0.0"
        ws.row_dimensions[r_num].height = 17


def _xl_col_widths(ws, ncols, cols_lc, n_data_rows):
    from openpyxl.utils import get_column_letter
    for ci in range(1, ncols + 1):
        col_h   = cols_lc[ci - 1]
        is_wide = any(kw in col_h for kw in _XL_WIDE)
        max_len = max(
            (len(str(ws.cell(r, ci).value))
             for r in range(6, n_data_rows + 7)
             if ws.cell(r, ci).value is not None),
            default=8,
        )
        cap   = 70 if is_wide else 28
        min_w = 12 if is_wide else 14
        ws.column_dimensions[get_column_letter(ci)].width = min(max(max_len + 4, min_w), cap)


def _build_excel(report_type, columns, rows, summary, filters):
    """Return a BytesIO buffer containing the styled .xlsx workbook."""
    import datetime
    from io import BytesIO

    import openpyxl
    from openpyxl.utils import get_column_letter

    label   = REPORT_LABELS.get(report_type, report_type.replace("_", " ").title())
    ncols   = len(columns)
    cols_lc = [c.lower() for c in columns]
    now_str = datetime.datetime.now().strftime("%d %B %Y, %H:%M")
    meta    = [f"Generated: {now_str}"] + [f"{k.title()}: {v}" for k, v in filters.items() if v]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = label

    _xl_title_rows(ws, label, meta, ncols)
    _xl_summary_rows(ws, list(summary.items()), ncols)
    _xl_header_row(ws, columns)
    _xl_data_rows(ws, rows, cols_lc)
    _xl_col_widths(ws, ncols, cols_lc, len(rows))

    ws.freeze_panes = ws.cell(7, 1)
    ws.auto_filter.ref = f"A6:{get_column_letter(ncols)}6"

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


@ajax_login_required
@require_GET
def reports_export_csv(request):
    """Export the full (uncapped) report as a styled Excel workbook."""
    report_type = request.GET.get("report_type", "enrolment").strip()
    year        = request.GET.get("year",    "").strip()
    period      = request.GET.get("period",  "").strip()
    faculty     = request.GET.get("faculty", "").strip()
    threshold   = _parse_threshold(request.GET.get("threshold", ""))

    generators = {
        "enrolment":   _report_enrolment,
        "pass_rate":   _report_pass_rate,
        "at_risk":     _report_at_risk,
        "programme":   _report_programme,
        "demographic": _report_demographic,
    }
    generator = generators.get(report_type)
    if generator is None:
        return JsonResponse({"error": f"Unknown report type: {report_type}"}, status=400)

    columns, rows, summary, _, _ = generator(year, period, faculty, threshold, cap=999_999)

    filters = {"year": year, "period": period, "faculty": faculty}
    if report_type == "at_risk":
        filters["threshold"] = f"avg mark < {threshold}"

    try:
        buf = _build_excel(report_type, columns, rows, summary, filters)
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": f"Could not build Excel file: {exc}"}, status=500)

    resp = HttpResponse(
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="report_{report_type}.xlsx"'
    return resp


# ---------------------------------------------------------------------------
# Shared query helpers
# ---------------------------------------------------------------------------

def _parse_threshold(raw):
    try:
        return max(0.0, min(100.0, float(raw)))
    except (TypeError, ValueError):
        return float(DEFAULT_THRESHOLD)


def _d(val):
    """Return val if truthy, else em-dash placeholder."""
    return val if val else "—"


def _bar_chart(title, categories, series_name, data, color=None, y_max=None):
    chart = {
        "type":       "bar",
        "title":      title,
        "categories": categories,
        "series":     [{"name": series_name, "data": data}],
    }
    if color:
        chart["color"] = color
    if y_max is not None:
        chart["yMax"] = y_max
    return chart


def _base_qs(year, period, faculty):
    qs = Registration.objects.select_related(
        "student",
        "programme__department__faculty",
        "period",
    )
    if year:
        qs = qs.filter(
            Q(period__academic_year__icontains=year) | Q(period__name__icontains=year)
        )
    if period:
        qs = qs.filter(period__name__icontains=period)
    if faculty:
        qs = qs.filter(programme__department__faculty__name__icontains=faculty)
    return qs


def _cr_base_qs(year, period, faculty):
    qs = CourseResult.objects.filter(mark__isnull=False).select_related(
        "registration__student",
        "registration__programme__department__faculty",
        "registration__period",
    )
    if year:
        qs = qs.filter(
            Q(registration__period__academic_year__icontains=year)
            | Q(registration__period__name__icontains=year)
        )
    if period:
        qs = qs.filter(registration__period__name__icontains=period)
    if faculty:
        qs = qs.filter(
            registration__programme__department__faculty__name__icontains=faculty
        )
    return qs


def _pct(numerator, denominator):
    return round(numerator / denominator * 100) if denominator else 0


# ---------------------------------------------------------------------------
# Report generators
# Each returns: (columns, rows, summary, chart_data, total_db_rows)
# ---------------------------------------------------------------------------

def _report_enrolment(year, period, faculty, threshold, cap=MAX_ROWS):  # noqa: ARG001
    qs = (
        _base_qs(year, period, faculty)
        .values(
            "programme__department__faculty__name",
            "programme__name",
            "period__name",
        )
        .annotate(registrations=Count("id"), students=Count("student", distinct=True))
        .order_by(
            "programme__department__faculty__name",
            "programme__name",
            "period__name",
        )
    )
    total_db_rows = qs.count()
    rows = [
        [_d(r["programme__department__faculty__name"]),
         _d(r["programme__name"]),
         _d(r["period__name"]),
         r["students"],
         r["registrations"]]
        for r in qs[:cap]
    ]
    fac_students: dict[str, int] = defaultdict(int)
    for r in rows:
        fac_students[r[0]] += r[3]
    fac_items = sorted(fac_students.items(), key=lambda x: x[1], reverse=True)
    chart = _bar_chart(
        "Students by Faculty",
        [i[0] for i in fac_items],
        "Students",
        [i[1] for i in fac_items],
    )
    summary = {
        "Students":      sum(r[3] for r in rows),
        "Registrations": sum(r[4] for r in rows),
        "Programmes":    len({r[1] for r in rows}),
        "Periods":       len({r[2] for r in rows}),
    }
    return ["Faculty", "Programme", "Period", "Students", "Registrations"], rows, summary, chart, total_db_rows


def _build_pass_rate_row(r, threshold):
    total  = r["total"]
    passed = r["passed"]
    avg    = round(float(r["avg_mark"])) if r["avg_mark"] is not None else "—"
    return [
        _d(r["registration__programme__department__faculty__name"]),
        _d(r["registration__programme__name"]),
        total,
        passed,
        total - passed,
        _pct(passed, total),
        avg,
    ]


def _report_pass_rate(year, period, faculty, threshold, cap=MAX_ROWS):
    grouped = (
        _cr_base_qs(year, period, faculty)
        .values(
            "registration__programme__department__faculty__name",
            "registration__programme__name",
        )
        .annotate(
            total=Count("id"),
            passed=Count("id", filter=Q(mark__gte=threshold)),
            avg_mark=Avg("mark"),
        )
        .order_by(
            "registration__programme__department__faculty__name",
            "registration__programme__name",
        )
    )
    total_db_rows = grouped.count()
    rows = [_build_pass_rate_row(r, threshold) for r in grouped[:cap]]

    overall_total  = sum(r[2] for r in rows)
    overall_passed = sum(r[3] for r in rows)
    summary = {
        "Total Results":     overall_total,
        "Overall Pass Rate": f"{_pct(overall_passed, overall_total)}%",
        "Programmes":        len({r[1] for r in rows}),
    }
    top = sorted(rows, key=lambda r: r[2], reverse=True)[:20]
    chart = _bar_chart(
        "Pass Rate by Programme (top 20)",
        [r[1] for r in top],
        "Pass Rate %",
        [r[5] for r in top],
        y_max=100,
    )
    cols = ["Faculty", "Programme", "Total Results", "Passed", "Failed", "Pass Rate %", "Avg Mark"]
    return cols, rows, summary, chart, total_db_rows


def _build_at_risk_row(r):
    return [
        r["registration__student__registration_number"],
        f"{r['registration__student__first_names']} {r['registration__student__surname']}".strip(),
        _d(r["registration__programme__name"]),
        _d(r["registration__programme__department__faculty__name"]),
        _d(r["registration__period__name"]),
        round(float(r["avg_mark"])),
        r["courses_failed"],
        r["total_courses"],
    ]


def _report_at_risk(year, period, faculty, threshold, cap=MAX_ROWS):
    grouped = (
        _cr_base_qs(year, period, faculty)
        .values(
            "registration__student__registration_number",
            "registration__student__first_names",
            "registration__student__surname",
            "registration__programme__name",
            "registration__programme__department__faculty__name",
            "registration__period__name",
        )
        .annotate(
            avg_mark=Avg("mark"),
            courses_failed=Count("id", filter=Q(mark__lt=threshold)),
            total_courses=Count("id"),
        )
        .filter(avg_mark__lt=threshold)
        .order_by(
            "registration__student__surname",
            "registration__student__first_names",
            "registration__student__registration_number",
        )
    )
    total_db_rows = grouped.count()
    rows = [_build_at_risk_row(r) for r in grouped[:cap]]

    fac_counts: dict[str, int] = defaultdict(int)
    for r in rows:
        fac_counts[r[3]] += 1
    fac_items = sorted(fac_counts.items(), key=lambda x: x[1], reverse=True)
    chart = _bar_chart(
        f"At-Risk Students by Faculty (avg mark < {threshold})",
        [i[0] for i in fac_items],
        "At-Risk Students",
        [i[1] for i in fac_items],
        color="#dc2626",
    )
    summary = {
        "At-Risk Students": len(rows),
        "Threshold":        f"Avg < {threshold}",
        "Faculties":        len(fac_counts),
    }
    cols = ["Reg Number", "Student", "Programme", "Faculty", "Period", "Avg Mark", "Courses Failed", "Total Courses"]
    return cols, rows, summary, chart, total_db_rows


def _build_programme_rows(reg_map, cr_map, threshold, keys):
    rows = []
    for prog, fac in keys:
        reg  = reg_map.get((prog, fac), {})
        cr   = cr_map.get((prog, fac), {})
        tot  = cr.get("total_results", 0)
        pas  = cr.get("passed", 0)
        avg  = round(float(cr["avg_mark"])) if cr.get("avg_mark") is not None else "—"
        rows.append([
            _d(prog), _d(fac),
            reg.get("students", 0), reg.get("enrolments", 0),
            avg, _pct(pas, tot) if tot else "—",
        ])
    return rows


def _report_programme(year, period, faculty, threshold, cap=MAX_ROWS):
    reg_qs = (
        _base_qs(year, period, faculty)
        .values("programme__name", "programme__department__faculty__name")
        .annotate(enrolments=Count("id"), students=Count("student", distinct=True))
    )
    reg_map = {(r["programme__name"], r["programme__department__faculty__name"]): r for r in reg_qs}

    cr_grouped = (
        _cr_base_qs(year, period, faculty)
        .values("registration__programme__name", "registration__programme__department__faculty__name")
        .annotate(
            avg_mark=Avg("mark"),
            total_results=Count("id"),
            passed=Count("id", filter=Q(mark__gte=threshold)),
        )
    )
    cr_map = {
        (r["registration__programme__name"], r["registration__programme__department__faculty__name"]): r
        for r in cr_grouped
    }

    all_keys = sorted(set(reg_map) | set(cr_map))
    total_db_rows = len(all_keys)
    rows = _build_programme_rows(reg_map, cr_map, threshold, all_keys[:cap])

    top = sorted(rows, key=lambda r: r[2], reverse=True)[:20]
    chart = _bar_chart(
        "Enrolments by Programme (top 20)",
        [r[0] for r in top],
        "Students",
        [r[2] for r in top],
    )
    summary = {
        "Programmes":       len(rows),
        "Total Students":   sum(r[2] for r in rows),
        "Total Enrolments": sum(r[3] for r in rows),
    }
    cols = ["Programme", "Faculty", "Students", "Enrolments", "Avg Mark", "Pass Rate %"]
    return cols, rows, summary, chart, total_db_rows


def _report_demographic(year, period, faculty, threshold, cap=MAX_ROWS):  # noqa: ARG001
    grouped = list(
        _base_qs(year, period, faculty)
        .values("programme__department__faculty__name", "student__gender")
        .annotate(count=Count("student", distinct=True))
        .order_by("programme__department__faculty__name", "student__gender")
        [:cap]
    )

    fac_totals: dict[str, int] = defaultdict(int)
    for r in grouped:
        fac_totals[_d(r["programme__department__faculty__name"])] += r["count"]

    rows = [
        [
            _d(r["programme__department__faculty__name"]),
            (r["student__gender"] or "Unspecified").title(),
            r["count"],
            _pct(r["count"], fac_totals[_d(r["programme__department__faculty__name"])]),
        ]
        for r in grouped
    ]
    total_db_rows = len(rows)

    all_genders = sorted({r[1] for r in rows})
    fac_gender: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        fac_gender[r[0]][r[1]] += r[2]
    fac_order = sorted(fac_gender.keys())
    GENDER_COLORS = {"Male": "#1a6fa8", "Female": "#e05fa0", "Unspecified": "#9cb3c8"}
    chart = {
        "type":       "stacked_bar",
        "title":      "Gender Distribution by Faculty",
        "categories": fac_order,
        "series": [
            {
                "name":  g,
                "data":  [fac_gender[f].get(g, 0) for f in fac_order],
                "color": GENDER_COLORS.get(g, "#4fb0d1"),
            }
            for g in all_genders
        ],
    }
    summary = {
        "Total Students": sum(r[2] for r in rows),
        "Faculties":      len(fac_totals),
        "Gender Groups":  len(all_genders),
    }
    return ["Faculty", "Gender", "Students", "% of Faculty"], rows, summary, chart, total_db_rows
