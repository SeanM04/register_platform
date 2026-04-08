"""Constants for the story-first landing dashboard."""

OVERVIEW_ACTIVE_KEY = "dashboard"
OVERVIEW_PAGE_TITLE = "Overview Dashboard"

OVERVIEW_SUMMARY_CARD_SPECS = [
    {"key": "enrolled", "label": "Enrolled Students", "tone": "neutral"},
    {"key": "registered", "label": "Registrations", "tone": "neutral"},
    {"key": "pass_rate", "label": "Pass Rate", "tone": "success"},
    {"key": "completion_rate", "label": "Completion Rate", "tone": "neutral"},
    {"key": "on_time_graduation", "label": "On-Time Graduation", "tone": "neutral"},
    {"key": "first_year_retention", "label": "First Year Retention", "tone": "success"},
    {"key": "students_satisfaction", "label": "Student Satisfaction", "tone": "success"},
    {"key": "at_risk", "label": "At-Risk Students", "tone": "danger"},
]

RISK_BAND_CONFIG = [
    {"key": "critical", "label": "Critical (6+)", "min_score": 6, "max_score": None, "tone": "critical"},
    {"key": "high", "label": "High (4-5)", "min_score": 4, "max_score": 5, "tone": "high"},
    {"key": "moderate", "label": "Moderate (2-3)", "min_score": 2, "max_score": 3, "tone": "moderate"},
    {"key": "stable", "label": "Stable (0-1)", "min_score": 0, "max_score": 1, "tone": "stable"},
]

PROGRESS_STATUS_CONFIG = [
    {"key": "proceed", "label": "Proceed", "tone": "success"},
    {"key": "retake", "label": "Retake / Repeat", "tone": "warning"},
    {"key": "pending", "label": "Pending Review", "tone": "neutral"},
    {"key": "exit", "label": "Exited", "tone": "danger"},
    {"key": "other", "label": "Other", "tone": "info"},
]
